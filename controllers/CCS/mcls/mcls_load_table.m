function [MCMode, StartingMode, NAlarms, NEnablingConditions, info] = mcls_load_table(table_yaml, defaults_yaml, diaryfile)
%MCLS_LOAD_TABLE  MCLS mode table for the controller model, from a mode-table YAML and the library defaults YAML.
%
%   [MCMode, StartingMode, NAlarms, NEnablingConditions, info] = mcls_load_table(table_yaml, defaults_yaml, diaryfile)
%
%   table_yaml     mode table (input specification): top-level keys StartingMode (optional, default = the library's)
%                  and modes (list of mappings, one per MCLS mode, only the fields the author sets; Name is required).
%                  Values: a string -> char row; a number -> double scalar; a list of numbers -> double ROW vector;
%                  [] -> [] (0x0 double), as the former MATLAB setup scripts wrote them.
%                  Example: cases/input/psc/ip_story_mockup/mcls_table.yaml
%   defaults_yaml  library defaults (default: mcls_library_defaults.yaml next to this file), the YAML export of
%                  Config_MCLS.mat of pcssp-iter@8b30ca4b written by tools/mat_to_yaml_mcls.py (typed encoding, see
%                  that tool): MCModeFieldstruct, AlarmsStructure, EnablingConditions, StartingMode
%   diaryfile      settings report written by ReadMCmode (default: a temporary file); an existing file is replaced
%
%   MCMode, StartingMode, NAlarms, NEnablingConditions: the four Parameter data of the MCLS block (doubles), built as
%   the library block mask does (PCSSP_iter_cc_modules.slx block MCLS, system_9254.xml, mask initialization):
%   MCMode = ReadMCmode(MCMode, diary, MCModeFieldstruct, AlarmsStructure, EnablingConditions) (third_party/ReadMCmode.m,
%   unmodified library function), MCMode = rmfield(MCMode, 'Name'), NAlarms = length(AlarmsStructure),
%   NEnablingConditions = length(EnablingConditions); then, as the former setup scripts did, every field is checked to
%   be numeric with the same size in every mode and converted to double (a struct-array Parameter of a MATLAB
%   Function block needs that).
%   info: MCModeNames, AlarmNames, EnablingConditionNames, MCModeUser (the table before completion), table_yaml,
%   defaults_yaml, diaryfile.
%
% YAML is read through Python (pyyaml in the controller's pyenv, PCS module muscle3_venv):
% jsondecode(char(py.json.dumps(py.yaml.safe_load(...)))). jsondecode returns numeric lists as COLUMN vectors and an
% empty list as []; the conversions below restore the row orientation and the exact shapes. Check against a .mat
% made by the former setup scripts: mcls_check_yaml_vs_mat.m.
here = fileparts(mfilename('fullpath'));
if nargin < 2 || isempty(defaults_yaml), defaults_yaml = fullfile(here, 'mcls_library_defaults.yaml'); end
if nargin < 3 || isempty(diaryfile), diaryfile = [tempname '_mcls_diary.txt']; end
if exist('ReadMCmode', 'file') ~= 2, addpath(fullfile(here, 'third_party')); end

% library defaults
D = read_yaml(defaults_yaml);
if ~isfield(D, 'format') || ~strcmp(D.format, 'pds-mcls-matlab-yaml-1')
    error('mcls_load_table:format', '%s: not a pds-mcls-matlab-yaml-1 file (tools/mat_to_yaml_mcls.py)', defaults_yaml);
end
c = decode_value(D.variables.configMCLS);
MCModeFieldstruct = c.MCModeFieldstruct; AlarmsStructure = c.AlarmsStructure; EnablingConditions = c.EnablingConditions;

% mode table
T = read_yaml(table_yaml);
if ~isfield(T, 'modes') || isempty(T.modes)
    error('mcls_load_table:modes', '%s: no modes', table_yaml);
end
modes = T.modes;
if isstruct(modes), modes = num2cell(modes); end      % same keys in every mode: jsondecode gives a struct array
MCMode = struct([]);
for k = 1:numel(modes)
    m = modes{k};
    fn = fieldnames(m);
    for j = 1:numel(fn)
        MCMode(k).(fn{j}) = table_value(m.(fn{j}), sprintf('%s: modes(%d).%s', table_yaml, k, fn{j}));
    end
end
if isfield(T, 'StartingMode')
    StartingMode = double(T.StartingMode);
else
    StartingMode = double(c.StartingMode);
end
MCModeUser = MCMode;

% completion with the library defaults, as the library mask does
if isfile(diaryfile), delete(diaryfile); end
MCMode = ReadMCmode(MCMode, diaryfile, MCModeFieldstruct, AlarmsStructure, EnablingConditions);
MCModeNames = {MCMode.Name};
MCMode = rmfield(MCMode, 'Name');
NAlarms = length(AlarmsStructure);
NEnablingConditions = length(EnablingConditions);
% every field numeric with identical size across modes (struct-array Parameter of a MATLAB Function block)
fn = fieldnames(MCMode);
for k = 1:numel(fn)
    for m = 1:numel(MCMode)
        v = MCMode(m).(fn{k});
        if ~isnumeric(v) && ~islogical(v)
            error('mcls_load_table:field', 'field %s of mode %d is not numeric (%s)', fn{k}, m, class(v));
        end
        if ~isequal(size(v), size(MCMode(1).(fn{k})))
            error('mcls_load_table:size', 'field %s differs in size between modes 1 and %d', fn{k}, m);
        end
        MCMode(m).(fn{k}) = double(v);
    end
end
if StartingMode < 1 || StartingMode > numel(MCMode) || StartingMode ~= round(StartingMode)
    error('mcls_load_table:start', 'StartingMode %g is not a mode index (1..%d)', StartingMode, numel(MCMode));
end
info = struct('MCModeNames', {MCModeNames}, 'AlarmNames', {{AlarmsStructure.Name}}, ...
    'EnablingConditionNames', {{EnablingConditions.Name}}, 'MCModeUser', {MCModeUser}, ...
    'table_yaml', table_yaml, 'defaults_yaml', defaults_yaml, 'diaryfile', diaryfile);
end

function s = read_yaml(file)
% YAML file -> MATLAB value through pyyaml and jsondecode
if ~isfile(file)
    error('mcls_load_table:file', 'file not found: %s', file);
end
fh = py.open(file, 'r');
cleaner = onCleanup(@() fh.close()); %#ok<NASGU>
s = jsondecode(char(py.json.dumps(py.yaml.safe_load(fh))));
end

function v = table_value(y, where)
% value of a mode-table field: char row, double scalar, double row, or [] (0x0 double)
if ischar(y)
    v = reshape(y, 1, []);
elseif isnumeric(y) || islogical(y)
    if isempty(y)
        v = [];
    else
        v = reshape(double(y), 1, []);
    end
else
    error('mcls_load_table:value', '%s: unsupported value (class %s); use a string, a number or a list of numbers', where, class(y));
end
end

function v = decode_value(y)
% typed YAML encoding of tools/mat_to_yaml_mcls.py -> MATLAB value
if ischar(y)                                   % plain string = char row 1xN
    v = y;
elseif isnumeric(y) && isscalar(y)             % plain number = double 1x1
    v = double(y);
elseif isnumeric(y)                            % plain list (not written by the tool) = double row
    v = reshape(double(y), 1, []);
elseif isstruct(y) && isscalar(y) && isfield(y, 'matlab_class')
    sz = reshape(double(y.size), 1, []);
    switch y.matlab_class
        case 'double'
            d = y.data;
            if iscell(d)                       % NaN / Inf / -Inf tokens, possibly mixed with numbers
                d = cellfun(@token_to_double, d);
            end
            v = reshape(double(d), sz);
        case 'char'
            v = reshape(char(y.data), sz);
        case 'cell'
            d = as_cell(y.data);
            v = cell(sz);
            for k = 1:numel(d), v{k} = decode_value(d{k}); end
        case 'struct'
            f = y.fields;
            if ischar(f), f = {f}; end
            f = reshape(f, [], 1);
            d = as_cell(y.data);
            v = repmat(cell2struct(cell(numel(f), 1), f, 1), sz);
            for k = 1:numel(d)
                for j = 1:numel(f)
                    v(k).(f{j}) = decode_value(d{k}.(f{j}));
                end
            end
        otherwise
            error('mcls_load_table:decode', 'unknown matlab_class %s', y.matlab_class);
    end
    if numel(v) ~= prod(sz)
        error('mcls_load_table:decode', '%s of size %s holds %d element(s)', y.matlab_class, mat2str(sz), numel(v));
    end
else
    error('mcls_load_table:decode', 'not a value of the typed YAML encoding (class %s)', class(y));
end
end

function c = as_cell(d)
% jsondecode turns a list into a cell (mixed), a struct array (objects with the same keys), a numeric column
% (numbers), a char (one string) or [] (empty list)
if iscell(d)
    c = d;
elseif isstruct(d) || isnumeric(d) || islogical(d)
    c = num2cell(d);
elseif ischar(d)
    c = {d};
else
    error('mcls_load_table:decode', 'unexpected list (class %s)', class(d));
end
end

function x = token_to_double(t)
if ischar(t)
    switch t
        case 'NaN', x = NaN;
        case 'Inf', x = Inf;
        case '-Inf', x = -Inf;
        otherwise, error('mcls_load_table:decode', 'unknown numeric token %s', t);
    end
else
    x = double(t);
end
end
