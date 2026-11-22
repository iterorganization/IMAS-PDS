% ReadMCmode.m: unmodified copy of the function below (this 6-line header is the only addition) from
%   pcssp-iter@8b30ca4b (ssh://git@git.iter.org/pcs/pcssp-iter.git, branch develop, 2025-11-10)
%   device_lib/MCLS/MCLS_functions/ReadMCmode.m (last change 28e4d7c9 "Pull request #72: CREATE modules GPM 3").
% Used by controllers/CCS/mcls/mcls_load_table.m to complete a PDS MCLS mode table with the same defaults as the
% library block mask (PCSSP_iter_cc_modules.slx block MCLS, system_9254.xml). Provenance: PROVENANCE.md.
% The function writes a diary file (argument filename) with the settings of every mode.
function [MCModeout]=ReadMCmode(MCMode,filename,MCModeFieldstruct,AlarmsStructure,EnablingConditions)
% function [MCModeout]=ReadMCmode(MCMode,filename,MCModeFieldstruct,AlarmsStructure,EnablingConditions)
% This functions assumes as input the MCMode structure designed by the User
% and completes this structure with the default values.
% It also produces a text file named "filename" with all the selected
% choices for the MCMs.
% - MCModeFieldstrcut contains the fields needed to define a MCM
% - AlarmsStructure contains a list of all the possible Alarms from the MCLS
% - EnablingConditions contains a list of all the possible Enabling
% Conditions to make MCM transition or activate specific control actions

diary(filename)
for ii=1:length(MCMode)
    disp(' ')
    disp(' ')
    disp('**********************************************')
    disp(['Magnetic Control Mode ' num2str(ii)])
    disp([MCMode(ii).Name])
    disp('**********************************************')
    disp(' ')
    disp('-- READ and assign default values to field not defined --')
    [MCMode] = ExtractStringsMCMode(MCMode,ii,MCModeFieldstruct,AlarmsStructure,EnablingConditions);
    disp('--------------------------------------------------------')
    disp(' ')
    disp(' ')
    disp('-- Fields Report --')
    for jj = 1:length(MCModeFieldstruct)
        if strcmp(MCModeFieldstruct(jj).type,'Logical')
            disp([MCModeFieldstruct(jj).String2diary num2str(MCMode(ii).(MCModeFieldstruct(jj).namefield))])
        elseif strcmp(MCModeFieldstruct(jj).type,'Integer')
            disp([MCModeFieldstruct(jj).String2diary '[' num2str(MCMode(ii).(MCModeFieldstruct(jj).namefield)) ']'])
        elseif strcmp(MCModeFieldstruct(jj).type,'Real')
            disp([MCModeFieldstruct(jj).String2diary '[' num2str(MCMode(ii).(MCModeFieldstruct(jj).namefield)) ']'])
        elseif strcmp(MCModeFieldstruct(jj).type,'String')
            disp([MCModeFieldstruct(jj).String2diary (MCMode(ii).(MCModeFieldstruct(jj).namefield))])
        end
    end
    if not(all(MCMode(ii).AlarmsEnabled==0))
        disp('* Alarms Active')
        for kk = MCMode(ii).AlarmsEnabled(MCMode(ii).AlarmsEnabled>0)
            disp(AlarmsStructure(kk).Name)
        end
    end
    if not(all(MCMode(ii).EnablingConditions==0))
        disp('* EnablingConditions Active')
        for kk = MCMode(ii).EnablingConditions(MCMode(ii).EnablingConditions>0)
            disp(EnablingConditions(kk).Name)
        end
    end
    MCModeout=MCMode;
end
diary off
end

function [MCMode] = ExtractStringsMCMode(MCMode,k,MCModeFieldstruct,AlarmsStructure,EnablingConditions)
%
%
% If fields not defined for any Mode fill with empty variables for all
% the control Modes
%
MCModeold = MCMode;
NMCM = length(MCMode);
for ii=1:length(MCModeFieldstruct)
    if not(isfield(MCMode(k),MCModeFieldstruct(ii).namefield))
        for k1 = 1:NMCM
            MCMode(k1).(MCModeFieldstruct(ii).namefield)=[];
        end
    end
end

for ii=1:length(MCModeFieldstruct)
    if isempty(MCMode(k).(MCModeFieldstruct(ii).namefield))
        if strcmp(MCModeFieldstruct(ii).type,'String')
            if not(strcmp(MCModeFieldstruct(ii).default,'To be defined'))
                MCMode(k).(MCModeFieldstruct(ii).namefield) = MCModeFieldstruct(ii).default;
                disp([MCModeFieldstruct(ii).namefield ' not found and set to the default value ' MCModeFieldstruct(ii).default])
            else
                error([MCModeFieldstruct(ii).namefield ' not found - please define it'])
            end
        else
            if not(isnan(MCModeFieldstruct(ii).default))
                MCMode(k).(MCModeFieldstruct(ii).namefield) = MCModeFieldstruct(ii).default;
                disp([MCModeFieldstruct(ii).namefield ' not found and set to the default value [' num2str(MCModeFieldstruct(ii).default) ']'])
            else
                error([MCModeFieldstruct(ii).namefield ' not found - please define it'])
            end
        end
    end
end
kkName = 0;
kkName2 = 0;
kkName3 = 0;
kkName4 = 0;
for ii = k %1:length(MCMode)
    kkName = max(kkName,length(MCMode(ii).Name));
    %    kkName2 = max(kkName2,length(MCMode(ii).ControllerParameterFile));
    %    kkName3 = max(kkName3,length(MCMode(ii).FeedforwardXXFilename));
    %    kkName4 = max(kkName4,length(MCMode(ii).VS3KicksSignalFilename));
end
for ii = k %1:length(MCMode)
    MCMode(ii).NextEnabledModes(end+1:length(MCMode)) = 0;
    MCMode(ii).AlarmsEnabled(end+1:length(AlarmsStructure)) = 0;
    MCMode(ii).EnablingConditions(end+1:length(EnablingConditions)) = 0;
    MCMode(ii).EnablingHLTransitionControl(end+1:length(EnablingConditions)) = 0;
    MCMode(ii).EnablingLHTransitionControl(end+1:length(EnablingConditions)) = 0;
    MCMode(ii).EnablingVS3FailureManagControl(end+1:length(EnablingConditions)) = 0;
    MCMode(ii).EnablingEmergencyShutDownPolicy(end+1:length(EnablingConditions)) = 0;
    MCMode(ii).EnablingFWHLProtectionControl(end+1:length(EnablingConditions)) = 0;
    MCMode(ii).VS3KicksEnablingConditions(end+1:length(EnablingConditions)) = 0;
    MCMode(ii).Name(end+1:kkName) = ' ';
    %    MCMode(ii).ControllerParameterFile(end+1:kkName2) = ' ';
    %    MCMode(ii).VS3KicksSignalFilename(end+1:kkName4) = ' ';
end


end
        