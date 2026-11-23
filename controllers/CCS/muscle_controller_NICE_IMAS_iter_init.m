%% CCS magnetic controller: MUSCLE3 actor init and Simulink run.
% Based on work of R. Nouailletas, T. Ravensbergen, M. Schneider and G. Gros.
%
% 1. creates the MUSCLE3 instance and receives the reference equilibrium (the inverse run)
%    and the reference coil currents;
% 2. builds the references and the parameters read by the Simulink model (base workspace);
% 3. inits the PCSSP modules and runs pcssp_controller_and_ps, which exchanges with NICE at
%    every step through muscle_nice2control / muscle_control2nice.
% The model runs from t = 0, on NICE's steps: plasma time = Simulink time + t_start.
% With the setting psc_enabled = 1 the PSC block of the model (pulse supervision, pcssp-nightly)
% gets its configuration from psc_config_dir.
% With the setting mcls_enabled = 1 (requires psc_enabled = 1) the model pcssp_controller_and_ps_mcls runs instead:
% the same model plus the MCLS (Magnetic Control Local Supervisor) block, whose outputs drive the mode inputs of
% KCURR, RZIp and VS (and of ShapeIp when mcls_shape_enable = 1); mode table from the YAML file mcls_config
% (controllers/CCS/mcls/mcls_load_table.m), log RUN_DIR/mcls_log.csv. With mcls_enabled = 0 nothing changes.

fprintf('Controller Initialization\n')

DEBUG_LOG = true;   % writes simulink_log.csv in the run directory (columns: sig, below)

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

%% MUSCLE3 instance: the ports must match the workflow ymmsl
logger.info("Starting Simulink actor")
ports = py.dict();
ports{py.getattr(@py.ymmsl.Operator,"F_INIT")} = py.list({"equilibrium_in_f", "pf_active_in_f"});
ports{py.getattr(@py.ymmsl.Operator,"S")} = py.list({"equilibrium_in_s", "pf_active_in_s"});
ports{py.getattr(@py.ymmsl.Operator,"O_I")} = py.list({"pf_active_out_i"});

coder.extrinsic('py.libmuscle.Instance');
% the Simulink blocks reach the instance with evalin('base', ...)
if ~exist('instance','var') == 1
    instance = py.libmuscle.Instance(ports);
end

