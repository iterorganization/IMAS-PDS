%% muscle controller initialization script, PSC-4 variant (PSC in the loop).
% Copy of muscle_controller_NICE_IMAS_iter_init.m (student's fork 5620eb5 + P2d port) that, with the
% setting psc_enabled = 1 (default), runs pcssp_controller_and_ps_psc.slx: the real PSC
% (pcssp-nightly src/psc/PSC.slx, Subsystem Reference) produces Ipl_ref for KCURR from the four PSC
% files in the setting psc_config_dir. Clock (D20): the Simulink clock starts at 0 = t_start (the
% window start, = the converter's --cut-at), every From Workspace reference is shifted by -t_start
% and the PSC's segment 0 starts at the window start (PSCSysObj.m:66-70 counts from t = 0).
% psc_enabled = 0 runs the original wrapper exactly as the original script.
% 
% based on work of R. Nouailletas, T. Ravensbergen et M. Schneider, G. Gros

% This script initializes MUSCLE3 (logging, ports),
% initializes the controller params, and then launches a simulation.
% The controller receives a line_avg_density via MUSCLE3, and fires a
% pellet when the integral of the requested particle flow is larger than
% the size of a single pellet

fprintf('Controller Initialization\n')

DEBUG_LOG = true;
% run('../../initNice4matlab.m')
% run('../../../../pcs/pcssp_pcs_add_paths.m')
% get PCS stuff
pcs_path = getenv('PCS_PATH');
if isempty(pcs_path)
    error('PCS_PATH environment variable not set');
end
run('pcssp_pcs_add_paths')

logger = py.logging.getLogger();
setdefault(py.os.environ,'MUSCLE_INSTANCE','macro');

py.logging.basicConfig( ...
    pyargs( ...
        "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s", ...
        "level", py.logging.INFO ...
    ) ...
)

%% Create libmuscle instance, specify all Ports
% Ports need to match the MUSCLE3 yaml description on the other side
logger.info("Starting Simulink actor")
ports = py.dict();
ports{py.getattr(@py.ymmsl.Operator,"F_INIT")} = py.list({"equilibrium_in_f", "pf_active_in_f", "pulse_schedule_in_f"});
ports{py.getattr(@py.ymmsl.Operator,"S")} = py.list({"equilibrium_in_s", "pf_active_in_s"});
ports{py.getattr(@py.ymmsl.Operator,"O_I")} = py.list({"pf_active_out_i"});

%% declare muscle3 as non-codegen compatible
coder.extrinsic('py.libmuscle.Instance');

% write instance object to matlab workspace. Currently, there is no other
% way than to retrieve it from there within simulink with nasty 'evalin'
% statements.
% only populate when not yet there
if ~exist('instance','var') == 1
    instance = py.libmuscle.Instance(ports);
end

if instance.reuse_instance()
    %% Prepare IDS Python object
    % equilibrium_python=py.imas.equilibrium();
    equilibrium_python=ids_init('equilibrium');
    % equilibrium_python=ids_gen_allocate(equilibrium_python, 'equilibrium', '');
    % equilibrium_python=py.imas.IDSFactory().equilibrium();

    %% Init NICE parameters
    msg_eq = instance.receive("equilibrium_in_f");
    equilibrium_serial=uint8(msg_eq.data);
    equilibrium = imas_deserialize(equilibrium_serial,'equilibrium');

    msg_pfa = instance.receive("pf_active_in_f");
    pfa_serial=uint8(msg_pfa.data);
    pf_active = imas_deserialize(pfa_serial, 'pf_active');

    % Optional designer Ip reference: pulse_schedule IDS on pulse_schedule_in_f
    % (DD 4: flux_control/ip/reference, IMAS sign, time base flux_control/time or,
    % for a homogeneous-time IDS, /time). Used for Ipl_ref below only when the port is
    % connected and the reference is filled; otherwise Ipl_ref tracks the F_INIT
    % equilibrium Ip exactly as before.
    ps_ip_ref = [];
    ps_ip_time = [];
    if instance.is_connected("pulse_schedule_in_f")
        msg_ps = instance.receive("pulse_schedule_in_f");
        pulse_schedule = imas_deserialize(uint8(msg_ps.data), 'pulse_schedule');
        ps_ip_ref = pulse_schedule.flux_control.ip.reference;
        ps_ip_time = pulse_schedule.flux_control.time;
        if isempty(ps_ip_time)
            ps_ip_time = pulse_schedule.time;
        end
        if isempty(ps_ip_ref) || all(ps_ip_ref == -9.0e40)
            logger.info('pulse_schedule_in_f: no flux_control/ip/reference, Ipl_ref from the equilibrium');
            ps_ip_ref = [];
        else
            logger.info(sprintf('pulse_schedule_in_f: Ipl_ref from flux_control/ip/reference (%d samples, %.4f to %.4f s, %.6g to %.6g A)', ...
                numel(ps_ip_ref), ps_ip_time(1), ps_ip_time(end), min(ps_ip_ref), max(ps_ip_ref)));
        end
    end

    t_start = equilibrium.time(1);
    t_max = equilibrium.time(end);
    psc_enabled = double(instance.get_setting('psc_enabled', pyargs('default', 1)));
    if psc_enabled
        psc_config_dir = char(instance.get_setting('psc_config_dir'));
        psc_time_offset = t_start;   % Simulink/PSC time 0 = t_start (read by psc_log_row.m)
    else
        psc_time_offset = 0;
    end
    logger.info(sprintf('psc_enabled = %d, Simulink time offset = %.6f s', psc_enabled, psc_time_offset));

    %% call simulink model inits
    reference_current=[];
    for i=1:length(pf_active.coil)
        reference_current=[reference_current, pf_active.coil{i}.current.data];
    end

    %Init Simulink object
    n_slices = length(equilibrium.time_slice);
    ip_ref = zeros(1,n_slices);
    rpl_ref = zeros(1,n_slices);
    zpl_ref = zeros(1,n_slices);
    
    N_GAPS = 62; % 6 used by the controller
    gaps_ref = zeros(N_GAPS,n_slices); %TODO: update gaps
    
    plasma_position = char(instance.get_setting('plasma_position', pyargs('default', 'geometric_axis')));
    if ~any(strcmp(plasma_position, {'geometric_axis','magnetic_axis','current_centre'}))
        error('muscle_controller_NICE_IMAS_iter_init:plasma_position',['plasma_position must be ''geometric_axis'', ''magnetic_axis'' or ''current_centre'' (got ''%s'').'], plasma_position);
    end
    logger.info(sprintf('plasma position = %s', plasma_position));

    for i=1:n_slices
        ip_ref(i)   = equilibrium.time_slice{i}.global_quantities.ip;
        if strcmp(plasma_position, 'geometric_axis')
            rpl_ref(i) = equilibrium.time_slice{i}.boundary.geometric_axis.r;
            zpl_ref(i) = equilibrium.time_slice{i}.boundary.geometric_axis.z;
            rpl_ref(i) = geo_ref_with_fallback(rpl_ref(i), equilibrium.time_slice{i}, 'r', logger);
            zpl_ref(i) = geo_ref_with_fallback(zpl_ref(i), equilibrium.time_slice{i}, 'z', logger);
        elseif strcmp(plasma_position, 'current_centre')
            cc = equilibrium.time_slice{i}.global_quantities.current_centre;
            if ~isempty(cc.r) && cc.r > 0 && cc.r < 1e30
                rpl_ref(i) = cc.r;
                zpl_ref(i) = cc.z;
            else
                [rpl_ref(i), zpl_ref(i)] = current_centre_estimate(equilibrium.time_slice{i});
                if isnan(zpl_ref(i))
                    rpl_ref(i) = geo_ref_with_fallback(equilibrium.time_slice{i}.boundary.geometric_axis.r,equilibrium.time_slice{i}, 'r', logger);
                    zpl_ref(i) = geo_ref_with_fallback(equilibrium.time_slice{i}.boundary.geometric_axis.z,equilibrium.time_slice{i}, 'z', logger);
                end
            end
        else
            rpl_ref(i) = equilibrium.time_slice{i}.global_quantities.magnetic_axis.r;
            zpl_ref(i) = equilibrium.time_slice{i}.global_quantities.magnetic_axis.z;
            
        end
    end

    Ipl_ref =  timeseries(ip_ref,equilibrium.time);
    if ~isempty(ps_ip_ref)
        % Same signed (IMAS, Ip < 0) frame as the equilibrium branch above.
        Ipl_ref = timeseries(ps_ip_ref(:)', ps_ip_time(:)');
    end
    Rpl_ref = timeseries(rpl_ref,equilibrium.time);
    Zpl_ref = timeseries(zpl_ref,equilibrium.time);
    Gaps_ref = timeseries(gaps_ref, equilibrium.time);
    CSPF_curr_ref = timeseries(reference_current,equilibrium.time);
    if psc_enabled
        % references on the PSC clock (0 at t_start); Ipl_ref is not read by the PSC wrapper
        % (its From Workspace block is replaced by the PSC), kept for the log only
        Ipl_ref.Time = Ipl_ref.Time - t_start;
        Rpl_ref.Time = Rpl_ref.Time - t_start;
        Zpl_ref.Time = Zpl_ref.Time - t_start;
        Gaps_ref.Time = Gaps_ref.Time - t_start;
        CSPF_curr_ref.Time = CSPF_curr_ref.Time - t_start;
    end

    enable_KCURR= double(instance.get_setting('KCURR', pyargs('default', 1)));
    IpControlMode_KCURR= double(instance.get_setting('control_Ip', pyargs('default', 1)));
    schedulingVar_KCURR=0;

    enable_RZIp=double(instance.get_setting('RZIp', pyargs('default', 0)));
    IpControlMode_RZIp=0;
    %schedulingVar_RZIp =[50, 1, 1.2]'; built inside the controller with actual values of [t,li3,elongation]
    
    enable_VS = double(instance.get_setting('VS', pyargs('default', 1))); % Enable VS control (=1 enabled)
    VSControlMode = double(instance.get_setting('VS_control_mode', pyargs('default', 3))); % VS controller Mode {'Off (0)'; 'VS1 (1)'; 'VS3 (2)'; 'VS1+VS3 (3)'}
    %schedulingVar_VS = 0.9; %built inside the controller with actual values of [li3]
    VSIpScaling = 1;% VS control action scaled with (nominal or estimated) Ip {'On with nominal Ip (1)'; 'On with estimated Ip (2)'}

    SchedulingVar_GapContr = 0; % Vector of variables for gain scheduling gap control
    ShapeIpControlMode = double(instance.get_setting('Shape_control', pyargs('default', 0))); %only gap control Shape-Ip control mode {'Off (0)'; 'PositionControl Rpl and Zpl (1)'; 'Isoflux ShapeControl (2)'; 'Isoflux Shape Control with Xpoint (3)'; 'Gap Control (4)'; 'Only CSPF Currents (5)'}
    SCIpScaling = 0; %Shape control action scaled with (nominal or estimated) Ip {'Off (0)'; 'On with nominal Ip (1)'; 'On with estimated Ip (2)'}
    IpControlMode = 0; % Activation of Ip Control (In case of CCS, 0 non active, 1 if integrated with KCURR, 2 if integrated with Shape control).

    AllocatorMode = 1;
    usePSModel = double(instance.get_setting('PSModel', pyargs('default', 1))); 

    % Exchange period with the plant (s), the sample time of the CODAC_input, MATLAB Function and Output blocks of the Simulink model:
    in_out_dt = double(instance.get_setting('in_out_msg_dt', pyargs('default', 0.001)));

    zdot_disturbance = double(instance.get_setting('zdot_disturbance', pyargs('default', 0)));
    zdot_filter = double(instance.get_setting('zdot_filter', pyargs('default', 0)));

    nice_signs = double(instance.get_setting('nice_signs', pyargs('default', 1))); % 1 with NICE evo_rd


    logger.info(sprintf('exchange period in_out_dt = %g s', in_out_dt));

    %%  Simulink controller

    obj = pcssp_KCURR_PFPO1_obj();
    obj.init;
    obj.setup;

    obj2 = RZIp_CCS_wrapper_obj();
    obj2.init;
    obj2.setup;

    obj3 = pcssp_VS_obj();
    obj3.init;
    obj3.setup;

    obj4 = shapeIp_CCS_obj();
    obj4.init;
    obj4.setup;

    obj5 = VS1_allocator_obj();
    obj5.init;
    obj5.setup;

    obj6 = pcssp_PowerSupplies_obj();
    obj6.init;
    obj6.setup;

    if psc_enabled
        psc_framework_conf();   % configurationSettings in base for the pcssp_RZIp_CCS wrapper (nightly scdds)
    end

    % Data dictionary of the top model
    if psc_enabled
        top_mdl = 'pcssp_controller_and_ps_psc';
    else
        top_mdl = 'pcssp_controller_and_ps';
    end
    top_dd_file = fullfile(fileparts(which([top_mdl '.slx'])), [top_mdl '.sldd']);
    if isfile(top_dd_file)
        top_dd = Simulink.data.dictionary.open(top_dd_file);
    else
        top_dd = Simulink.data.dictionary.create(top_dd_file);
    end
    if ~top_dd.EnableAccessToBaseWorkspace
        top_dd.EnableAccessToBaseWorkspace = true;
    end
    for dd_source = {'pcssp_KCURR_PFPO1.sldd', 'pcssp_PowerSupplies.sldd'}
        if ~any(strcmp(top_dd.DataSources, dd_source{1}))
            addDataSource(top_dd, dd_source{1});
        end
    end
    if top_dd.HasUnsavedChanges
        saveChanges(top_dd);
    end
    close(top_dd);
    if psc_enabled
        % pcssp-nightly ebf3ee0 src/psc/PSC.slx was saved by R2026a: allow loading it in this MATLAB (session preference)
        set_param(0, 'ErrorIfLoadNewModel', 'off');
    end
    load_system(top_mdl);
    set_param(top_mdl, 'DataDictionary', [top_mdl '.sldd']);
    if psc_enabled
        % PSC mask set-up with the PSC's own callback (buses PSC_*_Bus, PSCObj in base)
        psc_setup_block(top_mdl, psc_config_dir);
        logger.info(sprintf('PSC configured from %s', psc_config_dir));
        psc_csv = fullfile(getenv('RUN_DIR'), 'psc_log.csv');
        if exist(psc_csv, 'file'), delete(psc_csv); end
        f = fopen(psc_csv, 'w');
        fprintf(f, '%s\n', strjoin({'t_abs','t_psc','psc_ref__Ipl_ref','psc_ref__current_segment', ...
            'psc_ref_lastModSegment','psc_OldModSegment','psc_segmentTime','psc_simTime','psc_lastTimeDiff', ...
            'glb_ps__run_plasma','glb__PulseDone','glb_ps__ip_too_high','glb_ps__end_of_flux', ...
            'glb_ps__z_excursion','in_ip_ip__meas','in_z_meas','in_cs_margin'}, ','));
        fclose(f);
    end

    % create Reference for Simulink
    in = Simulink.SimulationInput(top_mdl);
    if psc_enabled
        in = in.setModelParameter('StartTime','0','StopTime',num2str(t_max - t_start,17));
    else
        in = in.setModelParameter('StartTime',num2str(t_start),'StopTime',num2str(t_max));
    end
    in = in.setModelParameter('SaveOutput', 'on');

    fprintf('Start closed loop\n')
    if DEBUG_LOG
        csv_file = fullfile(getenv('RUN_DIR'), 'simulink_log.csv');
        if exist(csv_file, 'file'), delete(csv_file); end
            sig = { 
                'KCURR_CSPF_ctrl_e',11;
                'KCURR_Ip_ctrl_e',1;  
                'KCURR_residual_ctrl_e',11; 
                'KCURR_actual_ref',11;
                    'RZIp_CSPF_curr_cmd',11;
                    'RZIp_VS1_cmd',1;
                'VS_VS1_cmd',1;   
                'VS_VS3_cmd',1;
                    'Shape_CSPF_curr_cmd',11;
                    'Shape_VS_decoupling',11;
                'Output_total',14;
                    'CSPF_curr_ref',11;
                    'Zdot',1;
                    'Ip_ref',1;
                    'Z_ref',1;
                    'R_ref',1;
                'ip',1;
                'zpl', 1;
            };
        h = {'t'};
        for k = 1:size(sig,1)
            if sig{k,2} == 1
                h{end+1} = sig{k,1};
            else
                for j = 1:sig{k,2}
                    h{end+1} = sprintf('%s_%d', sig{k,1}, j);
                end
            end
        end
        f = fopen(csv_file, 'w');  fprintf(f, '%s\n', strjoin(h, ','));  fclose(f);
    end

    tic;
    logs = sim(in);
    close_system(top_mdl,0);
    simulation_time=toc;
    plasma_duration=t_max-t_start;

    fprintf(['\nControl over! ' num2str(simulation_time) 's of simulation for ' num2str(plasma_duration) 's of plasma.\n']);
end

instance.reuse_instance();

function value = geo_ref_with_fallback(value, ts, field, logger)

    persistent warned
    if isempty(warned)
        warned = false;
    end
    if isempty(value) || abs(value) > 1e30
        outline_field = ts.boundary.outline.(field);
        if ~isempty(outline_field)
            value = (max(outline_field) + min(outline_field)) / 2;
            fallback = 'outline midpoint';
        else
            value = ts.global_quantities.magnetic_axis.(field);
            fallback = 'magnetic_axis';
        end
        if ~warned
            logger.warning(sprintf( ...
                ['muscle_controller_NICE_IMAS_iter_init: boundary.geometric_axis.%s was empty/sentinel, falling back to %s'], field, fallback));
            warned = true;
        end
    end
end
