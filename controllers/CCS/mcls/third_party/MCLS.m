function [ControlModeIndex,ShapeIpControlMode,IpControlMode, VSControlMode, SCIpScaling, VSIpScaling ,...
    SNUControl, CurrentLimitAvoidance, VS3_kick_volt_on, RefSmoothTrans,...
    HL_contr_on, LH_contr_on, FWHLP_contr_on, EmShutDown_contr_on, Alarms_MCLS, EnablingConditions_MCLS] = ...
    MCLS(time,CSPF_curr_meas,VS1_curr_meas,VS3_curr_meas,Ipl_est,Rpl_est,Zpl_est,...
    islimiter_est,li3_est,betapol_est,RXP_est,ZXP_est,RXPup_est,ZXPup_est,dsep_est,IplContrErr,RplContrErr,ZplContrErr,...
    GapContrErr,FluxContrErr,CSPF_curr_ContrErr,ForceControlMode,...
    MCMode,StartingMode,NAlarms,NEnablingConditions,isHmode,isVS3Failure,...
    HL_contr_cmd,LH_contr_cmd,FWHLP_contr_cmd,EmShutDown_contr_cmd,TriggerControlAction)
% PDS copy of chart_150 (pcssp-iter@8b30ca4b), MODIFIED in 4 lines: this comment line added, line 153 changed (imin -> imin(1)), and two coder.varsize declarations added (lines 179 and 186), all for MATLAB R2025b code generation; see PROVENANCE.md in this folder for the source, the exact changes and how to re-extract the original.
persistent iactualmode
%
if isempty(iactualmode) % First step MCM
    iactualmode=StartingMode;
    disp('*************************************')
    disp(['Starting Control Mode '])
    disp(iactualmode)
end
% MCM forced by PSC
if not(round(ForceControlMode)==0)
    iactualmode= round(ForceControlMode);
    disp('Mode Forced to ')
    disp(iactualmode)