if instance.reuse_instance()
    %% reference equilibrium and coil currents (F_INIT)
    msg_eq = instance.receive("equilibrium_in_f");
    equilibrium = imas_deserialize(uint8(msg_eq.data), 'equilibrium');
    msg_pfa = instance.receive("pf_active_in_f");
    pf_active = imas_deserialize(uint8(msg_pfa.data), 'pf_active');

    t_start = equilibrium.time(1);   % Simulink time 0 (also read by log_row)
    t_max = equilibrium.time(end);

    %% settings (magnetic_controller.* in the ymmsl)
    enable_KCURR = double(instance.get_setting('KCURR', pyargs('default', 1)));
    IpControlMode_KCURR = double(instance.get_setting('control_Ip', pyargs('default', 1)));
    enable_RZIp = double(instance.get_setting('RZIp', pyargs('default', 0)));
    enable_VS = double(instance.get_setting('VS', pyargs('default', 1)));
    VSControlMode = double(instance.get_setting('VS_control_mode', pyargs('default', 3)));    % 0 off, 1 VS1, 2 VS3, 3 VS1+VS3
    ShapeIpControlMode = double(instance.get_setting('shape_control', pyargs('default', 0)));  % 2 isoflux limiter, 3 isoflux X-point, 4 gaps
    usePSModel = double(instance.get_setting('PSModel', pyargs('default', 1)));
    in_out_dt = double(instance.get_setting('in_out_msg_dt', pyargs('default', 0.001)));      % [s] exchange period with NICE = sample time of the CODAC blocks
    zdot_disturbance = double(instance.get_setting('zdot_disturbance', pyargs('default', 0)));  % noise on zdot (controller_input_preprocess)
    zdot_filter = double(instance.get_setting('zdot_filter', pyargs('default', 0)));            % low pass on zdot
    nice_signs = double(instance.get_setting('nice_signs', pyargs('default', 1)));              % 1 with NICE evo_rd: voltages sent with the opposite sign
    psc_enabled = double(instance.get_setting('psc_enabled', pyargs('default', 0)));            % 1: Ipl_ref from the PSC
    if psc_enabled
        psc_config_dir = char(instance.get_setting('psc_config_dir'));                          % folder with the four PSC files
    end
    t_offset = t_start;   % alias read by mcls_log_row.m and the MCLS block's clock constant (MCLS_clock_offset)
    mcls_enabled = double(instance.get_setting('mcls_enabled', pyargs('default', 0)));          % 1: MCLS in the model
    controller_model = 'pcssp_controller_and_ps';
    if mcls_enabled
        % MCLS: model with the MCLS block, mode table (four Parameter data of the block, base workspace)
        if ~psc_enabled
            error('muscle_controller_NICE_IMAS_iter_init:mcls', 'mcls_enabled = 1 needs psc_enabled = 1 (the MCLS takes ForceControlMode from the PSC bus)');
        end
        controller_model = 'pcssp_controller_and_ps_mcls';
        mcls_dir = fullfile(getenv('CONTROLLER_PATH'), 'mcls');
        addpath(mcls_dir, fullfile(mcls_dir, 'third_party'));
        mcls_config = char(instance.get_setting('mcls_config'));                                % mode-table YAML (required)
        mcls_shape_enable = double(instance.get_setting('mcls_shape_enable', pyargs('default', 0)));   % 1: ShapeIp modes from the MCLS
        [MCMode, StartingMode, NAlarms, NEnablingConditions, mcls_info] = mcls_load_table(mcls_config, ...
            fullfile(mcls_dir, 'mcls_library_defaults.yaml'), fullfile(getenv('RUN_DIR'), 'mcls_diary.txt'));
        logger.info(sprintf('MCLS table %s: %d mode(s) [%s], StartingMode %d, shape guard enable %d; model %s', ...
            mcls_config, numel(MCMode), strjoin(strtrim(mcls_info.MCModeNames), ', '), StartingMode, mcls_shape_enable, controller_model));
    end

    %% controlled gaps and isoflux control points
    GAP_LIST = [3 8 15 21 25 48];   % the gaps used by shapeIp_CCS (nonzero columns of its Proj)
    N_GAPS = 62;
    N_FLUX = 62;                    % flux inputs of shapeIp_CCS; only the first numel(RfluxCTRpts) are used
    % RR3/ZZ3 of the pcs XPT02 case (copy_setup_pcs_params_pcs_expert.m:466-494) without its 9th point, the
    % X-point reference: here the reference flux of mode 3 is the measured psi_xp (at the saddle, or at the
    % reference X-point rxp_ref/zxp_ref with xp_flux_at_ref = 1, as the pcs XPT02 case evaluates FluxXP_est)
    RfluxCTRpts = [4.3863 4.2220 5.1385 7.2929 8.1866 7.0307 4.6170 5.2594];   % [m]
    ZfluxCTRpts = [-1.5 1.5492 3.5094 2.9244 0.6292 -2.0128 -3.6807 -3.9861];
    if ShapeIpControlMode == 2      % limited plasma: the first six points and the touch point (RR2/ZZ2)
        RfluxCTRpts = [RfluxCTRpts(1:6) 4.1000];
        ZfluxCTRpts = [ZfluxCTRpts(1:6) 0.7500];
    end
    R_lim = 4.1053;                 % fixed limiter point [m]: PsiLimiter of muscle_nice2control.m outside mode 2 (mode 2 uses psi_boundary)
    Z_lim = 0.6039;
    flux_scale = double(instance.get_setting('isoflux_flux_scale', pyargs('default', 1)));   % scales the fluxes seen by shapeIp_CCS (references and measurements)

    %% references: one value per slice of the reference equilibrium
    n_slices = length(equilibrium.time_slice);
    ip_ref = zeros(1,n_slices);
    rpl_ref = zeros(1,n_slices);
    zpl_ref = zeros(1,n_slices);
    rxp_ref = nan(1,n_slices);      % NaN where the slice has no X-point
    zxp_ref = nan(1,n_slices);
    psixp_ref = nan(1,n_slices);
    gaps_ref = zeros(N_GAPS,n_slices);
    psi_pts_ref = zeros(numel(RfluxCTRpts), n_slices);
    psi_lim_ref = zeros(1, n_slices);

    reference_current = [];
    for i = 1:length(pf_active.coil)
        reference_current = [reference_current, pf_active.coil{i}.current.data];
    end
    for i = 1:n_slices
        ts = equilibrium.time_slice{i};
        cc = ts.global_quantities.current_centre;
        ip_ref(i) = ts.global_quantities.ip;
        rpl_ref(i) = cc.r;
        zpl_ref(i) = cc.z;
        % gaps and X-point come from the diagnostics actor: without it in the inverse workflow
        % the gaps are missing and the X-point is a mesh node (jumps of 1-3 cm)
        gap = ts.boundary.gap;
        for k = GAP_LIST
            gaps_ref(k, i) = NaN;
            if numel(gap) >= k && ~isempty(gap{k}.value) && abs(gap{k}.value) < 1e30
                gaps_ref(k, i) = gap{k}.value;
            end
        end
        for k = 1:numel(ts.contour_tree.node)
            node = ts.contour_tree.node{k};
            if node.critical_type == 1
                rxp_ref(i) = node.r;
                zxp_ref(i) = node.z;
                psixp_ref(i) = node.psi;
                break
            end
        end
        % psi at the isoflux points, interpolated on NICE's mesh
        g = ts.ggd{1};
        F = scatteredInterpolant(g.r{1}.values(:), g.z{1}.values(:), g.psi{1}.values(:));
        psi_pts_ref(:, i) = F(RfluxCTRpts(:), ZfluxCTRpts(:));
        psi_lim_ref(i) = ts.global_quantities.psi_boundary;   % limited plasma: the touch-point flux is the boundary flux
    end

    % slices without separatrix or X-point take the value of the nearest slice
    missing = isnan(gaps_ref(GAP_LIST, :));
    if any(missing(:))
        logger.warning(sprintf('gap references: %d values not found, taken from the nearest slice', nnz(missing)));
        gaps_ref(GAP_LIST, :) = fillmissing(gaps_ref(GAP_LIST, :), 'nearest', 2);
    end
    xp_missing = isnan(rxp_ref);
    if any(xp_missing)
        logger.warning(sprintf('X-point references: none in %d slices, taken from the nearest slice', nnz(xp_missing)));
        rxp_ref = fillmissing(rxp_ref, 'nearest');
        zxp_ref = fillmissing(zxp_ref, 'nearest');
        psixp_ref = fillmissing(psixp_ref, 'nearest');
    end

    % isoflux reference: psi(control point) - psi(boundary), where the boundary flux is
    % global_quantities.psi_boundary in mode 2 and the X-point's in mode 3; 0 when the point is on the boundary
    if ShapeIpControlMode == 3 && all(xp_missing)
        error('mode 3: no X-point in the reference equilibrium');
    end
    n_ctr = numel(RfluxCTRpts);
    flux_sign = sign(mean(ip_ref)) + (mean(ip_ref) == 0);   % shapeIp_CCS is designed for Ip > 0: fluxes taken to that frame
    flux_scale = flux_sign * flux_scale;
    psi_pts_ref = flux_scale * psi_pts_ref;
    psi_lim_ref = flux_scale * psi_lim_ref;
    psixp_ref = flux_scale * psixp_ref;
    dpsi_ref = zeros(N_FLUX, n_slices);
    if ShapeIpControlMode == 2
        dpsi_ref(1:n_ctr, :) = psi_pts_ref - psi_lim_ref;
    elseif ShapeIpControlMode == 3
        dpsi_ref(1:n_ctr, :) = psi_pts_ref - psixp_ref;
    end

    % read by the From Workspace blocks of the model, on the Simulink time
    t_ref = equilibrium.time - t_start;
    Ipl_ref = timeseries(ip_ref, t_ref);
    Rpl_ref = timeseries(rpl_ref, t_ref);
    Zpl_ref = timeseries(zpl_ref, t_ref);
    Rxp_ref = timeseries(rxp_ref, t_ref);
    Zxp_ref = timeseries(zxp_ref, t_ref);
    Gaps_ref = timeseries(gaps_ref, t_ref);
    dPsi_ref = timeseries(dpsi_ref, t_ref);
    CSPF_curr_ref = timeseries(reference_current, t_ref);

    %% fixed controller parameters (Constant blocks of the model)
    schedulingVar_KCURR = 0;
    IpControlMode_RZIp = 0;         % schedulingVar_RZIp = [t, li3, elongation] comes from the measurements
    % sign of the R and Z errors fed to RZIp_CCS (designed for Ip > 0): both flipped when Ip < 0 (IMAS); the earlier Z runaway came from the VS3 current polarity (controller_input_preprocess.m)
    RZIp_R_sign = double(instance.get_setting('RZIp_R_sign', pyargs('default', sign(mean(ip_ref)) + (mean(ip_ref) == 0))));
    RZIp_Z_sign = double(instance.get_setting('RZIp_Z_sign', pyargs('default', RZIp_R_sign)));
    VSIpScaling = 1;                % VS action scaled with: 1 nominal Ip, 2 estimated Ip
    SchedulingVar_ShapeContr = VSControlMode;   % gain region of shapeIp_CCS (its two regions are identical today)
    % shape action scaled with: 0 nominal Ip, 1 Ip_ref, 2 Ip_est. Default 1: Ip_ref/Ipl_nominal < 0 in the IMAS frame gives the
    % geometric errors (gaps, X-point position) the frame flip they need; the fluxes are already in the design frame (flux_sign)
    SCIpScaling = double(instance.get_setting('SC_Ip_scaling', pyargs('default', 1)));
    xp_flux_at_ref = double(instance.get_setting('xp_flux_at_ref', pyargs('default', 0)));   % 1: mode 3 psi_xp at the reference X-point (muscle_nice2control.m)
    IpControlMode = 0;              % Ip control inside the CCS: 0 off, 1 with KCURR, 2 with the shape controller
    AllocatorMode = 1;
    save(fullfile(getenv('RUN_DIR'), 'isoflux_refs.mat'), 'RfluxCTRpts', 'ZfluxCTRpts', 'dpsi_ref', 'rxp_ref', 'zxp_ref', 't_ref', 't_start', 'flux_scale', 'flux_sign', 'SCIpScaling', 'xp_flux_at_ref', 'RZIp_R_sign', 'RZIp_Z_sign');
    % isoflux_log.csv: one row per step received by muscle_nice2control.m
    f = fopen(fullfile(getenv('RUN_DIR'), 'isoflux_log.csv'), 'w');
    fprintf(f, 't,%s,psi_xp,r_xp,z_xp,zpl,ip,psi_lim\n', strjoin(compose('flux_%d', 1:8), ','));
    fclose(f);

    logger.info(sprintf('exchange period in_out_dt = %g s', in_out_dt));

    %% PCSSP modules
    obj = pcssp_KCURR_PFPO1_obj();
    obj.init;
    obj.setup;

    obj2 = RZIp_CCS_wrapper_obj();
    obj2.init;
    obj2.setup;

    obj3 = pcssp_VS_obj();
    obj3.init;
    % VS gains from FC016 instead of the module's defaults
    S = load(fullfile(getenv('CONTROLLER_PATH'), 'params/FC016_Config_VS.mat'), 'Config_VS');
    S.Config_VS.Gains.KIVS1_VS13 = -S.Config_VS.Gains.KIVS1_VS13;   % keeps VS1 = -0.1*(I_VS3U-I_VS3L)/2 with the VS3 polarity of controller_input_preprocess.m
    fp = ccs_vs_fp(obj3, S.Config_VS);
    if isprop(obj3, 'ddHdl') && ~isempty(obj3.ddHdl) && ismethod(obj3.ddHdl, 'updateField')
        % scdds-core 6b7e482 (pcssp-nightly merge_IGZ_PSC): update_nominal_param_value calls ddHdl.updateValue,
        % absent from SCDDSclass_ddHdl (renamed updateField, SCDDSclass_ddHdl.m:189-230; SCDDSclass_algo.m:1023-1026)
        obj3.ddHdl.updateField('VS_fp', fp);
    else
        obj3.update_nominal_param_value('VS_fp', fp);
    end
    fprintf('VS gains from FC016_Config_VS.mat (KZ_VS1 = %g)\n', S.Config_VS.Gains.KZ_VS1);
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

    % pcssp-nightly framework: the RZIp wrapper needs 'configurationSettings' in the base workspace
    SCDconf_setConf('pcssp_Simulation', 'configurations_container_pcssp.sldd');

    % data dictionary of the top model: links the modules' dictionaries and the base workspace
    top_dd_file = fullfile(fileparts(which([controller_model '.slx'])), [controller_model '.sldd']);
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
    set_param(0, 'ErrorIfLoadNewModel', 'off');   % pcssp-nightly PSC.slx (in the model) is saved by a newer MATLAB
    load_system(controller_model);
    set_param(controller_model, 'DataDictionary', [controller_model '.sldd']);
    if psc_enabled
        % the PSC block (Subsystem Reference to PSC) gets its four files
        psc_blk = find_system(controller_model, 'LookUnderMasks', 'all', 'ReferencedSubsystem', 'PSC');
        if isempty(psc_blk)
            error('psc_enabled = 1 but the model has no PSC block (Subsystem Reference to PSC)');
        end
        psc_setup_block(psc_blk{1}, psc_config_dir);
        logger.info(sprintf('PSC configured from %s', psc_config_dir));
    end
    if mcls_enabled
        % MCLS log (mcls_log_row.m; columns = MCLS_mux order of the model, then the NAlarms alarms and the
        % NEnablingConditions enabling conditions)
        mcls_csv = fullfile(getenv('RUN_DIR'), 'mcls_log.csv');
        if exist(mcls_csv, 'file'), delete(mcls_csv); end
        f = fopen(mcls_csv, 'w');
        hdr = {'t_abs','t_sim','ControlModeIndex','ShapeIpControlMode','IpControlMode','VSControlMode','SCIpScaling', ...
            'VSIpScaling','SNUControl','CurrentLimitAvoidance','VS3_kick_volt_on','RefSmoothTrans','HL_contr_on', ...
            'LH_contr_on','FWHLP_contr_on','EmShutDown_contr_on','ForceControlMode','Ipl_est_pcs','mcls_time'};
        for k = 1:NAlarms, hdr{end+1} = sprintf('alarm_%d', k); end %#ok<AGROW>
        for k = 1:NEnablingConditions, hdr{end+1} = sprintf('cond_%d', k); end %#ok<AGROW>
        fprintf(f, '%s\n', strjoin(hdr, ','));
        fclose(f);
    end

    %% simulation
    in = Simulink.SimulationInput(controller_model);
    in = in.setModelParameter('StartTime', '0', 'StopTime', num2str(t_max - t_start, 12));
    in = in.setModelParameter('SaveOutput', 'on');

    if DEBUG_LOG
        % header of simulink_log.csv: the inputs of the logger Mux, in its order, with their widths
        csv_file = fullfile(getenv('RUN_DIR'), 'simulink_log.csv');
        if exist(csv_file, 'file'), delete(csv_file); end
        sig = {
            'KCURR_CSPF_ctrl_e', 11;
            'KCURR_Ip_ctrl_e', 1;
            'KCURR_residual_ctrl_e', 11;
            'KCURR_actual_ref', 11;
            'RZIp_CSPF_curr_cmd', 11;
            'RZIp_VS1_cmd', 1;
            'VS_VS1_cmd', 1;
            'VS_VS3_cmd', 1;
            'Shape_CSPF_curr_cmd', 11;
            'Shape_VS_decoupling', 11;
            'Output_total', 14;
            'CSPF_curr_ref', 11;
            'Zdot', 1;
            'Ip_ref', 1;
            'Z_ref', 1;
            'R_ref', 1;
            'ip', 1;
            'zpl', 1;
            'gaps', numel(GAP_LIST);
            'gaps_ref', numel(GAP_LIST);
            'rxp', 1;
            'zxp', 1;
            'rxp_ref', 1;
            'zxp_ref', 1;
            'psc_segment', 1;
            'psc_ip_too_high', 1;
            'psc_end_of_flux', 1;
            'psc_z_excursion', 1;

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

    fprintf('Start closed loop\n')
    tic;
    logs = sim(in);
    close_system(controller_model, 0);
    simulation_time = toc;
    plasma_duration = t_max - t_start;
    fprintf(['\nControl over! ' num2str(simulation_time) 's of simulation for ' num2str(plasma_duration) 's of plasma.\n']);
end
instance.reuse_instance();
