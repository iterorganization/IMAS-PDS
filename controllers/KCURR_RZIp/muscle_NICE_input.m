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

resistances= [0.0005 0.0005 0.0005 0.0005 0.0005 0.0005 0.0005 0.0005 0.0005 0.0005 0.0005 0.0005 0.0057 0.00791];

% KCURR_PFPO1's CSPF vector is 11-wide, sorted CS3U CS2U CS1 CS2L CS3L
% P1..P6, with CS1U/CS1L ganged into a single "CS1" circuit (see
% pcssp_KCURR_PFPO1_obj.m). pf_active carries CS1U/CS1L as separate coils
% (14 total: 6 CS + 6 PF + 2 VS), so expand back onto the 14 physical
% coils, duplicating the CS1 voltage onto both CS1U and CS1L.
if numel(voltage) ~= 11
    error('muscle_NICE_input:unexpectedVoltageWidth', ...
        'expected the 11-wide CSPF voltage command, got %s', mat2str(size(voltage)));
end
cspf_to_coil = [1 2 3 3 4 5 6 7 8 9 10 11];
voltage_full = zeros(1,14);
voltage_full(1:12) = voltage(cspf_to_coil);

% RZIp's VS voltage command isn't wired into this signal. Fall back to a
% resistive (V=IR) estimate from the last measured VS currents when
% available, otherwise leave the VS coils unforced (0V).
if numel(coil_current) >= 14 && all(~isnan(coil_current(13:14)))
    voltage_full(13:14) = resistances(13:14) .* reshape(coil_current(13:14),1,[]);
else
    voltage_full(13:14) = 0;
end
voltage = voltage_full;

voltage=max(voltage,Vmin);
voltage=min(voltage,Vmax);

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
instance.send("pf_active_out_i", msg);
