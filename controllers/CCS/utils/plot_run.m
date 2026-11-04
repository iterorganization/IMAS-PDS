close all
clc
clear

run_dir = '/home/ITER/centong/Desktop/PDSs/IMAS-PDS-torax/cases/runs/evolutive_controller_105073_20261104_110915';

plot_rms = true;
t_rms    = 0.1;

ts ='/equilibrium/time_slice[]&';
eq_signals = {
    'ip', [ts 'global_quantities&ip']
    'zgeo', [ts 'boundary&geometric_axis&z']
    'rgeo', [ts 'boundary&geometric_axis&r']
    'rmag', [ts 'global_quantities&magnetic_axis&r']
    'zmag', [ts 'global_quantities&magnetic_axis&z']
    %'li_3',[ts 'global_quantities&li_3']
    %'psi_boundary',[ts 'boundary&psi']
};
vtf_signals = {
    'b0', '/equilibrium/vacuum_toroidal_field&b0'
    'r0', '/equilibrium/vacuum_toroidal_field&r0'
    'f', [ts 'profiles_1d&f']
};
psi_signals = {'psi_b', [ts 'global_quantities&psi_boundary']};
eq_signals = [eq_signals; vtf_signals; psi_signals];
% NICE and TORAX profiles against psi and global quantities, compared in the TORAX workflows
prof_signals = {
    'psi_1d', [ts 'profiles_1d&psi']
    'p_1d', [ts 'profiles_1d&pressure']
    'q_1d', [ts 'profiles_1d&q']
    'j_1d', [ts 'profiles_1d&j_phi']
};
gq_signals = {
    'beta_pol', [ts 'global_quantities&beta_pol']
    'li_3', [ts 'global_quantities&li_3']
};
tcp_signals = {
    'v_loop', '/core_profiles/global_quantities&v_loop'
    'beta_pol', '/core_profiles/global_quantities&beta_pol'
    'li_3', '/core_profiles/global_quantities&li_3'
};

pfa_signals = {
    'coil_current', '/pf_active/coil[]&current&data'
    'coil_names', '/pf_active/coil[]&name'
};

ref_signals = {
    'coil_current', '/pf_active/coil[]&current&data'
    'coil_voltage', '/pf_active/coil[]&voltage&data'
    'coil_names', '/pf_active/coil[]&name'
};

ppas_signals = {
    'loop_current', '/pf_passive/loop[]&current'
};

