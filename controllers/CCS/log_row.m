function log_row(t, u)
% Appends one line [t, u] to simulink_log.csv in the run directory (the header is written by the init).
% t is the Simulink time: t_offset (init) turns it into the plasma time (it is not 0 with the PSC).
persistent t_offset
if isempty(t_offset)
    t_offset = evalin('base', 't_offset');
end
f = fopen(fullfile(getenv('RUN_DIR'), 'simulink_log.csv'), 'a');
if f < 0, return; end
fprintf(f, '%.6f', t + t_offset);
fprintf(f, ',%.9g', u(:));
fprintf(f, '\n');
fclose(f);
end
