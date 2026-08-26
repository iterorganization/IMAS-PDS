function [coils_current,rgeo,zgeo,ip,t_out,stop_signal] = muscle_IDS_NICE_output()

% Receive the line average density package from MUSCLE3 via the instance
% py-class living in the base WS of matlab. Matlab automatically converts
% the data type into doubles for use in Simulink

% retrieve instance object from base ws
instance = evalin('base','instance');
logger = evalin('base','logger');

% Holds the last accepted measurement across calls, for the output_flag=-1
% case below (persists for the lifetime of the MATLAB session/model).
persistent last_coils_current last_rgeo last_zgeo last_ip last_t_out
% Set once nice_evo_rd sends its final message (next_timestamp=None). The
% Stop Simulation block this feeds only halts at the end of the current
% step, so this same function still gets called again on a later step --
% without this guard, that call tries to receive on the now-closed port and
% crashes with "Port ... was closed while trying to receive on it" instead
% of the simulation stopping cleanly (confirmed live).
persistent finished

t_out=0;
stop_signal=0;
rgeo=0;
zgeo=0;
ip=0;
coils_current=zeros(14,1);

if isequal(finished, true)
    coils_current = last_coils_current;
    rgeo = last_rgeo;
    zgeo = last_zgeo;
    ip = last_ip;
    t_out = last_t_out;
    stop_signal = 1;
    return;
end

% nice_evo_rd closes its output port directly once it reaches its own
% t_end, rather than sending one more message flagged next_timestamp=None
% -- so the receive() for that (never-coming) message throws
% "Port ... was closed while trying to receive on it" instead of the
% t_next-is-None branch below ever running. Treat that the same way: stop
% cleanly on the last accepted measurement (confirmed live).
try
    msg_eq = instance.receive("equilibrium_in_s");
    msg_pfa = instance.receive("pf_active_in_s");
catch ME
    if contains(ME.message, 'was closed while trying to receive')
        logger.warning('muscle_IDS_NICE_output: peer port closed without a next_timestamp=None sentinel, stopping cleanly');
        coils_current = last_coils_current;
        rgeo = last_rgeo;
        zgeo = last_zgeo;
        ip = last_ip;
        t_out = last_t_out;
        stop_signal = 1;
        finished = true;
        return;
    end
    rethrow(ME);
end

t_out = msg_eq.timestamp;
t_next = msg_eq.next_timestamp;
last_t_out = t_out;

if isequal(t_next, py.None)
    stop_signal  = 1;
    finished = true;
end

equilibrium_serial=uint8(msg_eq.data);
equilibrium = imas_deserialize(equilibrium_serial,'equilibrium');

pf_active_serial=uint8(msg_pfa.data);
pf_active=imas_deserialize(pf_active_serial,'pf_active');

eq_flag = double(equilibrium.code.output_flag);
pfa_flag = double(pf_active.code.output_flag);
is_stale = (~isempty(eq_flag) && eq_flag(1) == -1) || (~isempty(pfa_flag) && pfa_flag(1) == -1);

if is_stale && ~isempty(last_ip)
    logger.warning(sprintf('muscle_IDS_NICE_output: received output_flag=-1 at t=%g, holding last valid measurement', t_out));
    coils_current = last_coils_current;
    rgeo = last_rgeo;
    zgeo = last_zgeo;
    ip = last_ip;
else
    ip=abs(equilibrium.time_slice{1}.global_quantities.ip);
    rgeo=equilibrium.time_slice{1}.boundary.geometric_axis.r;
    zgeo=equilibrium.time_slice{1}.boundary.geometric_axis.z;

    for ii=1:length(pf_active.coil)
       coil=struct(pf_active.coil{ii});
       coils_current(ii)=coil.current.data;
    end

    last_coils_current = coils_current;
    last_rgeo = rgeo;
    last_zgeo = zgeo;
    last_ip = ip;
end