% read every run; the F_INIT reference (ref) comes from the case of the run
run_dirs = cellstr(run_dir);
for i = 1:numel(run_dirs)
    rd = strip(run_dirs{i}, 'right', '/');
    [runs_dir, run_name] = fileparts(rd);
    case_name = regexprep(run_name, '_\d{8}_\d{6}.*$', '');
    R(i).case_dir = fullfile(fileparts(runs_dir), case_name);
    R(i).label = strrep(erase(run_name, [case_name '_']), '_', '\_');   
    R(i).csv  = read_csv_signals(fullfile(rd, 'simulink_log.csv'));

    R(i).csv.CSPF_curr_ref = R(i).csv.KCURR_actual_ref;

    plant_dir = first_folder(rd, {'out_plant', 'out_nice', 'nice_out'});
    ctrl_dir  = first_folder(rd, {'out_controller', 'controller_out'});
    ref_dir   = first_folder(fullfile(R(i).case_dir, 'preprocess'), {'initial_state', 'dina_in', 'in'});
    has_torax = isfile(fullfile(rd, 'out_torax', 'equilibrium.h5'));
    nice_signals = eq_signals;
    if has_torax
        nice_signals = [eq_signals; prof_signals; gq_signals];
    end
    R(i).eq   = read_h5_signals(fullfile(plant_dir, 'equilibrium.h5'), '/equilibrium/time', nice_signals);
    R(i).tx   = struct();                      % TORAX's equilibrium, in the TORAX workflows only
    if has_torax
        R(i).tx = read_h5_signals(fullfile(rd, 'out_torax', 'equilibrium.h5'), '/equilibrium/time', ...
            [vtf_signals; psi_signals; prof_signals]);
    end
    R(i).tcp  = struct();                      % TORAX's loop voltage, beta_pol and li_3
    if isfile(fullfile(rd, 'out_torax', 'core_profiles.h5'))
        R(i).tcp = read_h5_signals(fullfile(rd, 'out_torax', 'core_profiles.h5'), '/core_profiles/time', ...
            tcp_signals);
    end
    R(i).pfa  = read_h5_signals(fullfile(plant_dir, 'pf_active.h5'), '/pf_active/time', pfa_signals);       % measured coil currents
    R(i).ppas = struct();
    if isfile(fullfile(plant_dir, 'pf_passive.h5'))
        R(i).ppas = read_h5_signals(fullfile(plant_dir, 'pf_passive.h5'), '/pf_passive/time', ppas_signals);    % vessel loop currents
    end
    ctrl_file = fullfile(ctrl_dir, 'pf_active.h5');
    R(i).ctrl = read_h5_signals(ctrl_file, '/pf_active/time', ...
        {'supply_voltage', supply_voltage_path(ctrl_file)});              % voltages sent by the controller
    R(i).ref  = read_h5_signals(fullfile(ref_dir, 'pf_active.h5'), '/pf_active/time', ref_signals);
    if abs(R(i).csv.time(end) - R(i).pfa.time(end)) > 0.01
        warning('%s: simulink_log.csv ends at t = %.3f s but the run at %.3f s: it is from another run', ...
            run_name, R(i).csv.time(end), R(i).pfa.time(end));
    end
end
if numel(unique({R.case_dir})) > 1
    warning('The runs come from different cases: the KCURR reference and the F_INIT slices shown are those of the first run.');
end
colors = lines(numel(R));
t_lim = [min(arrayfun(@(r) r.csv.time(1), R)), max(arrayfun(@(r) r.csv.time(end), R))];
% the first run, for the reference and the single-run sections
csv_ctrl = R(1).csv; eq = R(1).eq; pfa = R(1).pfa; ref = R(1).ref; ctrl = R(1).ctrl; ppas = R(1).ppas;

% ===== Constants =====
circ_names = {'CS3U','CS2U','CS1','CS2L','CS3L','PF1','PF2','PF3','PF4','PF5','PF6'};
% the 14 coils of pf_active and the KCURR circuit of each (column of CSPF_curr_ref, 0 = none)
coil_names = {'CS3U','CS2U','CS1U','CS1L','CS2L','CS3L','PF1','PF2','PF3','PF4','PF5','PF6','VS3U','VS3L'};
coil_circ = [1 2 3 3 4 5 6 7 8 9 10 11 0 0];
% the 14 voltages sent by the controller are power-supply voltages, coil{k}.voltage = supply k
% (controller_output_preprocess); limits: voltage_limit_max of pf_active.supply in the F_INIT entry
supply_names = {'CS3U','CS2U','CS1U','CS1L','CS2L','CS3L','PF1','PF2','PF3','PF4','PF5','VS1','PF6','VS3'};
vlim_supply = [2100 2100 2100 2100 2100 2100 2100 3150 3150 3150 3150 6300 2100 2400];
tau = 0.1;

t_csv = csv_ctrl.time;
[~, dIref_dt] = gradient(csv_ctrl.CSPF_curr_ref, 1, t_csv);   % derivative along time
slices = ref.time(ref.time >= t_csv(1) & ref.time <= t_csv(end));

