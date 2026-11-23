function test_mcls_block_standalone(repo, ccs, do_update)
% Smoke test of the MCLS integration (MCLS block in the controller wrapper with the PSC), two parts.
%
% Part 1 (no Simulink): the block script controllers/CCS/mcls/third_party/MCLS.m (chart_150 of the pcssp-iter library,
% modified in 4 lines for R2025b code generation, see PROVENANCE.md there) is called as a plain MATLAB function (its
% persistent iactualmode reset with `clear MCLS`) over t = 0:0.1:10 s with synthetic inputs, for the committed mode
% table of the case ip_story_mockup, loaded with controllers/CCS/mcls/mcls_load_table.m:
%   story       cases/input/psc/ip_story_mockup/mcls_table.yaml: Ipl_est = 15.02 MA - 0.5 MA/s * t (PCS frame),
%               ForceControlMode 0, then 3 for 7 <= t < 9 s, then 0 again: mode 1 (flattop_gaps: VS 3, Ip 1, Shape 4,
%               SCIp 1) while Ipl_est >= 13.5 MA (t <= 3.0 s), mode 2 (rampdown_position: 3/1/0/1) from the first tick
%               below 13.5 MA (t = 3.1 s), mode 3 (termination: 3/1/0/2) from t = 7 s (forced), still 3 after the
%               force returns to 0 (MCM3 lists only itself). A note line prints, for the record, the Ip-window and
%               Ipmin tests of mode 1 for an IMAS-signed Ip (-15 MA, the sign the wrapper would feed WITHOUT its
%               Gain -1): it documents why the wrapper negates Ip (printed only, not checked).
% Part 2 (Simulink, needs PCS_PATH and the module chain of ../model_build/build_mcls_controller.sh): load_system of
% controllers/CCS/pcssp_controller_and_ps_mcls.slx, print the port connections of the MCLS block (only if the optional
% debug helper mcls_print_ports.m is on the path) and of the modules it drives and, when do_update, a diagram update
% with the PSC configuration cases/input/psc/ip_story_mockup/psc_config and its mode table (as
% ../model_build/build_mcls_controller.sh calls ../model_build/build_mcls_controller_wrapper.m).
%
%   test_mcls_block_standalone(repo, ccs, do_update)
%     repo      repository root (default: four levels above this file, controllers/CCS/mcls/tests)
%     ccs       controllers/CCS folder (default <repo>/controllers/CCS); '' skips part 2
%     do_update true/false (default true)
% Needs pyyaml in the MATLAB pyenv (mcls_load_table reads YAML through Python; ../model_build/build_mcls_controller.sh sets it).
here = fileparts(mfilename('fullpath'));
if nargin < 1 || isempty(repo), repo = fullfile(here, '..', '..', '..', '..'); end
if nargin < 2, ccs = fullfile(repo, 'controllers', 'CCS'); end
if nargin < 3, do_update = true; end
mcls_dir = fullfile(repo, 'controllers', 'CCS', 'mcls');
addpath(mcls_dir, fullfile(mcls_dir, 'third_party'));
fprintf('MCLS script %s\n', which('MCLS'));
diary_dir = tempname; mkdir(diary_dir);
nfail = 0;
% ------------------------------------------------------------------ part 1: the script as a function
tv = 0:0.1:10;
% story (case ip_story_mockup)
Sx = table_struct(fullfile(repo, 'cases', 'input', 'psc', 'ip_story_mockup', 'mcls_table.yaml'), fullfile(diary_dir, 'story_diary.txt'));
% the IMAS-sign case, shown for the record (printed, not checked): with Ipl_est = -15 MA the Ip-window test of mode 1
% fails, and alarm 2 (Ipl_est < Ipmin) would fire if it were enabled
fprintf('  note: with Ipl_est = -15 MA, Ip0intervals test of mode 1 (MCLS.m:61) is %d; Ipmin test (:66) would be alarm 2 = %d\n', ...
    -15e6 >= Sx.MCMode(1).Ip0intervals, -15e6 < Sx.MCMode(1).Ipmin);
