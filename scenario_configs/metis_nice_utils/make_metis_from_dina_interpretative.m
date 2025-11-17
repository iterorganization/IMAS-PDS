% make METIS data from dina for pds test case
addpath ../../../run/metis
zineb_path;
p = fileparts(which('metis'));
root = fileparts(fileparts(p));
dina_file  = getenv('metis_dina_source');
metis_file = getenv('metis_imas_dataset');
metis_ref  = fullfile(p,'certification','metis','reference_NTM_ITER.mat');
prepare_IDS4METIS_from_dina(dina_file, metis_file,metis_ref,'interpretative',51);
              