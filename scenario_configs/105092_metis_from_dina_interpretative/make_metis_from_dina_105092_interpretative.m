% make METIS data from dina for pds test case
addpath ../../../run/metis
zineb_path;
p = fileparts(which('metis'));
root = fileparts(fileparts(p));
dina_file  = sprintf('imas:hdf5?path=%s',fullfile(pwd,'data','105092_in'));
metis_file = sprintf('imas:hdf5?path=%s',fullfile(pwd,'data','105092_metis_in'));
metis_ref  = fullfile(p,'certification','metis','reference_NTM_ITER.mat');
prepare_IDS4METIS_from_dina(dina_file, metis_file,metis_ref,'interpretative',301);
              