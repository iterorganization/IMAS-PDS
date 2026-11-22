function mcls_log_row(t, u, alarms, ec)
% MCLS integration: one row per MCLS tick into RUN_DIR/mcls_log.csv (header written by
% controllers/CCS/muscle_controller_NICE_IMAS_iter_init.m when mcls_enabled = 1). Called through coder.extrinsic by the
% MATLAB Function block MCLS_logger of controllers/CCS/pcssp_controller_and_ps_mcls.slx. t = Simulink time (0 at the
% window start); the first column is the absolute time t + t_offset (base variable set by the init; as log_row.m).
% u = the 17-vector of the model's MCLS_mux: [ControlModeIndex ShapeIpControlMode IpControlMode VSControlMode SCIpScaling
% VSIpScaling SNUControl CurrentLimitAvoidance VS3_kick_volt_on RefSmoothTrans HL_contr_on LH_contr_on FWHLP_contr_on
% EmShutDown_contr_on ForceControlMode Ipl_est(PCS frame) mcls_time]; alarms = Alarms_MCLS (9);
% ec = EnablingConditions_MCLS (12).
persistent off
if isempty(off)
    off = evalin('base', 't_offset');
end
f = fopen(fullfile(getenv('RUN_DIR'), 'mcls_log.csv'), 'a');
if f < 0, return; end
fprintf(f, '%.6f,%.6f', t + off, t);
fprintf(f, ',%.9g', u(:));
fprintf(f, ',%d', round(alarms(:)));
fprintf(f, ',%d', round(ec(:)));
fprintf(f, '\n');
fclose(f);
end
