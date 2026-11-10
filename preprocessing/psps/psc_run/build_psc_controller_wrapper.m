function build_psc_controller_wrapper(ccs, cfgdir)
% PSC-4: build controllers/CCS/pcssp_controller_and_ps_psc.slx, a COPY of the student's fork
% wrapper pcssp_controller_and_ps.slx (left untouched), with the real PSC in the Ip path:
%   - Ip_FromWS (FromWorkspace Ipl_ref, SID 2149) and its line to Goto8 <Ip_ref> (SID 2180) deleted;
%   - PSC = Subsystem Reference to pcssp-nightly src/psc/PSC.slx;
%   - PSC_input (MATLAB Function): PSC_In_Bus from the glue measurements
%       ip_ip__meas = -Ip (From <Ip>, IMAS sign -> PCS frame), plasma_state__exist_diag = 1,
%       z_meas = boundary.geometric_axis.z (global psc_zgeo set in muscle_nice2control),
%       cs_margin = min over the 6 CS coils of (45 kA - |I_coil|) (CODAC_input out:1, per turn);
%   - PSC_Out_Bus -> Bus Selector psc_ref__Ipl_ref -> Gain -1 (PCS frame -> IMAS sign) -> Goto8 <Ip_ref>
%     (-> KCURR in:4 via From13, unchanged);
%   - PSC_logger (MATLAB Function): Clock, PSC_Out_Bus, PSC_Int_Bus, PSC_In_Bus -> psc_log_row.m.
% Then a diagram update with the cfgdir PSC configuration (compile check).
% Run through the PDS controller module chain (MATLAB 2025b-r1),
% PCS_PATH = local_installs/pcs-nightly (pds_setup.sh, INSTALL_PCS_NIGHTLY).
mdl0 = 'pcssp_controller_and_ps'; mdl = 'pcssp_controller_and_ps_psc';
fprintf('MATLAB %s\n', version);
addpath(getenv('PCS_PATH')); pcssp_pcs_add_paths; addpath(ccs); cd(ccs);
fprintf('PSC.slx = %s\nPSCSysObj = %s\n', which('PSC.slx'), which('PSCSysObj'));
% pcssp-nightly ebf3ee0 src/psc/PSC.slx was saved by R2026a: allow loading it in R2025b (session preference)
set_param(0, 'ErrorIfLoadNewModel', 'off');
copyfile(fullfile(ccs, [mdl0 '.sldd']), fullfile(ccs, [mdl '.sldd']));
load_system(fullfile(ccs, [mdl0 '.slx']));
save_system(mdl0, fullfile(ccs, [mdl '.slx']));           % in-memory model renamed; original file unchanged
set_param(mdl, 'DataDictionary', [mdl '.sldd']);
p = @(b) [mdl '/' b];
pos = get_param(p('Ip_FromWS'), 'Position'); g8 = get_param(p('Goto8'), 'Position');
fprintf('deleted: Ip_FromWS SID %s (VariableName %s) -> Goto8 SID %s\n', get_param(p('Ip_FromWS'), 'SID'), ...
    get_param(p('Ip_FromWS'), 'VariableName'), get_param(p('Goto8'), 'SID'));
