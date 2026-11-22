function log_row(t, u)
% Appends one line [t, u] to simulink_log.csv in the run directory (the header is written by the init).
% t is the Simulink time, which starts at 0: adding t_start (init) gives the plasma time.
persistent t_start
if isempty(t_start)
    t_start = evalin('base', 't_start');
end
f = fopen(fullfile(getenv('RUN_DIR'), 'simulink_log.csv'), 'a');
if f < 0, return; end
fprintf(f, '%.6f', t + t_start);
fprintf(f, ',%.9g', u(:));
fprintf(f, '\n');
fclose(f);
end
