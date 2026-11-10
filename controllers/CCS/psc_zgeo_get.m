function z = psc_zgeo_get()
% PSC-4: plasma vertical position for the PSC input z_meas = NICE boundary.geometric_axis.z of the
% last accepted measurement (global psc_zgeo, set in muscle_nice2control.m); 0 before the first one.
global psc_zgeo
if isempty(psc_zgeo)
    z = 0;
else
    z = double(psc_zgeo(1));
end
end
