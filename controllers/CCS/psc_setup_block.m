function psc_setup_block(mdl, cfgdir, files)
% PSC-4: configure the PSC Subsystem Reference block <mdl>/PSC with the four files of cfgdir and
% run the PSC's own mask set-up (pcssp-nightly@ebf3ee0 src/psc/+PSC/+MODEL/MaskCallBacks.m
% 'PSCModelSetUp': parsers, buses PSC_In/Out/Int_Bus, PSC.PSCClass -> base workspace PSCObj),
% as the PSC-2 check did on a host model. The Pcssignal bus is defined first, as in
% pcs@add-AM run_CREATE_assessment_CCS01.m:19-21.
if nargin < 3
    files = struct('intf', 'PSCIntConfig.xml', 'glob', 'PSCGlobalMonConfig.xml', 'bt', 'BTree.xml', 'refgen', 'PS.xml');
end
[~, B] = PcsSignal(1, "value", ""); assignin('base', 'Pcssignal', B{1});
blk = [mdl '/PSC'];
set_param(0, 'CurrentSystem', mdl);
set_param(blk, 'ConfFolderPath', cfgdir);
mo = get_param(blk, 'MaskObject');
for prm = {'PSCInterConfFileName', 'GlobMonFileName', 'DecisionFileName', 'RefGenFileName'}
    q = mo.getParameter(prm{1}); q.TypeOptions = {files.intf, files.glob, files.bt, files.refgen};
end
set_param(blk, 'PSCInterConfFileName', files.intf, 'GlobMonFileName', files.glob, ...
    'DecisionFileName', files.bt, 'RefGenFileName', files.refgen);
% MaskCallBacks.m:155 (updateSystemObjectMask) searches the MATLAB System block under gcs: make the
% PSC block the current system so that exactly the PSC's PSCMatSys is found
set_param(0, 'CurrentSystem', blk);
h = find_system(gcs, 'FollowLinks', 'on', 'LookUnderMasks', 'on', 'FindAll', 'on', 'BlockType', 'MATLABSystem');
fprintf('PSC set-up: gcs = %s, MATLAB System blocks found under it: %d\n', gcs, numel(h));
try
    PSC.MODEL.MaskCallBacks(blk, 'PSCModelSetUp');
catch ME
    % Observed 2026-11-06 (R2025b, after the module inits): updateSystemObjectMask (MaskCallBacks.m:155-157)
    % finds no MATLAB System block under gcs and fails. It runs after PSCObj was assigned to base
    % (MaskCallBacks.m:84-85); it only copies the mask values onto the inner PSCMatSys block, whose
    % bus names already are PSC_In/Out/Int_Bus and whose file fields setupImpl does not read
    % (PSCSysObj.m:90-116 takes evalin('base','PSCObj')). Accept that case only, after checking it.
    sysb = [blk '/PSCMatSys'];
    okb = strcmp(get_param(sysb, 'InBus'), 'PSC_In_Bus') && strcmp(get_param(sysb, 'OutBus'), 'PSC_Out_Bus') && ...
          strcmp(get_param(sysb, 'IntBus'), 'PSC_Int_Bus') && evalin('base', 'exist(''PSCObj'', ''var'')') == 1;
    st = ME.stack(1);
    fprintf('PSC set-up: PSCModelSetUp error "%s" at %s:%d, gcs = %s; PSCObj in base and inner bus names OK = %d\n', ...
        ME.message, st.name, st.line, gcs, okb);
    if ~(okb && strcmp(st.name, 'updateSystemObjectMask')), rethrow(ME); end
end
ph = get_param(blk, 'PortHandles');
fprintf('PSC set-up: %s, in=%d out=%d, PSCObj in base = %d\n', cfgdir, numel(ph.Inport), numel(ph.Outport), ...
    evalin('base', 'exist(''PSCObj'', ''var'')'));
end
