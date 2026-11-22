function ok = mcls_check_yaml_vs_mat(table_yaml, old_mat, defaults_yaml)
%MCLS_CHECK_YAML_VS_MAT  Check that a mode-table YAML gives the same MCLS parameters as a .mat of the former setup scripts.
%
%   ok = mcls_check_yaml_vs_mat(table_yaml, old_mat)
%   ok = mcls_check_yaml_vs_mat(table_yaml, old_mat, defaults_yaml)
%
% Loads the table through mcls_load_table.m (YAML route, defaults YAML default: mcls_library_defaults.yaml) and the
% old .mat (variables MCMode, StartingMode, NAlarms, NEnablingConditions, MCModeNames, AlarmNames,
% EnablingConditionNames, MCModeUser, as written by the former setup scripts), then compares field by field with
% isequaln plus class and size, and the MCMode field order. Prints every difference (the first one marked FIRST) and
% stops with an error if there is any. Needs the controller's pyenv (pyyaml), e.g. from the build environment of
% controllers/CCS/mcls/model_build/build_mcls_controller.sh.
%
% Example (from the repository root; the old .mat file is an untracked study file):
%   addpath controllers/CCS/mcls
%   mcls_check_yaml_vs_mat('cases/input/psc/ip_story_mockup/mcls_table.yaml', ...
%       'cases/input/psc/F_story/_v1_2026-11-16/Config_MCLS_pds_story.mat')
if nargin < 3, defaults_yaml = ''; end
[MCMode, StartingMode, NAlarms, NEnablingConditions, info] = ...
    mcls_load_table(table_yaml, defaults_yaml, [tempname '_mcls_check_diary.txt']);
O = load(old_mat);
nd = 0;
    function report(msg)
        nd = nd + 1;
        if nd == 1, fprintf('  FIRST DIFFERENCE: %s\n', msg); else, fprintf('  difference: %s\n', msg); end
    end
    function cmp(name, a, b)
        if ~strcmp(class(a), class(b))
            report(sprintf('%s: class %s (YAML) vs %s (mat)', name, class(a), class(b)));
        elseif ~isequal(size(a), size(b))
            report(sprintf('%s: size %s (YAML) vs %s (mat)', name, mat2str(size(a)), mat2str(size(b))));
        elseif ~isequaln(a, b)
            if isnumeric(a), report(sprintf('%s: %s (YAML) vs %s (mat)', name, mat2str(a), mat2str(b)));
            else, report(sprintf('%s: values differ', name)); end
        end
    end
cmp('StartingMode', StartingMode, O.StartingMode);
cmp('NAlarms', NAlarms, O.NAlarms);
cmp('NEnablingConditions', NEnablingConditions, O.NEnablingConditions);
cmp('MCModeNames', info.MCModeNames, O.MCModeNames);
if isfield(O, 'AlarmNames'), cmp('AlarmNames', info.AlarmNames, O.AlarmNames); end
if isfield(O, 'EnablingConditionNames'), cmp('EnablingConditionNames', info.EnablingConditionNames, O.EnablingConditionNames); end
if ~isequal(size(MCMode), size(O.MCMode))
    report(sprintf('MCMode: size %s (YAML) vs %s (mat)', mat2str(size(MCMode)), mat2str(size(O.MCMode))));
else
    fy = fieldnames(MCMode); fm = fieldnames(O.MCMode);
    if ~isequal(fy, fm)
        report(sprintf('MCMode field order/set differs: YAML {%s} vs mat {%s}', strjoin(fy', ','), strjoin(fm', ',')));
    end
    for k = 1:numel(MCMode)
        for f = intersect(fy, fm, 'stable')'
            cmp(sprintf('MCMode(%d).%s', k, f{1}), MCMode(k).(f{1}), O.MCMode(k).(f{1}));
        end
    end
end
% the table before completion (orientation of the user lists), compared for information with the same rules
if isfield(O, 'MCModeUser') && isequal(size(info.MCModeUser), size(O.MCModeUser))
    for k = 1:numel(O.MCModeUser)
        for f = fieldnames(O.MCModeUser)'
            if isfield(info.MCModeUser, f{1})
                cmp(sprintf('MCModeUser(%d).%s', k, f{1}), info.MCModeUser(k).(f{1}), O.MCModeUser(k).(f{1}));
            else
                report(sprintf('MCModeUser(%d).%s missing in the YAML table', k, f{1}));
            end
        end
    end
end
ok = nd == 0;
fprintf('RESULT mcls_check %s: %s vs %s (%d mode(s), %d field(s), %d difference(s))\n', ...
    pick(ok, 'OK', 'FAIL'), table_yaml, old_mat, numel(MCMode), numel(fieldnames(MCMode)), nd);
assert(ok, 'mcls_check_yaml_vs_mat: %d difference(s) between %s and %s', nd, table_yaml, old_mat);
end

function s = pick(c, a, b)
if c, s = a; else, s = b; end
end
