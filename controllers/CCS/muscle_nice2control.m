function [coils_current,rpl,zpl,ip,gaps,li3,schedulingVar_RZIp,t_out,stop_signal] = muscle_nice2control()

global z_cur
% Vertical velocity given by the plant (current_centre.velocity_z), read by
% controller_input_preprocess; NaN when not available: Zdot is then the derivative of zpl
global zdot_meas

% retrieve instance object from base ws
instance = evalin('base','instance');
logger = evalin('base','logger');

% Holds the last accepted measurement across calls, for the output_flag=-1
% case below (persists for the lifetime of the MATLAB session/model).
persistent last_coils_current last_rpl last_zpl last_ip last_t_out last_gaps last_li3 last_schedulingVar_RZIp finished
persistent last_zdot_meas cc_source
% Set once nice_evo_rd sends its final message (next_timestamp=None). The
% Stop Simulation block this feeds only halts at the end of the current
% step, so this same function still gets called again on a later step --

N_GAPS=62;
li3=0;
t_out=0;
stop_signal=0;
rpl=0;
zpl=0;
ip=0;
gaps = zeros(N_GAPS,1);
coils_current=zeros(14,1);
schedulingVar_RZIp=zeros(3,1); %time,li,elongation
if isempty(last_zdot_meas)
    last_zdot_meas = NaN;
end
zdot_meas = last_zdot_meas;     % held by the early returns below

if isequal(finished, true)
    coils_current = last_coils_current;
    rpl = last_rpl;
    zpl = last_zpl;
    ip = last_ip;
    gaps = last_gaps;
    schedulingVar_RZIp = last_schedulingVar_RZIp;
    li3 = last_li3;
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
        logger.warning('muscle_nice2control: peer port closed without a next_timestamp=None sentinel, stopping cleanly');
        coils_current = last_coils_current;
        rpl = last_rpl;
        zpl = last_zpl;
        ip = last_ip;
        gaps = last_gaps;
        t_out = last_t_out;
        li3 = last_li3;
        schedulingVar_RZIp = last_schedulingVar_RZIp;
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
    logger.warning(sprintf('muscle_nice2control: received output_flag=-1 at t=%g, holding last valid measurement', t_out));
    coils_current = last_coils_current;
    rpl = last_rpl;
    zpl = last_zpl;
    ip = last_ip;
    gaps = last_gaps;
    li3 = last_li3;
    schedulingVar_RZIp = last_schedulingVar_RZIp;
else
    %NEW QUANTITIES
    ip= equilibrium.time_slice{1}.global_quantities.ip;
    gq = equilibrium.time_slice{1}.global_quantities;
    zdot_meas = NaN;
    switch evalin('base','plasma_position')
        case 'geometric_axis'
            rpl = equilibrium.time_slice{1}.boundary.geometric_axis.r;
            zpl = equilibrium.time_slice{1}.boundary.geometric_axis.z;
        case 'current_centre'
            cc = gq.current_centre;
            if is_filled(cc.r) && cc.r > 0
                rpl = cc.r;
                zpl = cc.z;
                source = 'current_centre';
                if is_filled(cc.velocity_z) && cc.velocity_z ~= 0
                    zdot_meas = cc.velocity_z;
                end
            else
                [rpl, zpl, how] = current_centre_estimate(equilibrium.time_slice{1});
                source = ['current centre from ' how];
                if isnan(zpl)
                    rpl = equilibrium.time_slice{1}.boundary.geometric_axis.r;
                    zpl = equilibrium.time_slice{1}.boundary.geometric_axis.z;
                    source = 'boundary geometric axis (no current centre, no ggd)';
                end
            end
            if ~strcmp(source, cc_source)
                logger.info(sprintf('muscle_nice2control: from t = %g, plasma position = %s', t_out, source));
                cc_source = source;
            end
        otherwise
            rpl = gq.magnetic_axis.r;
            zpl = gq.magnetic_axis.z;
    end
    last_zdot_meas = zdot_meas;

    for ii=1:length(pf_active.coil)
       coil=struct(pf_active.coil{ii});
       coils_current(ii)= coil.current.data;
    end
    li3 = equilibrium.time_slice{1}.global_quantities.li_3;
    kappa = equilibrium.time_slice{1}.boundary.elongation;
    schedulingVar_RZIp = [t_out; li3; kappa];

    last_coils_current = coils_current;
    last_rpl = rpl;
    last_zpl = zpl;
    last_ip = ip;
    last_gaps = gaps;
    last_li3 = li3;
    last_schedulingVar_RZIp = schedulingVar_RZIp;
end

z_cur = zpl;

end

function ok = is_filled(v)
ok = ~isempty(v) && isfinite(v(1)) && abs(v(1)) < 1e30;
end

