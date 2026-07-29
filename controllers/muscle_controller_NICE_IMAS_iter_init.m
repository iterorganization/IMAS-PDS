%% muscle controller initialization script. 
% 
% based on work of R. Nouailletas, T. Ravensbergen et M. Schneider, G. Gros

% This script initializes MUSCLE3 (logging, ports),
% initializes the controller params, and then launches a simulation.
% The controller receives a line_avg_density via MUSCLE3, and fires a
% pellet when the integral of the requested particle flow is larger than
% the size of a single pellet

fprintf('Controller Initialization\n')

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
ports{py.getattr(@py.ymmsl.Operator,"F_INIT")} = py.list({"equilibrium_in_f", "pf_active_in_f"});
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

while instance.reuse_instance()
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

    t_start = equilibrium.time(1);
    t_max = equilibrium.time(end);

    %% call simulink model inits
    reference_current=[];
    coils_resistance=[];
    for i=1:length(pf_active.coil)
        reference_current=[reference_current, pf_active.coil{i}.current.data];
        coils_resistance=[coils_resistance; pf_active.coil{i}.resistance];
    end
    reference_current=reference_current;
    coils_resistance=coils_resistance';

    reference_current_ts = timeseries(reference_current,equilibrium.time)
    %Init Simulink object

    % Ipl_ref/Rpl_ref/Zpl_ref track the F_INIT equilibrium (the un-controlled
    % target trajectory) over the whole run, same as CSPF_curr_ref above --
    % fed to the model via FromWorkspace blocks (not Constant), so they vary
    % over the simulation instead of pinning to a single scalar.
    n_slices = length(equilibrium.time_slice);
    ip_ref = zeros(1,n_slices);
    rgeo_ref = zeros(1,n_slices);
    zgeo_ref = zeros(1,n_slices);
    for i=1:n_slices
        ip_ref(i) = abs(equilibrium.time_slice{i}.global_quantities.ip);
        rgeo_ref(i) = equilibrium.time_slice{i}.boundary.geometric_axis.r;
        zgeo_ref(i) = equilibrium.time_slice{i}.boundary.geometric_axis.z;
    end

    enable_KCURR=1;
    IpControlMode_KCURR=0;
    schedulingVar_KCURR=0; %Ip

    Ipl_ref = timeseries(ip_ref,equilibrium.time);
    CSPF_curr_ref= reference_current_ts;
    CSPF_volt_cmd_FF=zeros(11,1); %take scenario to smooth this out

    enable_RZIp=1;
    IpControlMode_RZIp=0;
    schedulingVar_RZIp=0; %Ip
    schedulingVar_RZIp =[50, 1, 1.2]'; %[50, 1, 1.2]'

    Rpl_ref = timeseries(rgeo_ref,equilibrium.time);
    Zpl_ref = timeseries(zgeo_ref,equilibrium.time);

    %%  Simulink controller

    obj = pcssp_KCURR_PFPO1_obj;
    obj.init;
    obj.setup;

    obj2 = pcssp_RZIp_CCS_obj;
    obj2.init;
    obj2.setup;

    %% create Reference for Simulink
    in = Simulink.SimulationInput('pcssp_KCURR_RZIp_MUSCLE3');
    in = in.setModelParameter('StartTime',num2str(t_start),'StopTime',num2str(t_max));
    in = in.setModelParameter('SaveOutput', 'on');

    fprintf('Start closed loop\n')
    tic;
    logs = sim(in);
    close_system('pcssp_KCURR_RZIp_MUSCLE3',0);
    simulation_time=toc;
    plasma_duration=t_max-t_start;

    fprintf(['\nControl over! ' num2str(simulation_time) 's of simulation for ' num2str(plasma_duration) 's of plasma.\n']);
end
