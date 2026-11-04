function [Icspf,Ivs3,rpl,zpl,zdot,ip,gaps,li3,schedulingVar_RZIp] = controller_input_preprocess(coil_currents,rpl,zpl,ip,gaps,li3,schedulingVar_RZIp,t)
% Turns the plant measurements into the controller inputs:
% - Icspf: the 11 CS/PF circuit currents, CS1 = mean of CS1U and CS1L;
% - Ivs3: the VS3 circuit current, (I_VS3U - I_VS3L)/2 (anti-series pair);
% - zdot: vertical velocity. The plant's own value when it gives one (current_centre.velocity_z,
%   set by muscle_nice2control in the global zdot_meas), else the backward difference of
%   zpl. Optional noise (zdot_disturbance) and low pass 1/(tau*s + 1) by Tustin at the actual
%   time step (zdot_filter, tau = 7.5 ms). The first call returns 0; a call with the same or
%   an earlier time holds the previous value.

global zdot_meas
persistent last_t last_zpl last_zdot last_zdot_in
tau = 0.0075;

coil_currents = coil_currents(:);
cs1mean = (coil_currents(3) + coil_currents(4))/2;
Icspf = [coil_currents(1:2); cs1mean; coil_currents(5:12)];
Ivs3 = 0.5*(coil_currents(13) - coil_currents(14));

if isempty(last_t)
    zdot_in = 0;      % derivative + noise
    zdot = 0;         % controller input
else
    dt = t - last_t;
    if dt > 0
        if ~isempty(zdot_meas) && ~isnan(zdot_meas)
            zdot_in = zdot_meas;                 % velocity given by the plant
        else
            zdot_in = (zpl - last_zpl)/dt;       % backward difference
        end
        if evalin('base','zdot_disturbance')
            c = -0.6; % Lower bound
            d = 0.6;  % Upper bound
            noise = sqrt(3)*(c + (d - c)*rand(1))*sqrt(0.0005/dt); %rms = 0.6m/s at dt = 0.5ms
            zdot_in = zdot_in + noise;
        end
        if evalin('base','zdot_filter')                 
            a = (2*tau - dt)/(2*tau + dt);
            b = dt/(2*tau + dt);
            zdot = a*last_zdot + b*(zdot_in + last_zdot_in);
        else
            zdot = zdot_in;
        end
    else
        zdot_in = last_zdot_in;
        zdot = last_zdot;
    end
end

last_t = t;
last_zpl = zpl;
last_zdot_in = zdot_in;
last_zdot = zdot;

if abs(ip) <= 100
    error("plasma current is almost 0");
end