delete_line(mdl, 'Ip_FromWS/1', 'Goto8/1'); delete_block(p('Ip_FromWS'));
x = pos(1) - 900; y = pos(2) - 200;
add_block('simulink/Signal Routing/From', p('PSC_From_Ip'), 'GotoTag', 'Ip', 'Position', [x y x+60 y+20]);
add_block('simulink/User-Defined Functions/MATLAB Function', p('PSC_input'), 'Position', [x+150 y-10 x+260 y+50]);
add_block('simulink/Ports & Subsystems/Subsystem Reference', p('PSC'), 'Position', [x+350 y-10 x+500 y+80]);
set_param(p('PSC'), 'ReferencedSubsystem', 'PSC');
add_block('simulink/Signal Routing/Bus Selector', p('PSC_out_sel'), 'Position', [x+600 y-10 x+610 y+30]);
set_param(p('PSC_out_sel'), 'OutputSignals', 'psc_ref__Ipl_ref');
add_block('simulink/Math Operations/Gain', p('PSC_Ip_sign'), 'Gain', '-1', 'Position', [x+680 y-5 x+720 y+25]);
add_block('simulink/User-Defined Functions/MATLAB Function', p('PSC_logger'), 'Position', [x+600 y+100 x+720 y+180]);
add_block('simulink/Sinks/Terminator', p('PSC_term'), 'Position', [x+780 y+130 x+800 y+150]);
set_param(p('Goto8'), 'Position', [x+780 y-5 x+780+(g8(3)-g8(1)) y-5+(g8(4)-g8(2))]);
rt = sfroot; bd = rt.find('-isa', 'Simulink.BlockDiagram', 'Name', mdl);
ch = bd.find('-isa', 'Stateflow.EMChart', 'Path', p('PSC_input'));
ch.Script = strjoin({ ...
 'function inb = psc_input(ip, coils)'
 '% PSC-4: PSC_In_Bus from the measurements of the glue (PCS frame, SI units).'
 'coder.extrinsic(''psc_zgeo_get'');'
 'z = 0;'
 'z = psc_zgeo_get();'
 'inb.ip_ip__meas.value = -ip;'
 'inb.ip_ip__meas.quality = PcsQuality_t.kGood;'
 'inb.ip_ip__meas.activity = PcsActivity_t.kRunning;'
 'inb.plasma_state__exist_diag.value = 1;'
 'inb.plasma_state__exist_diag.quality = PcsQuality_t.kGood;'
 'inb.plasma_state__exist_diag.activity = PcsActivity_t.kRunning;'
 'inb.z_meas.value = z;'
 'inb.z_meas.quality = PcsQuality_t.kGood;'
 'inb.z_meas.activity = PcsActivity_t.kRunning;'
 'inb.cs_margin.value = min(45e3 - abs(coils(1:6)));'
 'inb.cs_margin.quality = PcsQuality_t.kGood;'
 'inb.cs_margin.activity = PcsActivity_t.kRunning;'
 'end'}, newline);
d = ch.find('-isa', 'Stateflow.Data', 'Name', 'inb'); d.DataType = 'Bus: PSC_In_Bus';
lg = bd.find('-isa', 'Stateflow.EMChart', 'Path', p('PSC_logger'));
lg.Script = strjoin({ ...
 'function y = psc_logger(t, outb, intb, inb)'
 '% PSC-4: one row per tick into RUN_DIR/psc_log.csv (psc_log_row.m, header written by the glue).'
 'coder.extrinsic(''psc_log_row'');'
 'u = [outb.psc_ref__Ipl_ref; double(intb.psc_ref__current_segment); double(intb.psc_ref_lastModSegment); ...'
 '     double(intb.psc_OldModSegment); intb.psc_segmentTime; intb.psc_simTime; intb.psc_lastTimeDiff; ...'
 '     double(intb.glb_ps__run_plasma); double(intb.glb__PulseDone); double(intb.glb_ps__ip_too_high); ...'
 '     double(intb.glb_ps__end_of_flux); double(intb.glb_ps__z_excursion); ...'
 '     inb.ip_ip__meas.value; inb.z_meas.value; inb.cs_margin.value];'
 'psc_log_row(t, u);'
 'y = 0;'
 'end'}, newline);
for nm = {'outb', 'PSC_Out_Bus'; 'intb', 'PSC_Int_Bus'; 'inb', 'PSC_In_Bus'}'
    d = lg.find('-isa', 'Stateflow.Data', 'Name', nm{1}); d.DataType = ['Bus: ' nm{2}];
