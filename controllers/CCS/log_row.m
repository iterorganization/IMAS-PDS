function log_row(t, u)
    f = fopen(fullfile(getenv('RUN_DIR'), 'simulink_log.csv'), 'a');
    if f < 0, return; end
    fprintf(f, '%.6f', t);
    fprintf(f, ',%.9g', u(:));
    fprintf(f, '\n');
    fclose(f);
end