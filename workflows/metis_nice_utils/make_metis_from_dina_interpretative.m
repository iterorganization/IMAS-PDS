% make METIS data from dina for pds test case
addpath(getenv('EBROOTMETIS'))
zineb_path;
p = fileparts(which('metis'));
root = fileparts(fileparts(p));
dina_file  = getenv('metis_dina_source');
metis_file = getenv('metis_imas_dataset');
metis_ref  = fullfile(p,'certification','metis','reference_NTM_ITER.mat');
% 301 time slices (~0.1 s apart early in the pulse) instead of 51 (~0.7 s): the
% workflow's source_metis/synchro_nice_metis pick the CLOSEST slice to NICE's time, and
% with 51 slices the METIS bootstrap at 2.42 s used the 2.61 s slice (Ip 1.44 MA vs
% DINA's 1.27 MA), a 12% Ip error the magnetic controller then fought from step one.
prepare_IDS4METIS_from_dina(dina_file, metis_file,metis_ref,'interpretative',301);
              