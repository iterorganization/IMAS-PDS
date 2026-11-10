function psc_framework_conf()
% PSC-4: the framework copy runs scdds-core 6b7e482 (pcssp-nightly merge_IGZ_PSC ebf3ee0), whose
% SCDDSclass_algo.init attaches a ConfigSetRef <model>_ConfigRef to each pcssp_module model
% (SCDDSclass_algo.m:391-411, 650-680) instead of putting 'configurationSettings' in the base
% workspace as scdds 709c65f did (SCDDSclass_algo.m:529-546 there, via SCDconf_setConf). The pcs
% wrapper model pcssp_RZIp_CCS (RZIp_CCS_wrapper_obj, a pcssp_wrapper) still refers to a
% configuration reference 'configurationSettings' and no init attaches one, so a diagram update
% fails with "Unable to find configuration: 'configurationSettings' referenced by 'pcssp_RZIp_CCS'".
% This puts the same configuration as in the P2e runs (pcssp_Simulation from
% configurations_container_pcssp.sldd) in the base workspace under that name, with the framework's
% own function (nightly SCDconf_setConf.m, default exportname 'configurationSettings').
SCDconf_setConf('pcssp_Simulation', 'configurations_container_pcssp.sldd');
end