figure('Name','Coil error')
tiledlayout(2, numel(R), 'TileSpacing', 'compact', 'TileIndexing', 'columnmajor');   % one column per run
for i = 1:numel(R)
    c = R(i).csv;
    nexttile
    hh = plot(c.t, c.KCURR_CSPF_ctrl_e);
    title(['KCURR control error ' R(i).label])
    ylabel('I [A]')
    nexttile

    I_norm = max(abs(c.CSPF_curr_ref), [], 1);
    h = plot(c.t, 100*c.KCURR_CSPF_ctrl_e ./ I_norm);
    title('KCURR control error [% of max |I_{ref}|]')

    xlabel('t [s]')
    %ylabel('[A]')
    set(h([1 2 3 4 5]), 'LineWidth', 1.7)
    set(hh([1 2 3 4 5]), 'LineWidth', 1.7)
end
legend(circ_names)
% ===== 1) Coil currents v*s reference =====
% the 14 coil currents, taken by name; the KCURR reference is that of the circuit (CS1 for
% CS1U and CS1L, none for VS3U and VS3L, independent in the NICE linearisations)
coil = @(s, name) s.coil_current(:, strcmp(cellstr(string(s.coil_names)), name));
figure('Name', 'Coil currents vs reference');
tiledlayout(4, 4, 'TileSpacing', 'compact');
for k = 1:numel(coil_names)
    nexttile
    hold on
    for i = 1:numel(R)
        h_run(i) = plot(R(i).pfa.time, coil(R(i).pfa, coil_names{k}) / 1e3, 'Color', colors(i,:));
    end
    if coil_circ(k) > 0
        h_ref = plot(t_csv, csv_ctrl.CSPF_curr_ref(:, coil_circ(k)) / 1e3, 'r--');
    end
    h_finit = plot(ref.time, coil(ref, coil_names{k}) / 1e3, 'ko', 'MarkerSize', 4);
    xlim(t_lim); grid on
    title(coil_names{k}); xlabel('t [s]'); ylabel('I [kA]');
    if plot_rms                                % RMS of I - I(t0) from t0 + t_rms, one line per run
        for i = 1:numel(R)
            I_k = coil(R(i).pfa, coil_names{k});
            w = R(i).pfa.time >= R(i).pfa.time(1) + t_rms;
            text(0.02, 0.97 - 0.11*(i-1), sprintf('RMS %.3g A', rms(I_k(w) - I_k(1))), ...
                'Units', 'normalized', 'VerticalAlignment', 'top', 'FontSize', 8, 'Color', colors(i,:));
        end
    end
    if k == 1
        lg = legend([h_run, h_ref, h_finit], [strcat({'measured '}, {R.label}), ...
            {'reference seen by KCURR', 'F\_INIT slices'}]);
        lg.Layout.Tile = 'east';
    end
end

ref_coil_names = cellstr(string(ref.coil_names));
ref_supply_voltage = nan(numel(ref.time), numel(supply_names));
for k = 1:numel(supply_names)
    switch supply_names{k}
        case 'VS1'
            % no coil of its own
        case 'VS3'
            ref_supply_voltage(:, k) = ref.coil_voltage(:, strcmp(ref_coil_names, 'VS3L')) ...
                - ref.coil_voltage(:, strcmp(ref_coil_names, 'VS3U'));
        otherwise
            ref_supply_voltage(:, k) = ref.coil_voltage(:, strcmp(ref_coil_names, supply_names{k}));
    end
end
figure('Name', 'Power-supply voltages');
tiledlayout(4, 4, 'TileSpacing', 'compact');
for k = 1:numel(supply_names)
    nexttile
    hold on
    for i = 1:numel(R)
        h_run(i) = plot(R(i).ctrl.time, R(i).ctrl.supply_voltage(:, k), 'Color', colors(i,:));
    end
    h_finit = plot(ref.time, ref_supply_voltage(:, k), 'ko', 'MarkerSize', 4);
    h_lim = yline([-1 1] * vlim_supply(k), 'r--');
    xlim(t_lim); grid on
    title(supply_names{k}); xlabel('t [s]'); ylabel('V [V]');
end
legend([h_run, h_finit, h_lim(1)], [strcat({'sent by controller '}, {R.label}), ...
    {'F\_INIT reference (from coil voltages)', 'limit'}], 'Location', 'best');

