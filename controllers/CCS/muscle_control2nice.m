function muscle_control2nice(t_cur,voltage)
% This function receives the current simulation time and
% a voltage from simulink.

% retrieve instance object from base WS
instance = evalin('base','instance');
logger = evalin('base','logger');

if numel(voltage) ~= 14
    error('muscle_control2nice:unexpectedVoltageWidth', ...
        'expected the 14-wide voltage command, got %s', mat2str(size(voltage)));
end

supply_names = {'CS3U','CS2U','CS1U','CS1L','CS2L','CS3L','PF1','PF2','PF3','PF4','PF5','VS1','PF6','VS3'};
coil_names = {'CS3U','CS2U','CS1U','CS1L','CS2L','CS3L','PF1','PF2','PF3','PF4','PF5','PF6','VS3U','VS3L'};
pfa = ids_init('pf_active');
pfa.ids_properties.homogeneous_time = 1;
pfa.time = t_cur;
pfa.supply = ids_allocate('pf_active', 'supply', 14);
pfa.coil = ids_allocate('pf_active', 'coil', 14);
for i = 1:14
    pfa.supply{i}.name = supply_names{i};
    pfa.supply{i}.voltage.data = voltage(i);
    pfa.coil{i}.name = coil_names{i};
end

pfa_serialized=imas_serialize(pfa, 'pf_active');
s = sprintf('%d ' ,uint8(pfa_serialized));
x = py.numpy.fromstring(s, py.numpy.int8, int8(-1), char(' '));
pfa_serialized=py.bytes(x);
msg =  py.libmuscle.Message(t_cur,py.None,pfa_serialized);
instance.send("pf_active_out_i", msg);