end
isdiverted_est = logical(not(islimiter_est));
%
% Matrix with Conditions for MCM transitions
% Actual State per Rows. Next State per Columns
EnablingTransitionMatrix = logical(eye(length(MCMode),length(MCMode)));
%
ConditionMatrixEC = true(length(MCMode),length(MCMode),NEnablingConditions); % all transition possible if not forbidden
Condition01 = false;
Condition02 = false;
Condition03 = false;
Condition04 = false;
Condition05 = false;
Condition06 = false;
Condition07 = false;
Condition08 = false;
Condition09 = false;
Condition10 = false;
Condition11 = false;
Condition12 = false;
Condition01s = false; % Conditions enabling specific actions in the actual mode
Condition02s = false;
Condition03s = false;
Condition04s = false;
Condition05s = false;
AlarmMatrix = false(length(MCMode),NAlarms); % Alarms disabled
Alarms_MCLS = false(NAlarms,1);
EnablingConditions_MCLS = false(NEnablingConditions,1);
%
Trtime0s = logical(eye(length(MCMode),length(MCMode))); % Transition time condition
Trtime0f = logical(eye(length(MCMode),length(MCMode))); % Transition time condition
TrIp0s = logical(eye(length(MCMode),length(MCMode))); % Transition Ipl condition
TrIp0f = logical(eye(length(MCMode),length(MCMode))); % Transition Ipl condition
for ii=1:length(MCMode)
    ijk = MCMode(ii).NextEnabledModes(MCMode(ii).NextEnabledModes>0);
    EnablingTransitionMatrix(ii,ijk) = true;
    Trtime0s(:,ii) = time>=MCMode(ii).time0intervals; % check that time is in the activation interval
    Trtime0f(:,ii) = time<=MCMode(ii).time0intervalf; % check that time is in the activation interval
    TrIp0s(:,ii) = Ipl_est>=MCMode(ii).Ip0intervals;  % check that Ip is in the activation interval
    TrIp0f(:,ii) = Ipl_est<=MCMode(ii).Ip0intervalf;  % check that Ip is in the activation interval
    %
    % Alarms check
    AlarmMatrix(ii,1) = time>MCMode(ii).timemax;
    AlarmMatrix(ii,2) = Ipl_est < MCMode(ii).Ipmin;
    AlarmMatrix(ii,3) = Ipl_est > MCMode(ii).Ipmax;
    AlarmMatrix(ii,4) = abs(IplContrErr)>MCMode(ii).MaxIplContrError;
    AlarmMatrix(ii,5) = abs(RplContrErr)>MCMode(ii).MaxRplContrError;
    AlarmMatrix(ii,6) = abs(ZplContrErr)>MCMode(ii).MaxZplContrError;
    AlarmMatrix(ii,7) = max(abs(GapContrErr))>MCMode(ii).MaxGapContrError;
    AlarmMatrix(ii,8) = max(abs(FluxContrErr))>MCMode(ii).MaxFluxContrError;
    AlarmMatrix(ii,9) = max(abs(CSPF_curr_ContrErr))>MCMode(ii).MaxCurrContrError;
    jk = setdiff([1:NAlarms],sort(MCMode(ii).AlarmsEnabled));
    AlarmMatrix(ii,jk)= false;
    %
    % Check next MCM enabled
    for jj = 1:length(MCMode)
        RR = MCMode(jj).BoxForCentroid(1);
        ZZ = MCMode(jj).BoxForCentroid(2);
        DR = MCMode(jj).BoxForCentroid(3);
        DZ = MCMode(jj).BoxForCentroid(4);
        Condition01 = (Rpl_est<=RR+DR & Rpl_est>=RR-DR & Zpl_est<=ZZ+DZ & Zpl_est>=ZZ-DZ);
        RR = MCMode(jj).BoxForXP(1);
        ZZ = MCMode(jj).BoxForXP(2);
        DR = MCMode(jj).BoxForXP(3);
        DZ = MCMode(jj).BoxForXP(4);
        Condition02 = (RXP_est<=RR+DR & RXP_est>=RR-DR & ZXP_est<=ZZ+DZ & ZXP_est>=ZZ-DZ);
        Condition03 = isdiverted_est;
        RR = MCMode(jj).BoxForXPUP(1);
        ZZ = MCMode(jj).BoxForXPUP(2);
        DR = MCMode(jj).BoxForXPUP(3);
        DZ = MCMode(jj).BoxForXPUP(4);
        Condition04 = (RXPup_est<=RR+DR & RXPup_est>=RR-DR & ZXPup_est<=ZZ+DZ & ZXPup_est>=ZZ-DZ);
        Condition05 = (dsep_est<=MCMode(jj).dsepmin);
        Condition06 = logical(isHmode);
        Condition07 = logical(HL_contr_cmd);
        Condition08 = logical(LH_contr_cmd);
        Condition09 = logical(FWHLP_contr_cmd);
        Condition10 = logical(isVS3Failure);
        Condition11 = logical(EmShutDown_contr_cmd);
        Condition12 = not(isVS3Failure*1);
        if ii==jj
            Condition01s = Condition01;
            Condition02s = Condition02;
            Condition03s = Condition03;
            Condition04s = Condition04;
            Condition05s = Condition05;
        end
        ConditionMatrixEC(ii,jj,1) = Condition01;
        ConditionMatrixEC(ii,jj,2) = Condition02;
        ConditionMatrixEC(ii,jj,3) = Condition03;
        ConditionMatrixEC(ii,jj,4) = Condition04;
        ConditionMatrixEC(ii,jj,5) = Condition05;
        ConditionMatrixEC(ii,jj,6) = Condition06;
        ConditionMatrixEC(ii,jj,7) = Condition07;
        ConditionMatrixEC(ii,jj,8) = Condition08;
        ConditionMatrixEC(ii,jj,9) = Condition09;
        ConditionMatrixEC(ii,jj,10) = Condition10;
        ConditionMatrixEC(ii,jj,11) = Condition11;
        ConditionMatrixEC(ii,jj,12) = Condition12;
    end
end
%
for ii = 1:length(MCMode)
    for jj = 1:length(MCMode)
        for kk = 1:NEnablingConditions
            Auxx = [MCMode(jj).EnablingConditions];
            if (isempty(find(MCMode(jj).EnablingConditions==kk)))
                ConditionMatrixEC(ii,jj,kk) = true;
            end
        end
    end
end

TransitionMatrix = logical(EnablingTransitionMatrix.*Trtime0s.*Trtime0f.*TrIp0s.*TrIp0f);
for jk = 1:NEnablingConditions
    TransitionMatrix= logical(TransitionMatrix.*ConditionMatrixEC(:,:,jk));
end

inextmode = find(TransitionMatrix(iactualmode,:));
if not(all(inextmode==iactualmode)) % valutare se sostituire con not(all(...))
    disp('*************************************')
    disp(['Control Mode changed at time [s]'])
    disp(time)
    disp(['Ip [MA]'])
    disp(Ipl_est/1e6)
    disp(['New Control Mode '])
    disp(inextmode)
    jjj=MCMode(iactualmode).NextEnabledModes(MCMode(iactualmode).NextEnabledModes>0);
    pos = []; for kk=1:length(inextmode); pos=[pos find(inextmode(kk)==jjj)]; end
    [dum,imin]=min(pos);
    iactualmode = inextmode(imin(1)); % inextmode in order of priority. PDS 2026-11-15: imin(1) instead of imin -- R2025b codegen rejected the variable-size assignment (job 1317052); same result when imin is scalar. Further R2025b fixes: variable-size declarations after chart lines 177 and 183.
