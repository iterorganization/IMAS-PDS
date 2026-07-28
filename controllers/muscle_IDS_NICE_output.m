function [coils_current,rgeo,zgeo,ip,t_out,stop_signal] = muscle_IDS_NICE_output()

% Receive the line average density package from MUSCLE3 via the instance
% py-class living in the base WS of matlab. Matlab automatically converts
% the data type into doubles for use in Simulink

% retrieve instance object from base ws
instance = evalin('base','instance');
logger = evalin('base','logger');

t_out=0;
stop_signal=0;
rgeo=0;
zgeo=0;
ip=0;
coils_current=zeros(14,1);

msg_eq = instance.receive("equilibrium_in_s");
msg_pfa = instance.receive("pf_active_in_s");

t_out = msg_eq.timestamp;
t_next = msg_eq.next_timestamp;

if isequal(t_next, py.None)
    stop_signal  = 1;
end

equilibrium_serial=uint8(msg_eq.data);
equilibrium = imas_deserialize(equilibrium_serial,'equilibrium');
ip=abs(equilibrium.time_slice{1}.global_quantities.ip);
rgeo=equilibrium.time_slice{1}.boundary.geometric_axis.r;
zgeo=equilibrium.time_slice{1}.boundary.geometric_axis.z;

pf_active_serial=uint8(msg_pfa.data);
pf_active=imas_deserialize(pf_active_serial,'pf_active');
for ii=1:length(pf_active.coil)
   coil=struct(pf_active.coil{ii});
   coils_current(ii)=coil.current.data;
end

fprintf('DEBUG muscle_IDS_NICE_output t=%g ip=%g rgeo=%g zgeo=%g\n', t_out, ip, rgeo, zgeo);
fprintf('DEBUG muscle_IDS_NICE_output coils_current=%s\n', mat2str(coils_current));
