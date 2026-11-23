function [A_cl, sys_cl, L] = build_cl(G, VS_control_mode, loop_break)
% Closed loop of the linear system with a vertical unstable rigid plasma
%   G: VS gains (fields of K.VS / Config_VS.Gains, plus Ip_ref)
%   VS_control_mode: 0 off, 1 VS1, 2 VS3, 3 VS1+VS3
%   loop_break (optional): 'VS1', 'VS3' or a KCURR circuit ('CS3U', ..., 'PF6'). That supply gets an
%     external voltage d instead of the controller command y, all the other loops stay closed, and
%     L = -y/d is the loop transfer function.
%     A_cl and sys_cl are then the system with that loop open.
% States: plant (114), Zdot (1), VS filter (0-2). Inputs: the 11 circuit current references, Ip_ref.

if nargin < 3
    loop_break = '';
end

KCURR      = 1;      % 0 switches KCURR off
control_Ip = 1;      % Ke_Ip or Ke_noIp
dt         = 1e-3;   % for the derivative

prm = fullfile(fileparts(mfilename('fullpath')), '..', 'params');
P = load(fullfile(prm, 'plant.mat'));        % linear model
KC = load(fullfile(prm, 'FC001_Config_KCURR.mat'));   % KCURR gains, full precision (controller.mat has them rounded to 4 decimals)

circuits = {'CS3U','CS2U','CS1','CS2L','CS3L','PF1','PF2','PF3','PF4','PF5','PF6'};

%% VS law
%   mode 1: VS1 = F1(KZ_VS1*Ip_ref*Zdot - KI_VS1*(I - I_ref))
%   mode 2: VS3 = F3(-KZ_VS3*Ip_ref*Zdot - KI_VS3*I_VS3)
%   mode 3: VS3 = F13(-KZ_VS13*Ip_ref*Zdot - KIVS3_VS13*I_VS3), VS1 = -KIVS1_VS13*I_VS3 (KIVS1 flipped as in the init, VS1 unchanged)
switch VS_control_mode
    case 1
        g = [G.KZ_VS1*G.Ip_ref, 0, -G.KI_VS1(:)'];
        Av = G.AVS1;  Bv = G.BVS1(:)*g;  Cv = [G.CVS1(:)'; 0*G.CVS1(:)'];  Dv = [G.DVS1*g; zeros(1,13)];
    case 2
        g = [-G.KZ_VS3*G.Ip_ref, -G.KI_VS3, zeros(1,11)];
        Av = G.AVS3;  Bv = G.BVS3*g;  Cv = [0*G.CVS3; G.CVS3];  Dv = [zeros(1,13); G.DVS3*g];
    case 3
        g = [-G.KZ_VS13*G.Ip_ref, -G.KIVS3_VS13, zeros(1,11)];
        Av = G.AVS13; Bv = G.BVS13*g; Cv = [0*G.CVS13; G.CVS13];
        Dv = [0, -G.KIVS1_VS13, zeros(1,11); G.DVS13*g];
    otherwise
        Av = zeros(0);  Bv = zeros(0,13);  Cv = zeros(2,0);  Dv = zeros(2,13);
end
Av = double(Av);  Bv = double(Bv);  Cv = double(Cv);  Dv = double(Dv);

% every signal is a row acting on [x; Zdot; x_vs; ref; d]
sizes = [size(P.A,1), 1, size(Av,1), 12, 1];
u = mat2cell(eye(sum(sizes)), sizes, sum(sizes));
[x, Zdot, x_vs, ref, d] = u{:};
I_ref = ref(1:11,:);
Ip_ref = ref(12,:);

%% measurements
coil = @(name) double(strcmp(P.coil_names, name)) * P.C_coil;     % one coil current
I_circ = [coil('CS3U'); coil('CS2U'); (coil('CS1U') + coil('CS1L'))/2; coil('CS2L'); ...
          coil('CS3L'); coil('PF1'); coil('PF2'); coil('PF3'); coil('PF4'); coil('PF5'); coil('PF6')] * x;
Ip = P.c_Ip * x;
I_VS3 = (coil('VS3L') - coil('VS3U'))/2 * x;     % polarity of controller_input_preprocess.m: grows with VS3_cmd > 0

%% KCURR
if control_Ip
    Ke = KC.Config_KCURR.KCURR_Gains.Ke_Ip;
else
    Ke = KC.Config_KCURR.KCURR_Gains.Ke_noIp;
end
V_cspf = KCURR*Ke*[I_ref - I_circ; Ip_ref - Ip];

%% VS
r = [Zdot; I_VS3; I_circ - I_ref];
dx_vs = Av*x_vs + Bv*r;
VS_cmd = Cv*x_vs + Dv*r;
V_vs1 = VS_cmd(1,:);
VS3_cmd = VS_cmd(2,:);

%% loop break: one command replaced by d
cmd = [V_cspf; V_vs1; VS3_cmd];
cmd_names = [circuits, {'VS1', 'VS3'}];
applied = cmd;
if ~isempty(loop_break)
    k = find(strcmp(cmd_names, loop_break));
    if isempty(k)
        error('build_cl:loopBreak', 'unknown loop_break %s', loop_break);
    end
    applied(k,:) = d;
end

%% the 14 supply voltages
V = [applied(1:2,:); applied(3,:)/2; applied(3,:)/2; applied(4:10,:); applied(12,:); applied(11,:); applied(13,:)];

%% plant, driven by the controller output
dx = P.A*x + P.B*V;

%% Zdot
dZdot = (P.c_z*dx - Zdot)/(dt/2);

%% closed loop
n = sum(sizes(1:3));
dX = [dx; dZdot; dx_vs];
A_cl = dX(:, 1:n);
B_cl = dX(:, n+1:n+12);
C_cl = [P.c_z; P.C_coil] * x(:, 1:n);
D_cl = zeros(15, 12);
sys_cl = ss(A_cl, B_cl, C_cl, D_cl, 'InputName', [strcat('Iref_', circuits), {'Ipref'}], ...
            'OutputName', [{'zmag'}, strcat('I_', P.coil_names(:)')]);

L = [];
if ~isempty(loop_break)
    L = -ss(A_cl, dX(:, end), cmd(k, 1:n), cmd(k, end));
end
end
