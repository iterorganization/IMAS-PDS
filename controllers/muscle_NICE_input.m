function muscle_NICE_input(t_cur,voltage,coil_current)
% This function receives the current simulation time and
% a voltage from simulink.

% retrieve instance object from base WS
instance = evalin('base','instance');
logger = evalin('base','logger');
pfa_base = evalin('base','pf_active');

%add min max and some check
Vmax=[45000.0 45000.0 45000.0 45000.0 45000.0 45000.0 48000.0 55000.0 55000.0 55000.0 55000.0 22500.0 48000.0 60000.0];
Vmin=[-45000.0 -45000.0 -45000.0 -45000.0 -45000.0 -45000.0 -48000.0 -55000.0 -55000.0 -55000.0 -55000.0 -22500.0 -48000.0 -60000.0];

voltage=max(voltage,Vmin);
voltage=min(voltage,Vmax);

resistances= [0.0005 0.0005 0.0005 0.0005 0.0005 0.0005 0.0005 0.0005 0.0005 0.0005 0.0005 0.0005 0.0057 0.00791];

pfa = ids_init('pf_active');
pfa.ids_properties.homogeneous_time = 1;
pfa.time = [t_cur];
pfa.coil=ids_allocate('pf_active', 'coil', 14);
for i = 1:14
    pfa.coil{i}.element = pfa_base.coil{i}.element;
    pfa.coil{i}.resistance = resistances(i);
    pfa.coil{i}.voltage.data=voltage(i);
    pfa.coil{i}.current.data=coil_current(i);
end

pfa_serialized=imas_serialize(pfa, 'pf_active');
s = sprintf('%d ' ,uint8(pfa_serialized));
x = py.numpy.fromstring(s, py.numpy.int8, int8(-1), char(' '));
pfa_serialized=py.bytes(x);
msg =  py.libmuscle.Message(t_cur,py.None,pfa_serialized);
instance.send("pf_active_o_i", msg);
