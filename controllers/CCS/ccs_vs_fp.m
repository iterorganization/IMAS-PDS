function fp = ccs_vs_fp(obj, Config_VS)
% Fixed parameters of the PCSSP VS module from a Config_VS struct (continuous-time
% A/B/C/D, as Config_VS_structure), processed as pcssp_VS_loadfp does, except that
% KZ_VS1 is taken from Config_VS instead of being forced to 0.001.
fp = Config_VS;
fp.np = 1;
fp.timing = obj.gettiming;
fp.Ts = obj.gettiming.dt;
for k = 1:numel(fp.Gains)
    for c = {'VS1', 'VS13', 'VS3'}
        g = fp.Gains(k);
        sd = c2d(ss(g.(['A' c{1}]), g.(['B' c{1}]), g.(['C' c{1}]), g.(['D' c{1}])), fp.Ts, 'Tustin');
        fp.Gains(k).(['A' c{1}]) = sd.A;
        fp.Gains(k).(['B' c{1}]) = sd.B;
        fp.Gains(k).(['C' c{1}]) = sd.C;
        fp.Gains(k).(['D' c{1}]) = sd.D;
    end
end
end