%    c=find(any(jjj==inextmode',1));
%    iactualmode = jjj(c(1)); % inextmode in order of priority
end
%
ShapeIpControlMode=MCMode(iactualmode).ShapeIpControlMode;
IpControlMode=MCMode(iactualmode).IpControlMode;
VSControlMode=MCMode(iactualmode).VSControlMode;
if isVS3Failure && not(VSControlMode==0)
    VSControlMode = 1;
end
SCIpScaling=MCMode(iactualmode).SCIpScaling;
VSIpScaling=MCMode(iactualmode).VSIpScaling;
SNUControl=MCMode(iactualmode).SNUControl;
CurrentLimitAvoidance=MCMode(iactualmode).CurrentLimitAvoidance;

% Specific action activation
Conditions = ([Condition01s; Condition02s; Condition03s; Condition04s; Condition05s; ...
    Condition06; Condition07; Condition08; Condition09; Condition10; Condition11; Condition12]);

%HL_contr_on=0;
%LH_contr_on=0;
%FWHLP_contr_on=0;
%VS3_kick_volt_on=0;
%EmShutDown_contr_on=0;
icond = 100;
coder.varsize('icond', [1 12], [0 1]); % PDS 2026-11-15: index vector of up to NEnablingConditions=12 entries (R2025b codegen, job 1317081)
% Specific Control Action
% 
% VS3 Kicks
VS3Kickson=logical(MCMode(iactualmode).VS3Kicks);
iii = find(MCMode(iactualmode).VS3KicksEnablingConditions>0);
ccc = true;
coder.varsize('ccc', [12 1], [1 0]); % PDS 2026-11-15: scalar or logical column (Conditions(icond), chart line 202) (R2025b codegen)
if not(isempty(iii))
    icond = MCMode(iactualmode).VS3KicksEnablingConditions(iii);
    ccc = all(Conditions(icond));
else
    ccc = true;
end
if VS3Kickson && TriggerControlAction(1)==1 && all(ccc)
    VS3_kick_volt_on=1;
else
    VS3_kick_volt_on=0;
end
%
% HL Transitions
HLon=logical(MCMode(iactualmode).HLTransitionControl);
iii = find(MCMode(iactualmode).EnablingHLTransitionControl>0);
ccc = true;
if not(isempty(iii))
    icond = MCMode(iactualmode).EnablingHLTransitionControl(iii);
    ccc = Conditions(icond);
else
    ccc=true;
end
if HLon && all(ccc)
    HL_contr_on=1;
else
    HL_contr_on=0;
end
% LH Transitions
LHon=logical(MCMode(iactualmode).LHTransitionControl);
iii = find(MCMode(iactualmode).EnablingLHTransitionControl>0);
ccc=true;
if not(isempty(iii))
    icond = MCMode(iactualmode).EnablingLHTransitionControl(iii);
    ccc = all(Conditions(icond));
else
    ccc=true;
end
if LHon && all(ccc)
    LH_contr_on=1;
else
    LH_contr_on=0;
end
%
% FWHL Protection
FWHLPon=logical(MCMode(iactualmode).FWHLProtectionControl);
iii = find(MCMode(iactualmode).EnablingFWHLProtectionControl>0);
ccc=true;
if not(isempty(iii))
    icond = MCMode(iactualmode).EnablingFWHLProtectionControl(iii);
    ccc = all(Conditions(icond));
else
    ccc=true;
end
if FWHLPon && all(ccc)
    FWHLP_contr_on=1;
else
    FWHLP_contr_on=0;
end
%
% Emergency Shut Down
ESDon=logical(MCMode(iactualmode).EmergencyShutDownPolicy);
iii = find(MCMode(iactualmode).EnablingEmergencyShutDownPolicy>0);
ccc=true;
if not(isempty(icond))
    icond = MCMode(iactualmode).EnablingEmergencyShutDownPolicy(iii);
    ccc = all(Conditions(icond));
else
    ccc=true;
end
if ESDon && all(ccc)
    EmShutDown_contr_on=1;
else
    EmShutDown_contr_on=0;
end
%
RefSmoothTrans=MCMode(iactualmode).ReferenceSmoothTransition;
%
ControlModeIndex = iactualmode;
Alarms_MCLS(1:NAlarms) = AlarmMatrix(iactualmode,:);
%
% Selfcondition not used. Only for monitoring
for jk = 1:NEnablingConditions
    EnablingConditions_MCLS(jk) = ConditionMatrixEC(iactualmode,iactualmode,jk);
end
%