clear MCLS
ipl = 15.02e6 - 0.5e6 * tv;
force = zeros(size(tv)); force(tv >= 7 - 1e-9 & tv < 9 - 1e-9) = 3;
out = run_script(Sx, tv, ipl, force);
exp_cmi = ones(size(tv)); exp_cmi(ipl < 13.5e6) = 2; exp_cmi(tv >= 7 - 1e-9) = 3;
bad = out.cmi ~= exp_cmi;
if any(bad)
    fprintf('  FAIL story: ControlModeIndex differs at t = %s\n', mat2str(tv(bad)));
    nfail = nfail + 1;
else
    fprintf('  OK   story: mode 1 (|Ip| >= 13.5 MA) -> 2 (t = %.1f s) -> 3 (forced, t = 7 s) -> 3 (held after the force, t >= 9 s)\n', tv(find(exp_cmi == 2, 1)));
end
tab = [1 3 1 4 1; 2 3 1 0 1; 3 3 1 0 2];   % mode, VS, Ip, Shape, SCIpScaling (mcls_table.yaml of the story)
got = [out.vs; out.ip; out.shape; out.scip]';
wantt = tab(exp_cmi, 2:5);
if any(got(:) ~= wantt(:))
    fprintf('  FAIL story: VS/Ip/Shape/SCIpScaling do not follow the mode table\n'); nfail = nfail + 1;
else
    fprintf('  OK   story: VS/Ip/Shape/SCIpScaling follow the table (1: 3/1/4/1, 2: 3/1/0/1, 3: 3/1/0/2)\n');
end
fprintf('RESULT part1 %s (%d failure(s))\n', pick(nfail == 0, 'OK', 'FAIL'), nfail);
% ------------------------------------------------------------------ part 2: the wrapper
if isempty(ccs), if nfail > 0, error('test_mcls_block_standalone: %d failure(s)', nfail); end, return; end
mdl = 'pcssp_controller_and_ps_mcls';
try
    addpath(getenv('PCS_PATH')); pcssp_pcs_add_paths; addpath(ccs); cd(ccs);
    set_param(0, 'ErrorIfLoadNewModel', 'off');
    assignin('base', 'MCMode', Sx.MCMode); assignin('base', 'StartingMode', Sx.StartingMode);
    assignin('base', 'NAlarms', Sx.NAlarms); assignin('base', 'NEnablingConditions', Sx.NEnablingConditions);
    load_system(fullfile(ccs, [mdl '.slx']));
    set_param(mdl, 'DataDictionary', [mdl '.sldd']);   % created by build_mcls_controller_wrapper.m next to the model
    fprintf('loaded %s\n', which([mdl '.slx']));
    if exist('mcls_print_ports', 'file'), mcls_print_ports([mdl '/MCLS']); end   % optional debug helper, not part of the repository
    for b = {'Model', 'Model1', 'Model2', 'Model3', 'Equal4'}
        pc = get_param([mdl '/' b{1}], 'PortConnectivity');
        for k = 1:numel(pc)
            e = pc(k);
            if ~isempty(e.SrcBlock) && all(e.SrcBlock >= 0) && startsWith(get_param(e.SrcBlock, 'Name'), 'MCLS')
                fprintf('  %s in:%s <- %s/%d\n', b{1}, e.Type, get_param(e.SrcBlock, 'Name'), e.SrcPort + 1);
            end
        end
    end
    if do_update
        cfgdir = fullfile(repo, 'cases', 'input', 'psc', 'ip_story_mockup', 'psc_config');
        ws_for_update();
        for c = {'pcssp_KCURR_PFPO1_obj', 'RZIp_CCS_wrapper_obj', 'pcssp_VS_obj', 'shapeIp_CCS_obj', 'VS1_allocator_obj', 'pcssp_PowerSupplies_obj'}
            o = feval(c{1}); o.init; o.setup;
        end
        SCDconf_setConf('pcssp_Simulation', 'configurations_container_pcssp.sldd');   % as the controller init
        load_system(fullfile(ccs, [mdl '.slx']));
        psc_setup_block([mdl '/PSC'], cfgdir);   % controllers/CCS/psc_setup_block.m
        tic; set_param(mdl, 'SimulationCommand', 'update');
        fprintf('RESULT part2 update OK (%.0f s)\n', toc);
    else
        fprintf('RESULT part2 load OK (no update requested)\n');
    end
    close_system(mdl, 0);
