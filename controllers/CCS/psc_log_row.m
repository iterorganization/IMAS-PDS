function psc_log_row(t, u)
% PSC-4: one row per Simulink tick into RUN_DIR/psc_log.csv; t is the Simulink time (PSC clock,
% 0 at the window start), the absolute time t + psc_time_offset is written first.
persistent off
if isempty(off)
    off = evalin('base', 'psc_time_offset');
end
f = fopen(fullfile(getenv('RUN_DIR'), 'psc_log.csv'), 'a');
if f < 0, return; end
fprintf(f, '%.6f,%.6f', t + off, t);
fprintf(f, ',%.9g', u(:));
fprintf(f, '\n');
fclose(f);
end
