function build_mcls_controller_wrapper(ccs, cfgdir, mcls_table, opts)
% Build controllers/CCS/pcssp_controller_and_ps_mcls.slx (+ a new .sldd): a COPY of the controller wrapper with the PSC,
% controllers/CCS/pcssp_controller_and_ps.slx (left untouched; the copy was first built on 2026-11-16 from the model
% of commit 95785e6), with the MCLS (Magnetic Control Local Supervisor) beside the PSC, driving the mode inputs of
% KCURR / RZIp / VS (and, behind a guard, ShapeIp) instead of the constant settings of the controller init.
% The controller init runs this model when mcls_enabled = 1 (muscle_controller_NICE_IMAS_iter_init.m).
% Design (option (b) of section 2 of the plan document docs/psps/plan_ip_waveform_segments_mcls_2026-11-14.md in the
% PDS main repository): the MCLS block copied as a MATLAB Function block, no library link.
%
%   build_mcls_controller_wrapper(ccs, cfgdir, mcls_table, opts)
%     ccs        controllers/CCS folder (source model, destination of the copy; holds mcls/)
%     cfgdir     PSC configuration folder WITH the force_control_mode output (make_mcls_psc_config.py),
%                used for the compile check (diagram update)
%     mcls_table mode-table YAML (e.g. cases/input/psc/ip_story_mockup/mcls_table.yaml), loaded with
%                controllers/CCS/mcls/mcls_load_table.m (MCMode, StartingMode, NAlarms, NEnablingConditions) into the
%                base workspace for the compile check; needs pyyaml in the MATLAB pyenv
%     opts       struct, all optional: force_from_psc (true: ForceControlMode = PSC bus field
%                psc_ref__force_control_mode; false: constant 0), sample_time ('in_out_dt'), do_update (true)
%
% MCLS block = MATLAB Function block whose script is controllers/CCS/mcls/third_party/MCLS.m, the chart_150 script of
% pcssp-iter@8b30ca4b device_lib/generic/PCSSP_iter_cc_modules.slx (block MCLS SID 9254 / MATLAB Function1 SID 9498),
% modified in 4 lines for R2025b code generation (provenance and the exact changes: third_party/PROVENANCE.md). The
% script is embedded in the model at build time; MCLS.m is not read at run time. As in the library mask
% (system_9254.xml) the arguments MCMode, StartingMode, NAlarms, NEnablingConditions are Parameter-scope data
% (base workspace, filled by the init from the mode-table YAML), so the block has 29 input and 16 output ports (library
% Ports [29, 16]). Sample time: discrete, in_out_dt (1 ms exchange tick; the pcs XPT02 case ran it at TsMCLS = 0.1 s,
% setup_MCLS_01.m:3); set as block parameter SystemSampleTime (R2025b: EMChart has no UpdateMethod).
%
% Source model blocks used (pcssp_controller_and_ps.slx, system_root.xml, SIDs read on 2026-11-16):
%   measurements (Goto tags written by MATLAB Function2 SID 2620 = preprocess -> controller_input_preprocess.m):
%   CSPF_current (Goto6 2621, out:1 Icspf 11 circuits), VS3_current (Goto12 2622, out:2), Rpl (Goto1 2155, out:3
%   = current centre r, muscle_nice2control.m:79-89), Zpl (Goto 2153, out:4 = current centre z), Ip (Goto2 2157,
%   out:6, IMAS sign), schedulingVar_VS (Goto30 2490, out:13 = li3_meas). Rxp / Zxp (Goto29 2658 / Goto24 2657,
%   out:7/8) exist but are NaN before the first X-point: NOT used yet, MCLS in:11-14 stay Constant 0.
%   KCURR errors: Ipl_ContrError_KCURR (Goto26 2400 <- Model 2143 out:4), CSPF_curr_ContrError_KCURR (Goto25 2399
%   <- out:3, 11), each through a one-tick Delay (MCLS_dly_IplErr -> in:16, MCLS_dly_CSPFErr -> in:21) that
%   breaks the algebraic loop MCLS modes -> KCURR/RZIp enables -> KCURR errors -> MCLS (job 1317173, 2026-11-15).
%   Clock 2526; PSC 2687 (Subsystem Reference) out:1 = PSC_Out_Bus (out:2 feeds the model's 'PSC output' chart).
%   mode constants replaced: Constant 2122 'IpControlMode_KCURR' -> Model 2143 (pcssp_KCURR_PFPO1) in:6;
%   Constant8 2130 'IpControlMode_RZIp' -> Model1 2145 (pcssp_RZIp_CCS) in:9; Constant6 2188 'VSControlMode'
%   -> Equal4 2296 in:1 (VS enable gate > 0, AND 2294 with enable_VS) and Model3 2198 (pcssp_VS) in:12.
%   guarded (base variable mcls_shape_enable): Constant14 2218 'ShapeIpControlMode' -> Model2 2213
%   (shapeIp_CCS) in:16; Constant13 2217 'IpControlMode' -> Model2 in:18 (both constants kept as the "guard off"
%   inputs of two Switch blocks; shapeIp_CCS compares its mode input every tick: Enabled subsystems with reset,
%   output ramped over Time2Enable = 1 s, so an MCLS output can drive in:16 at run time).
%   untouched (MCLS values logged only): Constant12 2216 'SCIpScaling' -> Model2 in:17 (coding
%   mismatch VERIFIED in shapeIp_CCS.slx system_201.xml: Multiport Switch SID 208 'Zero-based contiguous', control
%   EnableIplScaling 202, data ports 0 = Ipl_nominal 203, 1 = Ipl_ref 204, 2 = Ipl_est 205, output / Ipl_nominal
%   (Divide6 207); the controller init sets SCIpScaling = 1 = Ip_ref, whereas the MCLS table's SCIpScaling follows the
%   old-framework mask coding 0 off / 1 nominal / 2 estimated); Constant11 2212 'VSIpScaling' -> Model3 in:13.
% Dispatch (pcs XPT02 MCA_CCS, fenix_iter.slx system_8688.xml SIDs 12278/12284; mode note
% docs/psps/work_notes/magnetic_mode_variables_decoded_2026-11-04.md section 3 in the PDS main repository):
% KCURR in:6 = (IpControlMode == 1), RZIp in:9 = (IpControlMode == 2), both boolean as the constants were (job 1317139).
% Sign: chart_150 compares Ipl_est with the (positive, PCS-frame) windows Ip0intervals/f, Ipmin/Ipmax
% (MCLS.m lines 61-62, 66-67); the model's <Ip> is IMAS-signed (negative): Ipl_est = -Ip through Gain -1
% (MCLS_Ip_sign), the same convention as the model's psc_input chart (ip_ip__meas = -ip). No abs(): a sign flip
% would be visible as a window exit, not hidden.
% Clock: MCLS time = Clock + t_offset (Sum), t_offset being the controller init's base variable
% (t_offset = psc_enabled * t_start; plasma time = Simulink time + t_offset, log_row.m), so the block
% sees pulse time (66D9M3 slide 14: windows "w.r.t. discharge reference time"). No extra setting.
% Force field: MCLS in:22 ForceControlMode = PSC bus field psc_ref__force_control_mode through a
% Bus Selector on PSC/1 (opts.force_from_psc true), or Constant 0 (false). NOT a Variant Source: the model's
% Variant Sources 2691/2701 leave the PSC inactive when psc_enabled == 0, a direct Bus Selector would re-activate
% an unconfigured PSC, and an API-built Variant Source cannot be tested without MATLAB here. Hence a model built
% with force_from_psc = true REQUIRES psc_enabled = 1 (the controller init refuses mcls_enabled = 1 otherwise).
% Neutral constants (no PDS source yet): VS1_curr_meas 0, islimiter_est 0 (-> isdiverted true,
% 105073 flat-top is diverted), betapol_est 0, RXP/ZXP/RXPup/ZXPup 0, dsep_est 1 m (large), RplContrErr 0,
% ZplContrErr 0, GapContrErr 0, FluxContrErr 0, isHmode 0, isVS3Failure 0, HL/LH/FWHLP/EmShutDown cmd 0,
% TriggerControlAction 0.
% Logging: MCLS_logger (MATLAB Function) -> controllers/CCS/mcls/mcls_log_row.m -> RUN_DIR/mcls_log.csv (header by the
% init); Alarms_MCLS also goes to a root Outport (SaveOutput on in the init -> logs.yout) for a future PSC
% global monitoring (not wired into the PSC).
% Data dictionary: the source model has no .sldd; a new pcssp_controller_and_ps_mcls.sldd is created next to the
% copy the way the controller init does (EnableAccessToBaseWorkspace; the data sources pcssp_KCURR_PFPO1.sldd and
% pcssp_PowerSupplies.sldd are added in the compile check, after the module inits).
if nargin < 4, opts = struct(); end
opts = defaults(opts, struct('force_from_psc', true, 'sample_time', 'in_out_dt', 'do_update', true));
mdl0 = 'pcssp_controller_and_ps'; mdl = 'pcssp_controller_and_ps_mcls';
mcls_dir = fullfile(ccs, 'mcls');
script_file = fullfile(mcls_dir, 'third_party', 'MCLS.m');
sf = dir(script_file);
fprintf('MATLAB %s\nMCLS script %s (%d bytes)\n', version, script_file, sf.bytes);
addpath(getenv('PCS_PATH')); pcssp_pcs_add_paths; addpath(ccs); addpath(mcls_dir, fullfile(mcls_dir, 'third_party')); cd(ccs);
fprintf('PSC.slx = %s\n', which('PSC.slx'));
set_param(0, 'ErrorIfLoadNewModel', 'off');     % PSC.slx (pcssp-nightly ebf3ee0) is an R2026a file
[M.MCMode, M.StartingMode, M.NAlarms, M.NEnablingConditions, minfo] = mcls_load_table(mcls_table, '', [tempname '_mcls_diary.txt']);
assignin('base', 'MCMode', M.MCMode); assignin('base', 'StartingMode', M.StartingMode);
assignin('base', 'NAlarms', M.NAlarms); assignin('base', 'NEnablingConditions', M.NEnablingConditions);
fprintf('MCLS table %s: %d mode(s) [%s], NAlarms %d, NEnablingConditions %d\n', mcls_table, numel(M.MCMode), ...
    strjoin(strtrim(minfo.MCModeNames), ', '), M.NAlarms, M.NEnablingConditions);

load_system(fullfile(ccs, [mdl0 '.slx']));
save_system(mdl0, fullfile(ccs, [mdl '.slx']));           % in-memory model renamed; original file unchanged
% new top data dictionary (the source model has none), as muscle_controller_NICE_IMAS_iter_init.m does
dd_file = fullfile(ccs, [mdl '.sldd']);
if isfile(dd_file)
    top_dd = Simulink.data.dictionary.open(dd_file);
else
    top_dd = Simulink.data.dictionary.create(dd_file);
end
if ~top_dd.EnableAccessToBaseWorkspace
    top_dd.EnableAccessToBaseWorkspace = true;
end
if top_dd.HasUnsavedChanges, saveChanges(top_dd); end
close(top_dd);
set_param(mdl, 'DataDictionary', [mdl '.sldd']);
fprintf('top sldd %s (EnableAccessToBaseWorkspace on)\n', dd_file);
p = @(b) [mdl '/' b];
% ---- the constants replaced by the MCLS (verify before deleting)
chk(p('Constant'), 'Value', 'IpControlMode_KCURR'); chk(p('Constant8'), 'Value', 'IpControlMode_RZIp');
chk(p('Constant6'), 'Value', 'VSControlMode'); chk(p('Constant14'), 'Value', 'ShapeIpControlMode');
chk(p('Constant13'), 'Value', 'IpControlMode'); chk(p('Constant12'), 'Value', 'SCIpScaling');
chk(p('PSC'), 'ReferencedSubsystem', 'PSC');
for b = {'Constant', 'Constant8', 'Constant6', 'Constant14', 'Constant13', 'Constant12', 'Model', 'Model1', 'Model2', 'Model3', 'Equal4', 'PSC', 'Clock'}
    fprintf('SOURCE %-10s SID %s\n', b{1}, get_param(p(b{1}), 'SID'));
end
delete_line(mdl, 'Constant/1', 'Model/6');      delete_block(p('Constant'));
delete_line(mdl, 'Constant8/1', 'Model1/9');    delete_block(p('Constant8'));
delete_line(mdl, 'Constant6/1', 'Equal4/1');    delete_line(mdl, 'Constant6/1', 'Model3/12'); delete_block(p('Constant6'));
delete_line(mdl, 'Constant14/1', 'Model2/16');  % kept as "guard off" input of MCLS_shape_sw
delete_line(mdl, 'Constant13/1', 'Model2/18');  % kept as "guard off" input of MCLS_ipmode_sw
% ---- layout: below the lowest block of the source model (Clock 2526 at y 2125-2145)
x0 = -1250; y0 = 2300;
C = @(nm, val, x, y) add_block('simulink/Sources/Constant', p(nm), 'Value', val, 'Position', [x y x+70 y+20]);
F = @(nm, tag, x, y) add_block('simulink/Signal Routing/From', p(nm), 'GotoTag', tag, 'Position', [x y x+110 y+20]);
% time: Simulink clock + t_offset (base variable of the controller init) = pulse time
C('MCLS_clock_offset', 't_offset', x0, y0-40);
add_block('simulink/Math Operations/Sum', p('MCLS_time'), 'Inputs', '++', 'IconShape', 'rectangular', 'Position', [x0+150 y0-50 x0+180 y0-20]);
% measurements
F('MCLS_From_CSPF', 'CSPF_current', x0, y0);            % Icspf, 11 circuits
C('MCLS_c_vs1', '0', x0, y0+30);                        % VS1_curr_meas: not delivered by the glue
F('MCLS_From_VS3', 'VS3_current', x0, y0+60);
F('MCLS_From_Ip', 'Ip', x0, y0+90);
add_block('simulink/Math Operations/Gain', p('MCLS_Ip_sign'), 'Gain', '-1', 'Position', [x0+150 y0+85 x0+190 y0+115]);
F('MCLS_From_R', 'Rpl', x0, y0+120);                    % current centre r (this model's rpl)
F('MCLS_From_Z', 'Zpl', x0, y0+150);                    % current centre z
C('MCLS_c_islimiter', '0', x0, y0+180);
F('MCLS_From_li3', 'schedulingVar_VS', x0, y0+210);     % = li3_meas (MATLAB Function2 out:13 -> Goto30)
C('MCLS_c_betapol', '0', x0, y0+240);
C('MCLS_c_xp', '0', x0, y0+270);                        % RXP, ZXP, RXPup, ZXPup (Rxp/Zxp Gotos 2658/2657 exist, NaN before the first X-point: not used yet)
C('MCLS_c_dsep', '1', x0, y0+300);                      % dsep_est 1 m: condition 5 (dsep < dsepmin 0.05) false
F('MCLS_From_IplErr', 'Ipl_ContrError_KCURR', x0, y0+330);
add_block('simulink/Discrete/Delay', p('MCLS_dly_IplErr'), 'DelayLength', '1', 'InitialCondition', '0', 'SampleTime', char(opts.sample_time), 'Position', [x0+150 y0+325 x0+190 y0+355]);
C('MCLS_c_zero', '0', x0, y0+360);                      % Rpl/Zpl/Gap/Flux errors, flags, commands, trigger
F('MCLS_From_CSPFErr', 'CSPF_curr_ContrError_KCURR', x0, y0+390);
add_block('simulink/Discrete/Delay', p('MCLS_dly_CSPFErr'), 'DelayLength', '1', 'InitialCondition', '0', 'SampleTime', char(opts.sample_time), 'Position', [x0+150 y0+385 x0+190 y0+415]);
if opts.force_from_psc
    % force field straight from the PSC_Out_Bus (PSC/1); the model then requires psc_enabled = 1
    add_block('simulink/Signal Routing/Bus Selector', p('MCLS_force_sel'), 'OutputSignals', 'psc_ref__force_control_mode', 'Position', [x0 y0+430 x0+10 y0+470]);
else
    C('MCLS_force_sel', '0', x0, y0+430);
end
% the MCLS block
xm = x0 + 350;
add_block('simulink/User-Defined Functions/MATLAB Function', p('MCLS'), 'Position', [xm y0-60 xm+220 y0+800]);
rt = sfroot; bd = rt.find('-isa', 'Simulink.BlockDiagram', 'Name', mdl);
ch = bd.find('-isa', 'Stateflow.EMChart', 'Path', p('MCLS'));
ch.Script = fileread(script_file);   % chart_150 script, modified in 4 lines for R2025b code generation (third_party/PROVENANCE.md)
for nm = {'MCMode', 'StartingMode', 'NAlarms', 'NEnablingConditions'}
    d = ch.find('-isa', 'Stateflow.Data', 'Name', nm{1});
    d.Scope = 'Parameter';
    try, d.Tunable = false; catch, end                    % struct array: compile-time constant
end
d = ch.find('-isa', 'Stateflow.Data', 'Name', 'Alarms_MCLS'); d.Props.Array.Size = sprintf('[%d 1]', M.NAlarms);
d = ch.find('-isa', 'Stateflow.Data', 'Name', 'EnablingConditions_MCLS'); d.Props.Array.Size = sprintf('[%d 1]', M.NEnablingConditions);
% explicit data sizes (library chart_150: CSPF_curr_meas 11, scalar inputs 1, parameters 1; the model feeds
% CSPF_curr_ContrErr with KCURR out:3 (11) and GapContrErr/FluxContrErr/TriggerControlAction with a scalar 0).
% Inherited (-1) sizes made the R2025b update fail on 'MCLS/CSPF_curr_ContrErr' (job 1316995).
dd = ch.find('-isa', 'Stateflow.Data', 'Scope', 'Input');
for k = 1:numel(dd)
    d = dd(k);
    switch d.Name
        case {'CSPF_curr_meas', 'CSPF_curr_ContrErr'}, d.Props.Array.Size = '11';
        otherwise, d.Props.Array.Size = '1';
    end
end
for nm = {'StartingMode', 'NAlarms', 'NEnablingConditions'}
    d = ch.find('-isa', 'Stateflow.Data', 'Name', nm{1}); d.Props.Array.Size = '1';
end
fprintf('MCLS chart sizes set: CSPF_curr_meas/CSPF_curr_ContrErr 11, other inputs 1, parameters 1\n');
set_block_sample_time(p('MCLS'), opts.sample_time);
nin = numel(ch.find('-isa', 'Stateflow.Data', 'Scope', 'Input')); nout = numel(ch.find('-isa', 'Stateflow.Data', 'Scope', 'Output'));
fprintf('MCLS chart: %d inputs, %d outputs, %d parameters (library block: [29, 16])\n', nin, nout, numel(ch.find('-isa', 'Stateflow.Data', 'Scope', 'Parameter')));
assert(nin == 29 && nout == 16, 'MCLS chart ports differ from the library block [29, 16]');
% inputs, in the order of the function signature (parameters excluded)
L = @(s, d) add_line(mdl, s, d, 'autorouting', 'on');
L('Clock/1', 'MCLS_time/1'); L('MCLS_clock_offset/1', 'MCLS_time/2');
L('MCLS_time/1', 'MCLS/1');             % time (pulse time)
L('MCLS_From_CSPF/1', 'MCLS/2');        % CSPF_curr_meas
L('MCLS_c_vs1/1', 'MCLS/3');            % VS1_curr_meas
L('MCLS_From_VS3/1', 'MCLS/4');         % VS3_curr_meas
L('MCLS_From_Ip/1', 'MCLS_Ip_sign/1'); L('MCLS_Ip_sign/1', 'MCLS/5');   % Ipl_est = -Ip (PCS frame)
L('MCLS_From_R/1', 'MCLS/6');           % Rpl_est
L('MCLS_From_Z/1', 'MCLS/7');           % Zpl_est
L('MCLS_c_islimiter/1', 'MCLS/8');      % islimiter_est
L('MCLS_From_li3/1', 'MCLS/9');         % li3_est
L('MCLS_c_betapol/1', 'MCLS/10');       % betapol_est
for k = 11:14, L('MCLS_c_xp/1', sprintf('MCLS/%d', k)); end   % RXP_est, ZXP_est, RXPup_est, ZXPup_est
L('MCLS_c_dsep/1', 'MCLS/15');          % dsep_est
% one-tick delay on the two error inputs fed from KCURR outputs: without it the MCLS mode outputs -> KCURR/RZIp enables
% -> KCURR errors -> MCLS form an algebraic loop (job 1317173). XPT02 (fenix_iter.slx system_7353.xml) takes its error
% inputs from local Sum blocks on references/measurements, in:21 = 0 and delays Zpl_est by one tick (Delay4, 0.001 s).
L('MCLS_From_IplErr/1', 'MCLS_dly_IplErr/1'); L('MCLS_dly_IplErr/1', 'MCLS/16');     % IplContrErr (one tick late)
L('MCLS_c_zero/1', 'MCLS/17');          % RplContrErr
L('MCLS_c_zero/1', 'MCLS/18');          % ZplContrErr
L('MCLS_c_zero/1', 'MCLS/19');          % GapContrErr
L('MCLS_c_zero/1', 'MCLS/20');          % FluxContrErr
L('MCLS_From_CSPFErr/1', 'MCLS_dly_CSPFErr/1'); L('MCLS_dly_CSPFErr/1', 'MCLS/21');    % CSPF_curr_ContrErr (11, one tick late)
if opts.force_from_psc, L('PSC/1', 'MCLS_force_sel/1'); end
L('MCLS_force_sel/1', 'MCLS/22');       % ForceControlMode
for k = 23:29, L('MCLS_c_zero/1', sprintf('MCLS/%d', k)); end % isHmode, isVS3Failure, HL/LH/FWHLP/EmShutDown cmd, TriggerControlAction
% outputs: 1 ControlModeIndex 2 ShapeIpControlMode 3 IpControlMode 4 VSControlMode 5 SCIpScaling 6 VSIpScaling
% 7 SNUControl 8 CurrentLimitAvoidance 9 VS3_kick_volt_on 10 RefSmoothTrans 11 HL 12 LH 13 FWHLP 14 EmShutDown
% 15 Alarms_MCLS 16 EnablingConditions_MCLS
xd = xm + 350;
C('MCLS_c_one', '1', xd, y0+20); C('MCLS_c_two', '2', xd, y0+80);
add_block('simulink/Logic and Bit Operations/Relational Operator', p('MCLS_ip_is1'), 'Operator', '==', 'Position', [xd+120 y0 xd+150 y0+30]);
add_block('simulink/Logic and Bit Operations/Relational Operator', p('MCLS_ip_is2'), 'Operator', '==', 'Position', [xd+120 y0+60 xd+150 y0+90]);
% Ip-mode flags: boolean like Constant 2122 / Constant8 2130 of the source model (job 1317139: KCURR in:6 expects boolean)
add_block('simulink/Signal Attributes/Data Type Conversion', p('MCLS_ip_kcurr'), 'OutDataTypeStr', 'boolean', 'Position', [xd+200 y0 xd+260 y0+30]);
add_block('simulink/Signal Attributes/Data Type Conversion', p('MCLS_ip_rzip'), 'OutDataTypeStr', 'boolean', 'Position', [xd+200 y0+60 xd+260 y0+90]);
L('MCLS/3', 'MCLS_ip_is1/1'); L('MCLS_c_one/1', 'MCLS_ip_is1/2'); L('MCLS_ip_is1/1', 'MCLS_ip_kcurr/1'); L('MCLS_ip_kcurr/1', 'Model/6');
L('MCLS/3', 'MCLS_ip_is2/1'); L('MCLS_c_two/1', 'MCLS_ip_is2/2'); L('MCLS_ip_is2/1', 'MCLS_ip_rzip/1'); L('MCLS_ip_rzip/1', 'Model1/9');
L('MCLS/4', 'Equal4/1'); L('MCLS/4', 'Model3/12');                 % VSControlMode -> VS gate and pcssp_VS
% ShapeIp guard: mcls_shape_enable > 0.5 -> MCLS values, else the constants of the controller init
C('MCLS_shape_en', 'mcls_shape_enable', xd, y0+140);
add_block('simulink/Signal Routing/Switch', p('MCLS_shape_sw'), 'Criteria', 'u2 > Threshold', 'Threshold', '0.5', 'Position', [xd+200 y0+120 xd+240 y0+180]);
add_block('simulink/Signal Routing/Switch', p('MCLS_ipmode_sw'), 'Criteria', 'u2 > Threshold', 'Threshold', '0.5', 'Position', [xd+200 y0+200 xd+240 y0+260]);
L('MCLS/2', 'MCLS_shape_sw/1'); L('MCLS_shape_en/1', 'MCLS_shape_sw/2'); L('Constant14/1', 'MCLS_shape_sw/3'); L('MCLS_shape_sw/1', 'Model2/16');
L('MCLS/3', 'MCLS_ipmode_sw/1'); L('MCLS_shape_en/1', 'MCLS_ipmode_sw/2'); L('Constant13/1', 'MCLS_ipmode_sw/3'); L('MCLS_ipmode_sw/1', 'Model2/18');
% SCIpScaling (MCLS/5) stays unconnected to Model2/17 (coding mismatch, see header); logged below.
% logger: [ControlModeIndex Shape Ip VS SCIp VSIp SNU CLA kick RST HL LH FWHLP ESD force Ipl_est time], alarms, conditions
add_block('simulink/Signal Routing/Mux', p('MCLS_mux'), 'Inputs', '17', 'Position', [xd y0+300 xd+10 y0+640]);
for k = 1:14, L(sprintf('MCLS/%d', k), sprintf('MCLS_mux/%d', k)); end
L('MCLS_force_sel/1', 'MCLS_mux/15'); L('MCLS_Ip_sign/1', 'MCLS_mux/16'); L('MCLS_time/1', 'MCLS_mux/17');
add_block('simulink/User-Defined Functions/MATLAB Function', p('MCLS_logger'), 'Position', [xd+120 y0+420 xd+240 y0+500]);
lg = bd.find('-isa', 'Stateflow.EMChart', 'Path', p('MCLS_logger'));
lg.Script = strjoin({ ...
 'function y = mcls_logger(t, u, alarms, ec)'
 '% MCLS integration: one row per tick into RUN_DIR/mcls_log.csv (mcls_log_row.m, header written by the init).'
 'coder.extrinsic(''mcls_log_row'');'
 'mcls_log_row(t, u, double(alarms), double(ec));'
 'y = 0;'
 'end'}, newline);
set_block_sample_time(p('MCLS_logger'), opts.sample_time);
add_block('simulink/Sinks/Terminator', p('MCLS_term'), 'Position', [xd+300 y0+450 xd+320 y0+470]);
L('Clock/1', 'MCLS_logger/1'); L('MCLS_mux/1', 'MCLS_logger/2'); L('MCLS/15', 'MCLS_logger/3'); L('MCLS/16', 'MCLS_logger/4'); L('MCLS_logger/1', 'MCLS_term/1');
add_block('simulink/Sinks/Out1', p('Alarms_MCLS'), 'Position', [xd+120 y0+700 xd+150 y0+715]);   % root outport -> logs.yout (hook for a future PSC global monitoring)
L('MCLS/15', 'Alarms_MCLS/1');
new = {'MCLS', 'MCLS_time', 'MCLS_clock_offset', 'MCLS_From_CSPF', 'MCLS_c_vs1', 'MCLS_From_VS3', 'MCLS_From_Ip', 'MCLS_Ip_sign', ...
    'MCLS_From_R', 'MCLS_From_Z', 'MCLS_c_islimiter', 'MCLS_From_li3', 'MCLS_c_betapol', 'MCLS_c_xp', 'MCLS_c_dsep', ...
    'MCLS_From_IplErr', 'MCLS_dly_IplErr', 'MCLS_c_zero', 'MCLS_From_CSPFErr', 'MCLS_dly_CSPFErr', 'MCLS_force_sel', 'MCLS_c_one', 'MCLS_c_two', 'MCLS_ip_is1', ...
    'MCLS_ip_is2', 'MCLS_ip_kcurr', 'MCLS_ip_rzip', 'MCLS_shape_en', 'MCLS_shape_sw', 'MCLS_ipmode_sw', 'MCLS_mux', ...
    'MCLS_logger', 'MCLS_term', 'Alarms_MCLS'};
for b = new, fprintf('BLOCK %-18s SID %s\n', b{1}, get_param(p(b{1}), 'SID')); end
save_system(mdl);
fprintf('RESULT build OK %s\n', which([mdl '.slx']));
if exist('mcls_print_ports', 'file'), mcls_print_ports(p('MCLS')); end   % optional debug helper, not in the repository
if ~opts.do_update, close_system(mdl, 0); return; end
% ---- compile check with the PSC configuration of cfgdir, in the order of the controller init
diagfile = '';
try
    mcls_define_ws();
    for c = {'pcssp_KCURR_PFPO1_obj', 'RZIp_CCS_wrapper_obj', 'pcssp_VS_obj', 'shapeIp_CCS_obj', 'VS1_allocator_obj', 'pcssp_PowerSupplies_obj'}
        o = feval(c{1}); o.init; o.setup; fprintf('module %s init+setup OK\n', c{1});
    end
    SCDconf_setConf('pcssp_Simulation', 'configurations_container_pcssp.sldd');   % as muscle_controller_NICE_IMAS_iter_init.m
    top_dd = Simulink.data.dictionary.open(dd_file);
    if ~top_dd.EnableAccessToBaseWorkspace
        top_dd.EnableAccessToBaseWorkspace = true;
    end
    for dd_source = {'pcssp_KCURR_PFPO1.sldd', 'pcssp_PowerSupplies.sldd'}      % as the controller init
        if ~any(strcmp(top_dd.DataSources, dd_source{1}))
            addDataSource(top_dd, dd_source{1});
        end
    end
    fprintf('top sldd data sources: %s\n', strjoin(top_dd.DataSources', ', '));
    if top_dd.HasUnsavedChanges, saveChanges(top_dd); end
    close(top_dd);
    load_system(fullfile(ccs, [mdl '.slx']));
    set_param(mdl, 'DataDictionary', [mdl '.sldd']);
    psc_setup_block([mdl '/PSC'], cfgdir);                % controllers/CCS/psc_setup_block.m
    diagdir = fullfile(ccs, '..', '..', 'cases', 'runs', 'mcls_logs');   % repo root from controllers/CCS
    if ~isfolder(diagdir), mkdir(diagdir); end
    diagfile = fullfile(diagdir, sprintf('sldiag_update_%s.txt', getenv('SLURM_JOB_ID')));
    try, sldiagviewer.diary(diagfile); sldiagviewer.diary('on'); catch ME2, fprintf('sldiagviewer.diary unavailable: %s\n', ME2.message); diagfile = ''; end
    tic; set_param(mdl, 'SimulationCommand', 'update');
    fprintf('RESULT update OK (%.0f s)\n', toc);
    try, sldiagviewer.diary('off'); catch, end
    if exist('mcls_print_ports', 'file'), mcls_print_ports(p('MCLS')); end   % optional debug helper, not in the repository
catch ME
    fprintf('RESULT update FAIL %s\n', ME.message);
    fprintf('%s\n', ME.getReport('extended', 'hyperlinks', 'off'));
    try, sldiagviewer.diary('off'); catch, end
    if ~isempty(diagfile) && isfile(diagfile)
        txt = fileread(diagfile); fprintf('--- Diagnostic Viewer (%s, %d chars) ---\n%s\n--- end ---\n', diagfile, numel(txt), txt(1:min(end, 20000)));
    end
    for s = ME.stack(1:min(5, numel(ME.stack)))', fprintf('    at %s:%d\n', s.file, s.line); end
    if isprop(ME, 'cause'), for c = 1:numel(ME.cause), fprintf('  cause: %s\n', ME.cause{c}.message); end, end
end
close_system(mdl, 0);
end

function chk(blk, prm, want)
got = get_param(blk, prm);
assert(strcmp(got, want), 'build_mcls_controller_wrapper: %s %s = %s, expected %s (model changed?)', blk, prm, got, want);
end

function o = defaults(o, d)
for f = fieldnames(d)', if ~isfield(o, f{1}), o.(f{1}) = d.(f{1}); end, end
end

function mcls_define_ws()
% base-workspace values for the compile check: every variable the source model reads
% (set by muscle_controller_NICE_IMAS_iter_init.m) plus the MCLS keys
t = [0 2.6824];
w = @(n, v) assignin('base', n, v);
w('Ipl_ref', timeseries([-15.063e6 -15.063e6], t));
w('Rpl_ref', timeseries([6.1264 6.1264], t)); w('Zpl_ref', timeseries([0.5934 0.5934], t));   % current centre, as the controller init
w('Rxp_ref', timeseries([5.12 5.12], t)); w('Zxp_ref', timeseries([-3.30 -3.30], t));
w('Gaps_ref', timeseries(zeros(62, 2), t)); w('dPsi_ref', timeseries(zeros(62, 2), t)); w('CSPF_curr_ref', timeseries(zeros(2, 14), t));
w('enable_KCURR', 1); w('IpControlMode_KCURR', 1); w('schedulingVar_KCURR', 0);
w('enable_RZIp', 0); w('IpControlMode_RZIp', 0); w('enable_VS', 1); w('VSControlMode', 3);
w('VSIpScaling', 1); w('SchedulingVar_ShapeContr', 3); w('ShapeIpControlMode', 4); w('SCIpScaling', 1);
w('IpControlMode', 0); w('AllocatorMode', 1); w('usePSModel', 1); w('in_out_dt', 0.001);
w('zdot_disturbance', 0); w('zdot_filter', 0); w('nice_signs', 1); w('DEBUG_LOG', false);
w('t_start', 84.317598); w('t_max', 86.9986); w('psc_enabled', 1); w('t_offset', 84.317598);
w('GAP_LIST', [3 8 15 21 25 48]); w('N_GAPS', 62); w('N_FLUX', 62);
w('RfluxCTRpts', [4.362071 4.1486759 5.1894636 7.0161489 8.137644 7.0624581]);
w('ZfluxCTRpts', [-1.5 1.5492 3.2382093 2.6846939 0.62839253 -2.0424846]);
w('R_lim', 4.1053); w('Z_lim', 0.6039); w('FLUX_CTR_PLACEHOLDER', true);
w('mcls_shape_enable', 0);
end

function set_block_sample_time(blk, st)
% R2025b: Stateflow.EMChart has no UpdateMethod/SampleTime; the MATLAB Function block
% stores it as the block parameter SystemSampleTime (as in pcssp_controller_and_ps.slx,
% block CODAC_input). Fall back to SampleTime for older releases.
if ~ischar(st) && ~isstring(st), st = num2str(st); end
try
    set_param(blk, 'SystemSampleTime', char(st));
catch
    set_param(blk, 'SampleTime', char(st));
end
fprintf('%s sample time: %s\n', blk, get_param(blk, 'SystemSampleTime'));
end