end
add_line(mdl, 'PSC_From_Ip/1', 'PSC_input/1', 'autorouting', 'on');
add_line(mdl, 'CODAC_input/1', 'PSC_input/2', 'autorouting', 'on');
add_line(mdl, 'PSC_input/1', 'PSC/1', 'autorouting', 'on');
add_line(mdl, 'PSC/1', 'PSC_out_sel/1', 'autorouting', 'on');
add_line(mdl, 'PSC_out_sel/1', 'PSC_Ip_sign/1', 'autorouting', 'on');
add_line(mdl, 'PSC_Ip_sign/1', 'Goto8/1', 'autorouting', 'on');
add_line(mdl, 'Clock/1', 'PSC_logger/1', 'autorouting', 'on');
add_line(mdl, 'PSC/1', 'PSC_logger/2', 'autorouting', 'on');
add_line(mdl, 'PSC/2', 'PSC_logger/3', 'autorouting', 'on');
add_line(mdl, 'PSC_input/1', 'PSC_logger/4', 'autorouting', 'on');
add_line(mdl, 'PSC_logger/1', 'PSC_term/1', 'autorouting', 'on');
for b = {'PSC_From_Ip', 'PSC_input', 'PSC', 'PSC_out_sel', 'PSC_Ip_sign', 'PSC_logger', 'PSC_term', 'Goto8', 'Clock', 'CODAC_input'}
    fprintf('BLOCK %-12s SID %s\n', b{1}, get_param(p(b{1}), 'SID'));
end
save_system(mdl);
fprintf('RESULT build OK %s\n', which([mdl '.slx']));
% compile check with the PSC configuration of cfgdir
try
    psc4_define_ws();
    % module inits as muscle_controller_NICE_IMAS_iter_init.m:186-208 (they write the module .sldd files)
    for c = {'pcssp_KCURR_PFPO1_obj', 'RZIp_CCS_wrapper_obj', 'pcssp_VS_obj', 'shapeIp_CCS_obj', 'VS1_allocator_obj', 'pcssp_PowerSupplies_obj'}
        o = feval(c{1}); o.init; o.setup; fprintf('module %s init+setup OK\n', c{1});
    end
    psc_framework_conf();
    top_dd = Simulink.data.dictionary.open(fullfile(ccs, [mdl '.sldd']));
    fprintf('top sldd data sources: %s\n', strjoin(top_dd.DataSources', ', ')); close(top_dd);
    load_system(fullfile(ccs, [mdl '.slx']));
    psc_setup_block(mdl, cfgdir);
    tic; set_param(mdl, 'SimulationCommand', 'update');
    fprintf('RESULT update OK (%.0f s)\n', toc);
catch ME
    fprintf('RESULT update FAIL %s\n', ME.message);
    for s = ME.stack(1:min(5, numel(ME.stack)))', fprintf('    at %s:%d\n', s.file, s.line); end
    if isprop(ME, 'cause'), for c = 1:numel(ME.cause), fprintf('  cause: %s\n', ME.cause{c}.message); end, end
end
close_system(mdl, 0);
end

function psc4_define_ws()
t = [0 2.6824];
w = @(n, v) assignin('base', n, v);
w('Ipl_ref', timeseries([-15.063e6 -15.063e6], t));
w('Rpl_ref', timeseries([6.2016 6.2016], t)); w('Zpl_ref', timeseries([0.2487 0.2487], t));
w('Gaps_ref', timeseries(zeros(62, 2), t)); w('CSPF_curr_ref', timeseries(zeros(2, 14), t));
w('enable_KCURR', 1); w('IpControlMode_KCURR', 1); w('schedulingVar_KCURR', 0);
w('enable_RZIp', 0); w('IpControlMode_RZIp', 0); w('enable_VS', 1); w('VSControlMode', 3);
w('VSIpScaling', 1); w('SchedulingVar_GapContr', 0); w('ShapeIpControlMode', 0); w('SCIpScaling', 0);
w('IpControlMode', 0); w('AllocatorMode', 1); w('usePSModel', 1); w('in_out_dt', 0.001);
w('zdot_disturbance', 0); w('zdot_filter', 0); w('nice_signs', 1); w('DEBUG_LOG', false);
w('t_start', 0); w('t_max', 2.6824);
end