% ===== Zdot seen by the VS controller (simulink_log.csv) =====
figure('Name', 'Zdot');
hold on
for i = 1:numel(R)
    plot(R(i).csv.time, R(i).csv.Zdot, 'Color', colors(i,:));
end
xlim(t_lim); grid on
title('Zdot seen by VS'); xlabel('t [s]'); ylabel('Zdot [m/s]');
legend({R.label}, 'Location', 'best');

% =====Z of the plant (equilibrium of out_plant), deviation from the first sample =====
figure('Name', 'z');
hold on
for i = 1:numel(R)
    plot(R(i).csv.time, 1e3*(R(i).csv.zpl), 'Color', colors(i,:));
end
xlim(t_lim); grid on
title('z of the plant'); xlabel('t [s]'); ylabel('z [mm]');
legend({R.label}, 'Location', 'best');

% ===== R of the plant: boundary geometric axis and magnetic axis =====
% Without RZIp nothing holds R: it follows the radial force balance (beta_pol, li_3) and
% the coil currents.
if all(arrayfun(@(r) isfield(r.eq, 'rgeo') && isfield(r.eq, 'rmag'), R))
    figure('Name', 'R');
    tiledlayout(2, 1, 'TileSpacing', 'compact');
    ax = [nexttile, nexttile];
    hold(ax, 'on');
    for i = 1:numel(R)
        plot(ax(1), R(i).eq.time, per_time(R(i).eq.rgeo, R(i).eq.time), 'Color', colors(i,:));
        plot(ax(2), R(i).eq.time, per_time(R(i).eq.rmag, R(i).eq.time), 'Color', colors(i,:));
    end
    xlim(ax, t_lim); grid(ax, 'on');
    title(ax(1), 'R of the boundary geometric axis'); ylabel(ax(1), 'R_{geo} [m]');
    title(ax(2), 'R of the magnetic axis'); ylabel(ax(2), 'R_{axis} [m]'); xlabel(ax(2), 't [s]');
    legend(ax(1), {R.label}, 'Location', 'best');
end

% ===== Plasma current of the plant (equilibrium of out_plant / out_nice) =====
figure('Name', 'Ip');
hold on
for i = 1:numel(R)
    plot(R(i).eq.time, R(i).eq.ip / 1e6, 'Color', colors(i,:));
end
xlim(t_lim); grid on
title('I_p of the plant'); xlabel('t [s]'); ylabel('I_p [MA]');
legend({R.label}, 'Location', 'best');

% ===== r0, b0 and f exchanged by NICE and TORAX, one figure per run =====
% NICE's r0 is fixed; TORAX writes b0 at the centre of the plasma (R_major), which moves:
% the file keeps a single r0, so it is f / b0 at the boundary. f = r0 b0 at the boundary.
c_nice = [0 0.447 0.741]; c_torax = [0.85 0.325 0.098];
% for i = 1:numel(R)
%     e = R(i).eq;
%     x = R(i).tx;
%     if ~isfield(e, 'f') || ~isfield(x, 'f') || ~isfield(x, 'b0')
%         continue
%     end
%     figure('Name', ['b0, r0, f ' R(i).label]);
%     tiledlayout(3, 1, 'TileSpacing', 'compact');
%     ax = [nexttile, nexttile, nexttile];
%     hold(ax, 'on');
%     plot(ax(1), e.time, per_time(e.r0, e.time), 'Color', c_nice, 'LineWidth', 2.5);
%     plot(ax(1), x.time, per_time(x.f(:, end), x.time) ./ per_time(x.b0, x.time), 'Color', c_torax);
%     plot(ax(2), e.time, abs(per_time(e.b0, e.time)), 'Color', c_nice, 'LineWidth', 2.5);
%     plot(ax(2), x.time, abs(per_time(x.b0, x.time)), 'Color', c_torax);
%     plot(ax(3), e.time, abs(per_time(e.f(:, end), e.time)), 'Color', c_nice, 'LineWidth', 2.5);
%     plot(ax(3), x.time, abs(per_time(x.f(:, end), x.time)), 'Color', c_torax);
%     xlim(ax, t_lim); grid(ax, 'on');
%     title(ax(1), ['r_0, b_0 and f exchanged by NICE and TORAX, ' R(i).label]);
%     ylabel(ax(1), 'r_0 [m]'); ylabel(ax(2), '|b_0| [T]'); ylabel(ax(3), '|f| = r_0 |b_0| [T m]');
%     xlabel(ax(3), 't [s]');
%     legend(ax(1), {'NICE', 'TORAX'}, 'Location', 'best');
% end

