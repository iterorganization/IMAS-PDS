function muscle_NICE_input(t_cur,voltage,coil_current)
% This function receives the current simulation time and
% a voltage from simulink.

global z_cur
% retrieve instance object from base WS
instance = evalin('base','instance');
logger = evalin('base','logger');
pfa_base = evalin('base','pf_active');
ip_sign = evalin('base','ip_sign');
% back from the controller's Ip>0 frame (see muscle_controller_NICE_IMAS_iter_init)
voltage = ip_sign*voltage;
coil_current = ip_sign*coil_current;

%add min max and some check
% This is coil currents limits and not voltage !!!!!
Imax=[45000.0 45000.0 45000.0 45000.0 45000.0 45000.0 48000.0 55000.0 55000.0 55000.0 55000.0 22500.0 48000.0 60000.0];
Imin=[-45000.0 -45000.0 -45000.0 -45000.0 -45000.0 -45000.0 -48000.0 -55000.0 -55000.0 -55000.0 -55000.0 -22500.0 -48000.0 -60000.0];
% just some rapid guess from Girbov documentation not to far from reality,
% should be checked and improved.
Vmax =  2.65e3 * ones(1,14);
Vmin = -2.65e3 * ones(1,14);

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

% RZIp's VS voltage command isn't wired into this signal. NICE_VERTICAL_CONTROL=1
% enables a simple vertical-position loop on the VS coils (VS3U/VS3L, anti-series),
% built in the IDS frame so the ip_sign and NICE sign handling below applies to it.
% Experimental: on 105073 at dt=10 ms it drove Z away as is and oscillated with the
% sign flipped (2026-10-26), so it is off by default.
voltage_full(13:14) = NaN;
if strcmp(getenv('NICE_VERTICAL_CONTROL'), '1')
    voltage_full(13:14) = vertical_control_voltage(z_cur, ip_sign, Vmax(13), logger);
end
if any(isnan(voltage_full(13:14))) && numel(coil_current) >= 14 && all(~isnan(coil_current(13:14)))
    % VS loop off or no valid z: resistive (V=IR) hold of the last measured VS currents
    voltage_full(13:14) = resistances(13:14) .* reshape(coil_current(13:14),1,[]);
end
voltage = voltage_full;
% max/min below would turn NaN into Vmin
voltage(isnan(voltage)) = 0;

voltage=max(voltage,Vmin);
voltage=min(voltage,Vmax);
% NICE evo_rd stores coil currents as -I_IDS internally but applies the IDS voltage
% unflipped, so V>0 lowers I_IDS there; negate so V>0 raises I_IDS as the controller assumes.
voltage=-voltage;

pfa = ids_init('pf_active');
pfa.ids_properties.homogeneous_time = 1;
pfa.time = t_cur;
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


function v = vertical_control_voltage(z_cur, ip_sign, v_max, logger)
% IDS-frame [VS3U VS3L] voltages from a tanh loop on the geometric-axis z,
% around a slow moving average of z. NaN when z is not available.
persistent z_ref
v = [NaN NaN];
if isempty(z_cur) || isnan(z_cur) || abs(z_cur) > 1e30
    return
end
if isempty(z_ref)
    z_ref = z_cur;
else
    z_ref = 0.99 * z_ref + 0.01 * z_cur;
end
dz_max = 0.04;
dz_cor = (z_ref - z_cur) / dz_max;
v(1) = ip_sign * v_max * tanh(exp(1) * (dz_cor/5 + dz_cor^3) / 1.2);
v(2) = -v(1);
logger.info(sprintf('dz_cor = %g & V_VS3U = %g (V) with z_ref = %g (m) & z_cur = %g (m)', ...
    dz_cor, v(1), z_ref, z_cur));
