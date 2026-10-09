% Build a METIS IMAS dataset (the pulse_schedule METIS runs from) out of DINA data.
%
% Driven by preprocessing/prepare --metis, which sets:
%   METIS_DINA_SOURCE  URI of the DINA dataset, already converted to DD 4.x
%   METIS_OUTPUT       URI to write the METIS dataset to
%   METIS_MODE         'interpretative' (kinetic profiles taken from DINA) or 'predictive'
%   METIS_NBT          number of time slices
%
% prepare_IDS4METIS_from_dina and the reference configuration both come from the METIS
% install ($EBROOTMETIS, module PDS-METIS).

setenv('IMAS_AL_DISABLE_VALIDATE', '1');   % DINA data trips static-IDS validation

metis_root = getenv('EBROOTMETIS');
if isempty(metis_root)
    error('EBROOTMETIS is unset -- module load PDS-METIS first');
end
addpath(fullfile(metis_root, 'acces', 'dina'));
addpath(genpath(fullfile(metis_root, 'libautre')));
zineb_path;

dina_uri   = getenv('METIS_DINA_SOURCE');
output_uri = getenv('METIS_OUTPUT');
mode       = getenv('METIS_MODE');
nbt        = str2double(getenv('METIS_NBT'));
metis_ref  = fullfile(metis_root, 'certification', 'metis', 'reference_NTM_ITER.mat');

if ~isfile(metis_ref)
    error('METIS reference configuration not found: %s', metis_ref);
end

fprintf('make_metis_input: %s -> %s (%s, %d slices)\n', dina_uri, output_uri, mode, nbt);
[~, error_flag] = prepare_IDS4METIS_from_dina(dina_uri, output_uri, metis_ref, mode, nbt);
if error_flag
    error('prepare_IDS4METIS_from_dina reported error_flag=%d', error_flag);
end
fprintf('make_metis_input: done\n');