% ===== psi at the boundary and loop voltage of NICE and TORAX, one figure per run =====
% psi_b - psi_b(t0) of both codes (the offset between them is removed). NICE's v_loop is
% -dpsi_b/dt, averaged over t_vloop (noisy at a 1 ms step); TORAX's is its own
% core_profiles.global_quantities.v_loop. A mirrored curve means a sign convention difference.
t_vloop = 0.005;      % [s]
for i = 1:numel(R)
    e = R(i).eq;
    x = R(i).tx;
    if ~isfield(e, 'psi_b') || ~isfield(x, 'psi_b')
        continue
    end
    psi_n = per_time(e.psi_b, e.time);
    psi_t = per_time(x.psi_b, x.time);
    v_n = -gradient(psi_n, e.time);
    v_n = movmean(v_n, max(1, round(t_vloop / median(diff(e.time)))));
    figure('Name', ['psi_b, v_loop ' R(i).label]);
    tiledlayout(2, 1, 'TileSpacing', 'compact');
    ax = [nexttile, nexttile];
    hold(ax, 'on');
    plot(ax(1), e.time, psi_n - psi_n(1), 'Color', c_nice, 'LineWidth', 2);
    plot(ax(1), x.time, psi_t - psi_t(1), 'Color', c_torax);
    plot(ax(2), e.time, v_n, 'Color', c_nice, 'LineWidth', 2);
    if isfield(R(i).tcp, 'v_loop')
        plot(ax(2), R(i).tcp.time, -per_time(R(i).tcp.v_loop, R(i).tcp.time), 'Color', c_torax);
    end
    xlim(ax, t_lim); grid(ax, 'on');
    title(ax(1),'\psi at the boundary, NICE and TORAX' );
    ylabel(ax(1), '\psi_b - \psi_b(t_0) [Wb]');
    title(ax(2), sprintf('Loop voltage', 1e3*t_vloop));
    ylabel(ax(2), 'v_{loop} [V]'); xlabel(ax(2), 't [s]');
    legend(ax(1), {'NICE', 'TORAX'}, 'Location', 'best');
end

