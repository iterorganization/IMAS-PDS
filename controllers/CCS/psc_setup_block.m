function psc_setup_block(blk, cfgdir)
% Gives the PSC block blk (Subsystem Reference to PSC) the four files of the folder cfgdir and
% runs the PSC's own mask set-up: buses PSC_In/Out/Int_Bus and PSCObj in the base workspace.
% Called by the controller init with psc_enabled = 1; also usable from the command window
% (local_installs/pcs-with-pcssp-nightly on the path) to have the buses when editing the model.
files = {'PSCIntConfig.xml', 'PSCGlobalMonConfig.xml', 'BTree.xml', 'PS.xml'};
[~, B] = PcsSignal(1, "value", "");
assignin('base', 'Pcssignal', B{1});
set_param(0, 'CurrentSystem', bdroot(blk));
set_param(blk, 'ConfFolderPath', cfgdir);
mo = get_param(blk, 'MaskObject');
prm = {'PSCInterConfFileName', 'GlobMonFileName', 'DecisionFileName', 'RefGenFileName'};
for k = 1:4
    q = mo.getParameter(prm{k});
    q.TypeOptions = files;
end
set_param(blk, prm{1}, files{1}, prm{2}, files{2}, prm{3}, files{3}, prm{4}, files{4});
% the set-up looks for the PSC's MATLAB System block under the current system
set_param(0, 'CurrentSystem', blk);
try
    PSC.MODEL.MaskCallBacks(blk, 'PSCModelSetUp');
catch ME
    % known R2025b failure in its last step (updateSystemObjectMask), after PSCObj is in base:
    % accept it only if the inner block already has the right buses
    sysb = [blk '/PSCMatSys'];
    ok = strcmp(get_param(sysb, 'InBus'), 'PSC_In_Bus') && strcmp(get_param(sysb, 'OutBus'), 'PSC_Out_Bus') && ...
         strcmp(get_param(sysb, 'IntBus'), 'PSC_Int_Bus') && evalin('base', 'exist(''PSCObj'', ''var'')') == 1;
    if ~(ok && strcmp(ME.stack(1).name, 'updateSystemObjectMask'))
        rethrow(ME);
    end
end
end
