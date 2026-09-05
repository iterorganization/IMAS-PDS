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

% Optional tighter symmetric clamp on the commanded coil voltages (V), e.g. the ITER
% main-converter rating (~1.35 kV) instead of the coil terminal limits above. Set the
% environment variable NICE_VOLTAGE_LIMIT to enable; unset means the limits above.
% Motivation: at start-up the current loop reacts to a ~2% mismatch between NICE's
% inverse currents and the DINA references with commands at the +-45 kV limits for
% two 2 ms steps, a flux kick that threw NICE's evolutive solve into NaN (2026-09-04).
nice_voltage_limit = str2double(getenv('NICE_VOLTAGE_LIMIT'));
if ~isnan(nice_voltage_limit) && nice_voltage_limit > 0
    Vmax = min(Vmax,  nice_voltage_limit);
    Vmin = max(Vmin, -nice_voltage_limit);
end

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

% Sign convention adapter towards NICE. NICE/3.0.0.dev258's evolutive actor flips
% coil currents to its internal (Ip>0) convention but applies the received IDS
% voltages unflipped (ReadDataEvolutiveProblemWithRD: `signIc = 1`, the
% change_coil_sign branch is commented out), so the IDS current it returns moves
% opposite to the IDS voltage we send -- an inverted plant for this controller
% (confirmed on all 11 coils, 2026-09-04, shot 105084). NICE_VOLTAGE_SIGN=-1 in the
% magnetic_controller launch script compensates; set it to 1 (or unset) once NICE
% converts voltages with the same COCOS sign as currents.
nice_voltage_sign = str2double(getenv('NICE_VOLTAGE_SIGN'));
if isnan(nice_voltage_sign)
    nice_voltage_sign = 1;
end
voltage = nice_voltage_sign * voltage;

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