% ===== Pressure and beta_pol of NICE and TORAX, one figure per run =====
% NICE evo_rd takes p(psi_N) from TORAX's equilibrium at every step: the two profiles must
% coincide (NICE/TORAX = 1), and so must beta_pol. The local NICE develop (fc720054)
% interpolates it as ratio*p(j) + p(j-1), which gives NICE about 1.5 times TORAX's pressure.
n_prof = 4;                                    % profiles shown, spread over the run
cmap = parula(n_prof + 1);                     % one colour per time, without the last (yellow)
for i = 1:numel(R)
    e = R(i).eq;
    x = R(i).tx;
    if ~isfield(e, 'p_1d') || ~isfield(x, 'p_1d')
        continue
    end
    t_show = e.time(round(linspace(1, numel(e.time), n_prof)));
    figure('Name', ['p, beta_pol ' R(i).label]);
    tiledlayout(1, 3, 'TileSpacing', 'compact');
    ax = [nexttile, nexttile, nexttile];
    hold(ax, 'on');
    h_t = gobjects(n_prof, 1);
    for k = 1:n_prof
        [xn, pn] = profile_at(e, 'p_1d', t_show(k));
        [xt, pt] = profile_at(x, 'p_1d', t_show(k));
        if numel(xn) < 2 || numel(xt) < 2
            continue
        end
        h_t(k) = plot(ax(1), xn, pn / 1e3, '-', 'Color', cmap(k,:), 'LineWidth', 2);
        plot(ax(1), xt, pt / 1e3, '--', 'Color', cmap(k,:));
        w = xn <= 0.95;                        % TORAX's p goes to 0 at the edge
        plot(ax(2), xn(w), pn(w) ./ interp1(xt, pt, xn(w)), 'Color', cmap(k,:));
    end
    yline(ax(2), 1, 'k--');
    if isfield(e, 'beta_pol')
        plot(ax(3), e.time, per_time(e.beta_pol, e.time), 'Color', c_nice, 'LineWidth', 2);
    end
    if isfield(R(i).tcp, 'beta_pol')
        plot(ax(3), R(i).tcp.time, per_time(R(i).tcp.beta_pol, R(i).tcp.time), 'Color', c_torax);
    end
    grid(ax, 'on'); xlim(ax(3), t_lim);
    title(ax(1), ['p: NICE solid, TORAX dashed, ' R(i).label]);
    xlabel(ax(1), '\psi_N'); ylabel(ax(1), 'p [kPa]');
    shown = isgraphics(h_t);
    if any(shown)
        legend(ax(1), h_t(shown), compose('t = %.3f s', t_show(shown)), 'Location', 'best');
    end
    title(ax(2), 'p_{NICE} / p_{TORAX}'); xlabel(ax(2), '\psi_N');
    title(ax(3), '\beta_{pol}'); xlabel(ax(3), 't [s]');
    legend(ax(3), {'NICE', 'TORAX'}, 'Location', 'best');
end

% ===== q, j_phi and li_3 of NICE and TORAX, one figure per run =====
% These follow psi. With TORAX's evolve_current False its psi is prescribed (the
% inverse_convergence trajectory) and is not NICE's: a difference here comes from that
% choice, not from the coupling. Absolute values, as the codes can differ in sign.
for i = 1:numel(R)
    e = R(i).eq;
    x = R(i).tx;
    if ~isfield(e, 'q_1d') || ~isfield(x, 'q_1d')
        continue
    end
    t_show = e.time(round(linspace(1, numel(e.time), n_prof)));
    figure('Name', ['q, j, li ' R(i).label]);
    tiledlayout(1, 3, 'TileSpacing', 'compact');
    ax = [nexttile, nexttile, nexttile];
    hold(ax, 'on');
    h_t = gobjects(n_prof, 1);
    for k = 1:n_prof
        [xn, qn] = profile_at(e, 'q_1d', t_show(k));
        [xt, qt] = profile_at(x, 'q_1d', t_show(k));
        h_t(k) = plot(ax(1), xn, abs(qn), '-', 'Color', cmap(k,:), 'LineWidth', 2);
        plot(ax(1), xt, abs(qt), '--', 'Color', cmap(k,:));
        if isfield(e, 'j_1d') && isfield(x, 'j_1d')
            [xn, jn] = profile_at(e, 'j_1d', t_show(k));
            [xt, jt] = profile_at(x, 'j_1d', t_show(k));
            plot(ax(2), xn, abs(jn) / 1e6, '-', 'Color', cmap(k,:), 'LineWidth', 2);
            plot(ax(2), xt, abs(jt) / 1e6, '--', 'Color', cmap(k,:));
        end
    end
    if isfield(e, 'li_3')
        plot(ax(3), e.time, per_time(e.li_3, e.time), 'Color', c_nice, 'LineWidth', 2);
    end
    if isfield(R(i).tcp, 'li_3')
        plot(ax(3), R(i).tcp.time, per_time(R(i).tcp.li_3, R(i).tcp.time), 'Color', c_torax);
    end
    grid(ax, 'on'); xlim(ax(3), t_lim);
    title(ax(1), ['|q|: NICE solid, TORAX dashed, ' R(i).label]); xlabel(ax(1), '\psi_N');
    legend(ax(1), h_t, compose('t = %.3f s', t_show), 'Location', 'best');
    title(ax(2), '|j_\phi| [MA/m^2]'); xlabel(ax(2), '\psi_N');
    title(ax(3), 'l_{i,3}'); xlabel(ax(3), 't [s]');
    legend(ax(3), {'NICE', 'TORAX'}, 'Location', 'best');