catch ME
    fprintf('RESULT part2 FAIL %s\n', ME.message);
    for s = ME.stack(1:min(5, numel(ME.stack)))', fprintf('    at %s:%d\n', s.file, s.line); end
    nfail = nfail + 1;
end
if nfail > 0, error('test_mcls_block_standalone: %d failure(s)', nfail); end
end

function T = table_struct(yml, diaryfile)
% the four Parameter data of the block from a mode-table YAML (mcls_load_table.m)
[T.MCMode, T.StartingMode, T.NAlarms, T.NEnablingConditions, T.info] = mcls_load_table(yml, '', diaryfile);
fprintf('table %s: %d mode(s) [%s]\n', yml, numel(T.MCMode), strjoin(strtrim(T.info.MCModeNames), ', '));
end

function out = run_script(T, tv, ipl, force)
% call MCLS.m (chart_150, 33 arguments) with neutral inputs as the wrapper feeds them
n = numel(tv);
out = struct('cmi', zeros(1, n), 'vs', zeros(1, n), 'ip', zeros(1, n), 'shape', zeros(1, n), 'scip', zeros(1, n), ...
    'alarms', false(T.NAlarms, n), 'actions', zeros(5, n));
for k = 1:n
    [cmi, shape, ip, vs, scip, ~, ~, ~, kick, ~, hl, lh, fwhlp, esd, alarms, ~] = MCLS(tv(k) + 84.317598, ...
        zeros(11, 1), 0, 0, ipl(k), 6.2, 0.25, 0, 0.9, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, zeros(11, 1), force(k), ...
        T.MCMode, T.StartingMode, T.NAlarms, T.NEnablingConditions, 0, 0, 0, 0, 0, 0, 0);
    out.cmi(k) = cmi; out.vs(k) = vs; out.ip(k) = ip; out.shape(k) = shape; out.scip(k) = scip;
    out.alarms(:, k) = alarms(:); out.actions(:, k) = [kick; hl; lh; fwhlp; esd];
end
end

function s = pick(c, a, b)
if c, s = a; else, s = b; end
end

function ws_for_update()
% base-workspace values for the update: every variable the controller model reads
% (controllers/CCS/muscle_controller_NICE_IMAS_iter_init.m) plus the MCLS keys; same list as
% ../model_build/build_mcls_controller_wrapper.m mcls_define_ws
t = [0 2.6824];
w = @(n, v) assignin('base', n, v);
w('Ipl_ref', timeseries([-15.063e6 -15.063e6], t));
w('Rpl_ref', timeseries([6.1264 6.1264], t)); w('Zpl_ref', timeseries([0.5934 0.5934], t));   % current centre, as the controller init
w('Rxp_ref', timeseries([5.12 5.12], t)); w('Zxp_ref', timeseries([-3.30 -3.30], t));
w('Gaps_ref', timeseries(zeros(62, 2), t)); w('dPsi_ref', timeseries(zeros(62, 2), t)); w('CSPF_curr_ref', timeseries(zeros(2, 14), t));
w('enable_KCURR', 1); w('IpControlMode_KCURR', 1); w('schedulingVar_KCURR', 0);
w('enable_RZIp', 0); w('IpControlMode_RZIp', 0); w('RZIp_R_sign', 1); w('RZIp_Z_sign', 1); w('enable_VS', 1); w('VSControlMode', 3);
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
