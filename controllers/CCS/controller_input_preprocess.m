function [Icspf,Ivs3,zdot] = controller_input_preprocess(coil_currents,ip,zdot,t)
% Plant measurements -> controller inputs:
% - Icspf: the 11 CS/PF circuit currents, CS1 = mean of CS1U and CS1L;
% - Ivs3:  the VS3 circuit current, (I_VS3L - I_VS3U)/2 (anti-series pair): the polarity driven by +V3cmd after the
%          nice_signs negation (it grows with V3cmd > 0), as the VS module's KIVS3 feedback term requires;
% - zdot:  current-centre vertical velocity, with optional noise (zdot_disturbance) and
%          low-pass filter 1/(tau s + 1) (zdot_filter); both are settings read by the init.

persistent last_t last_zdot_in last_zdot
tau = 0.0075;       % [s] filter time constant

coil_currents = coil_currents(:);
Icspf = [coil_currents(1:2); (coil_currents(3) + coil_currents(4))/2; coil_currents(5:12)];
Ivs3 = (coil_currents(14) - coil_currents(13))/2;

if abs(ip) <= 100
    error('controller_input_preprocess: plasma current is almost 0');
end

% zdot: unchanged at the first call; held when the time does not advance;
% otherwise noise, then the filter discretized (Tustin) at the actual time step
if isempty(last_t)
    zdot_in = zdot;
elseif t <= last_t
    zdot_in = last_zdot_in;
    zdot = last_zdot;
else
    dt = t - last_t;
    zdot_in = zdot;
    if evalin('base','zdot_disturbance')
        zdot_in = zdot_in + 0.6*sqrt(3)*(2*rand - 1)*sqrt(0.0005/dt);   % rms 0.6 m/s at dt = 0.5 ms
    end
    if evalin('base','zdot_filter')
        a = (2*tau - dt)/(2*tau + dt);
        b = dt/(2*tau + dt);
        zdot = a*last_zdot + b*(zdot_in + last_zdot_in);
    else
        zdot = zdot_in;
    end
end
last_t = t;
last_zdot_in = zdot_in;
last_zdot = zdot;
end