end

% ===== Local functions (must stay at the end of the script) =====

function data = read_h5_signals(file, time_path, signals)
    % Reads a list of signals from an IMAS HDF5 file into a struct.
    fprintf('\nReading %s\n', file);

    data = struct();
    data.time = double(h5read(file, time_path));
    data.time = data.time(:);
    nt = numel(data.time);
    fprintf('  %-15s %s\n', 'time', mat2str(size(data.time)));

    for k = 1:size(signals, 1)
        name = signals{k, 1};
        path = signals{k, 2};

        try
            x = h5read(file, path);
        catch err
            warning('Skipped "%s": cannot read %s\n  %s', name, path, err.message);
            continue
        end

        data.(name) = clean_imas(x, nt);
        fprintf('  %-15s %s\n', name, mat2str(size(data.(name))));
    end
end

function path = supply_voltage_path(file)
    % The controller sends the 14 supply voltages in pf_active.supply since 2026-11-03;
    % before then it sent supply k in coil slot k.
    info = h5info(file, '/pf_active');
    if any(strcmp({info.Datasets.Name}, 'supply[]&voltage&data'))
        path = '/pf_active/supply[]&voltage&data';
    else
        path = '/pf_active/coil[]&voltage&data';
    end
end

function data = read_csv_signals(file)
    % Reads the CSV into a struct. Columns like name_1, name_2, ... are grouped into one matrix.
    fid = fopen(file, 'r');
    headers = strsplit(strtrim(fgetl(fid)), ',');
    fclose(fid);

    M = readmatrix(file, 'NumHeaderLines', 1);
    base = regexprep(headers, '_\d+$', '');
    [names, ~, idx] = unique(base, 'stable');

    data = struct();
    data.time = M(:, 1);
    for k = 1:numel(names)
        field = matlab.lang.makeValidName(names{k});
        data.(field) = M(:, idx == k);
    end
end

function x = clean_imas(x, nt)
    % Converts to double, replaces IMAS empty values with NaN, puts time on rows.
    %x = double(x);
    %x(x < -1e40) = NaN;            % IMAS "empty" value is -9e40

    if isvector(x)
        x = x(:);                  % always a column vector
    elseif size(x, 2) == nt && size(x, 1) ~= nt
        x = x.';                   % MATLAB reads HDF5 with dimensions reversed
    end
end
function d = first_folder(root, names)
    % the first of root/names{k} that exists (the first name when none does)
    d = fullfile(root, names{1});
    for k = 1:numel(names)
        if isfolder(fullfile(root, names{k}))
            d = fullfile(root, names{k});
            return
        end
    end
end

function [psin, v] = profile_at(s, name, t)
    % profile `name` of the slice of s nearest to t, against the normalized poloidal flux
    [~, k] = min(abs(s.time - t));
    psi = s.psi_1d(k, :);
    v = s.(name)(k, :);
    ok = isfinite(psi) & isfinite(v) & psi > -1e40 & v > -1e40;
    psi = psi(ok);
    v = v(ok);
    if numel(psi) < 2
        psin = [];
        v = [];
        return
    end
    psin = (psi - psi(1)) / (psi(end) - psi(1));
end

function v = per_time(v, t)
    % one value per time: a value stored once is repeated; a file read while the run writes
    % it can have one more or one less sample than time (cut, or padded with NaN)
    v = v(:);
    n = numel(t);
    if isscalar(v)
        v = repmat(v, n, 1);
    elseif numel(v) >= n
        v = v(1:n);
    else
        v(end+1:n) = NaN;
    end
end
