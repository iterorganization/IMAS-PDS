% Closed-loop runs of the CCS controller: plasma current and position, gaps, coil currents,
% KCURR error and power-supply voltages. Several runs are overlaid, one colour per run; the
% poloidal section is that of the first run. Measured values come from the plant (out_nice),
% references and what the controller saw from simulink_log.csv. Set run_dir and run  plot_run

close all
clc
clear

run_dir = {'/home/ITER/centong/Desktop/PDSs/IMAS-PDS-torax/cases/runs/evolutive_controller_105073_20261110_210958',
    '/home/ITER/centong/Desktop/PDSs/IMAS-PDS-torax/cases/runs/evolutive_controller_105073_20261113_100036'};

t_section = [];                    % time of the poloidal section [s], [] = last slice of the first run
GAP_LIST  = [3 8 15 21 25 48];     % as in muscle_controller_NICE_IMAS_iter_init.m: gaps_1..6 of the csv

ts = '/equilibrium/time_slice[]&';
eq_signals = {
    'ip',    [ts 'global_quantities&ip']
    'r_cc',  [ts 'global_quantities&current_centre&r']
    'z_cc',  [ts 'global_quantities&current_centre&z']
    'psi_b', [ts 'boundary&psi']
};
pfa_signals = {
    'coil_current', '/pf_active/coil[]&current&data'
    'coil_names',   '/pf_active/coil[]&name'
};

% read every run
run_dirs = cellstr(run_dir);
for i = 1:numel(run_dirs)
    rd = strip(run_dirs{i}, 'right', '/');
    [runs_dir, run_name] = fileparts(rd);
    case_name = regexprep(run_name, '_\d{8}_\d{6}.*$', '');
    R(i).case_dir = fullfile(fileparts(runs_dir), case_name);
    R(i).label = strrep(erase(run_name, [case_name '_']), '_', '\_');
    R(i).csv  = read_csv_signals(fullfile(rd, 'simulink_log.csv'));
    plant_dir = first_folder(rd, {'out_nice', 'out_plant'});
    R(i).eq_file = fullfile(plant_dir, 'equilibrium.h5');
    R(i).eq   = read_h5_signals(R(i).eq_file, '/equilibrium/time', eq_signals);
    R(i).pfa  = read_h5_signals(fullfile(plant_dir, 'pf_active.h5'), '/pf_active/time', pfa_signals);
    R(i).ctrl = read_h5_signals(fullfile(rd, 'out_controller', 'pf_active.h5'), '/pf_active/time', ...
        {'supply_voltage', '/pf_active/supply[]&voltage&data'});        % voltages sent by the controller
    if abs(R(i).csv.time(end) - R(i).pfa.time(end)) > 0.01
        warning('%s: simulink_log.csv ends at t = %.3f s but the run at %.3f s: it is from another run', ...
            run_name, R(i).csv.time(end), R(i).pfa.time(end));
    end
end
colors = lines(numel(R));
t_lim = [min(arrayfun(@(r) r.csv.time(1), R)), max(arrayfun(@(r) r.csv.time(end), R))];

% ===== Constants =====
% the 11 KCURR circuits (columns of KCURR_actual_ref and KCURR_CSPF_ctrl_e)
circ_names = {'CS3U','CS2U','CS1','CS2L','CS3L','PF1','PF2','PF3','PF4','PF5','PF6'};
% the 14 coils of pf_active and the KCURR circuit of each (0 = none)
coil_names = {'CS3U','CS2U','CS1U','CS1L','CS2L','CS3L','PF1','PF2','PF3','PF4','PF5','PF6','VS3U','VS3L'};
coil_circ  = [1 2 3 3 4 5 6 7 8 9 10 11 0 0];
% the 14 power supplies (pf_active.supply of out_controller) and their voltage limits
supply_names = {'CS3U','CS2U','CS1U','CS1L','CS2L','CS3L','PF1','PF2','PF3','PF4','PF5','VS1','PF6','VS3'};
vlim_supply  = [2100 2100 2100 2100 2100 2100 2100 3150 3150 3150 3150 6300 2100 2400];

% ===== Plasma: Ip and current centre of the plant (solid), controller references (dashed) =====
figure('Name', 'Plasma');
tiledlayout(4, 1, 'TileSpacing', 'compact');
ax = [nexttile, nexttile, nexttile, nexttile];
hold(ax, 'on');
h_run = gobjects(1, numel(R));
for i = 1:numel(R)
    e = R(i).eq;
    c = R(i).csv;
    h_run(i) = plot(ax(1), e.time, per_time(e.ip, e.time) / 1e6, 'Color', colors(i,:));
    plot(ax(1), c.time, c.Ip_ref / 1e6, '--', 'Color', colors(i,:));
    if isfield(e, 'z_cc')
        plot(ax(2), e.time, 1e3 * per_time(e.z_cc, e.time), 'Color', colors(i,:));
        plot(ax(3), e.time, per_time(e.r_cc, e.time), 'Color', colors(i,:));
    end
    plot(ax(2), c.time, 1e3 * c.Z_ref, '--', 'Color', colors(i,:));
    plot(ax(3), c.time, c.R_ref, '--', 'Color', colors(i,:));
    plot(ax(4), c.time, c.Zdot, 'Color', colors(i,:));
end
xlim(ax, t_lim); grid(ax, 'on'); linkaxes(ax, 'x');
title(ax(1), 'I_p: plant solid, reference dashed'); ylabel(ax(1), 'I_p [MA]');
title(ax(2), 'Z of the current centre');            ylabel(ax(2), 'Z [mm]');
title(ax(3), 'R of the current centre');            ylabel(ax(3), 'R [m]');
title(ax(4), 'Zdot seen by VS');                    ylabel(ax(4), 'dZ/dt [m/s]');
xlabel(ax(4), 't [s]');
lg = legend(ax(1), h_run, {R.label});
lg.Layout.Tile = 'east';

% ===== Gaps: poloidal section of the first run, and each controlled gap against its reference =====
% The section shows the plant at t_section: boundary.gap written by the diagnostics actor,
% from the wall point of each line to the separatrix, a tick where the separatrix should cross
% (the reference the controller tracked) and both values in the labels. At this scale a few mm
% are not visible: read the labels. The traces show what the controller saw (gaps) and what it
% tracked (gaps_ref), both from simulink_log.csv.
e1 = R(1).eq;
if ~has_dataset(R(1).eq_file, '/equilibrium', 'time_slice[]&boundary&gap[]&value')
    warning('%s: no boundary.gap in the plant equilibrium (run without the diagnostics actor): no gap figure', ...
        R(1).label);
else
    if isempty(t_section)
        t_section = e1.time(end);
    end
    [~, k] = min(abs(e1.time - t_section));
    t_k = e1.time(k);

    % plasma boundary and gap lines at slice k; the DD angle is clockwise, theta counter-clockwise from +R
    out_r = slice_of(R(1).eq_file, [ts 'boundary&outline&r'], k);
    out_z = slice_of(R(1).eq_file, [ts 'boundary&outline&z'], k);
    ok = isfinite(out_r) & isfinite(out_z);
    out_r = out_r(ok);
    out_z = out_z(ok);
    g_r   = slice_of(R(1).eq_file, [ts 'boundary&gap[]&r'], k);
    g_z   = slice_of(R(1).eq_file, [ts 'boundary&gap[]&z'], k);
    theta = -slice_of(R(1).eq_file, [ts 'boundary&gap[]&angle'], k);
    gap   = slice_of(R(1).eq_file, [ts 'boundary&gap[]&value'], k);   % NaN where not found
    sep_r = g_r + gap .* cos(theta);                                  % where each line meets the separatrix
    sep_z = g_z + gap .* sin(theta);

    % reference of the controlled gaps at t_k: what the controller tracked (NaN if not logged)
    g_ref = nan(size(gap));
    if isfield(R(1).csv, 'gaps_ref')
        [~, kc] = min(abs(R(1).csv.time - t_k));
        g_ref(GAP_LIST) = R(1).csv.gaps_ref(kc, :);
    end
    ref_r = g_r + g_ref .* cos(theta);                                % where the separatrix should be
    ref_z = g_z + g_ref .* sin(theta);

    % first wall: first wall + divertor outlines, which together close the vessel
    wall_file = fullfile(first_folder(fullfile(R(1).case_dir, 'preprocess'), {'in', 'initial_state', 'dina_in'}), 'wall.h5');
    wr = h5read(wall_file, '/wall/description_2d[]&limiter&unit[]&outline&r');
    wz = h5read(wall_file, '/wall/description_2d[]&limiter&unit[]&outline&z');
    valid = abs(wr) < 1e30;                                           % -9e40 = IMAS empty
    wall_r = [wr(valid(:, 1), 1); wr(valid(:, 2), 2); wr(1, 1)];
    wall_z = [wz(valid(:, 1), 1); wz(valid(:, 2), 2); wz(1, 1)];

    % separatrix with its legs (where the divertor gaps end): psi = psi_b on NICE's mesh, linear
    % on the triangles of the nodes as in the diagnostics actor, on a 2 cm grid inside the first
    % wall (the mesh is much larger than the vessel)
    m_r   = slice_of(R(1).eq_file, [ts 'ggd[]&r[]&values'], k);
    m_z   = slice_of(R(1).eq_file, [ts 'ggd[]&z[]&values'], k);
    m_psi = slice_of(R(1).eq_file, [ts 'ggd[]&psi[]&values'], k);
    ok = isfinite(m_r) & isfinite(m_z) & isfinite(m_psi);
    F = scatteredInterpolant(m_r(ok), m_z(ok), m_psi(ok), 'linear', 'none');
    [RR, ZZ] = meshgrid(min(wall_r):0.02:max(wall_r), min(wall_z):0.02:max(wall_z));
    PSI = F(RR, ZZ);
    PSI(~inpolygon(RR, ZZ, wall_r, wall_z)) = NaN;

    figure('Name', 'Gaps', 'Units', 'normalized', 'Position', [0.1 0.05 0.6 0.85]);
    n_gaps = numel(GAP_LIST);
    tiledlayout(n_gaps, 3, 'TileSpacing', 'compact');

    ax_s = nexttile(1, [n_gaps 2]);                                   % section: first two columns
    hold(ax_s, 'on'); box(ax_s, 'on');
    h = gobjects(1, 7);
    h(1) = plot(ax_s, wall_r, wall_z, 'Color', '#52514e', 'LineWidth', 1.5);
    h(2) = patch(ax_s, 'XData', out_r, 'YData', out_z, 'FaceColor', '#2a78d6', 'FaceAlpha', 0.12, ...
                 'EdgeColor', 'none');
    [~, h(3)] = contour(ax_s, RR, ZZ, PSI, [1 1] * e1.psi_b(k), 'LineColor', '#2a78d6', 'LineWidth', 1);
    others = setdiff(find(isfinite(gap)), GAP_LIST);
    if ~isempty(others)
        h_other = plot(ax_s, [g_r(others) sep_r(others)]', [g_z(others) sep_z(others)]', ...
                       'Color', '#c3c2b7', 'LineWidth', 0.75);
        h(6) = h_other(1);
    end
    for j = GAP_LIST
        h(4) = plot(ax_s, [g_r(j) sep_r(j)], [g_z(j) sep_z(j)], 'Color', '#eb6834', 'LineWidth', 2.5);
        plot(ax_s, g_r(j), g_z(j), 'o', 'MarkerSize', 5, 'MarkerEdgeColor', '#eb6834', 'MarkerFaceColor', '#eb6834');
        if isfinite(g_ref(j))                                         % tick across the line at the reference
            p = 0.1 * [-sin(theta(j)) cos(theta(j))];
            h(5) = plot(ax_s, ref_r(j) + [-1 1]*p(1), ref_z(j) + [-1 1]*p(2), 'Color', '#0b0b0b', 'LineWidth', 1.5);
        end
        % label outside the wall, behind the start point, on the side away from the gap line
        d = [cos(theta(j)) sin(theta(j))];
        ha = 'center';  va = 'middle';
        if d(1) > 0.5,  ha = 'right';  elseif d(1) < -0.5,  ha = 'left';    end
        if d(2) > 0.5,  va = 'top';    elseif d(2) < -0.5,  va = 'bottom';  end
        label = sprintf('GAP%02d\n%.1f cm (ref %.1f)', j, 100*gap(j), 100*g_ref(j));
        text(ax_s, g_r(j) - 0.15*d(1), g_z(j) - 0.15*d(2), label, 'Color', '#0b0b0b', 'FontSize', 9, ...
             'HorizontalAlignment', ha, 'VerticalAlignment', va, 'BackgroundColor', 'w', 'Margin', 1);
    end
    h(7) = plot(ax_s, e1.r_cc(k), e1.z_cc(k), '+', 'Color', '#0b0b0b', 'MarkerSize', 10, 'LineWidth', 1.5);
    axis(ax_s, 'equal');
    axis(ax_s, [2.2 10.5 -5.0 5.4]);                                 % room for the labels outside the wall
    xlabel(ax_s, 'R [m]'); ylabel(ax_s, 'Z [m]');
    title(ax_s, sprintf('%s, t = %.3f s: gap now, black tick at its reference', R(1).label, t_k));
    names = {'first wall', 'plasma', 'separatrix', 'controlled gaps', 'gap reference', 'other gaps', 'current centre'};
    shown = isgraphics(h);
    lg = legend(ax_s, h(shown), names(shown), 'NumColumns', 4);
    lg.Layout.Tile = 'south';

    ax_g = gobjects(1, n_gaps);                                       % traces: third column
    h_gap = gobjects(1, numel(R));
    for n = 1:n_gaps
        ax_g(n) = nexttile(3*n);
        hold(ax_g(n), 'on');
        for i = 1:numel(R)
            c = R(i).csv;
            if isfield(c, 'gaps')
                h_gap(i) = plot(ax_g(n), c.time, 100 * c.gaps(:, n), 'Color', colors(i,:));
            end
            if isfield(c, 'gaps_ref')
                plot(ax_g(n), c.time, 100 * c.gaps_ref(:, n), '--', 'Color', colors(i,:));
            end
        end
        xline(ax_g(n), t_k, ':', 'Color', '#898781');                % time of the section
        grid(ax_g(n), 'on');
        ylabel(ax_g(n), sprintf('GAP%02d [cm]', GAP_LIST(n)));
        if n == 1 && numel(R) > 1
            shown = isgraphics(h_gap);
            lg = legend(ax_g(1), h_gap(shown), {R(shown).label});
            lg.Layout.Tile = 'east';
        end
    end
    xlim(ax_g, t_lim); linkaxes(ax_g, 'x');
    title(ax_g(1), 'seen by the controller, reference dashed');
    xlabel(ax_g(end), 't [s]');
end

% ===== Coil currents of the plant (solid) and the reference KCURR tracks (dashed) =====
% CS1U and CS1L share the CS1 reference, VS3U and VS3L have none; the reference moves with the Ip control
coil = @(s, name) s.coil_current(:, strcmp(cellstr(string(s.coil_names)), name));
figure('Name', 'Coil currents');
tiledlayout(4, 4, 'TileSpacing', 'compact');
h_ref = gobjects(1, numel(R));
for k = 1:numel(coil_names)
    nexttile
    hold on
    for i = 1:numel(R)
        h_run(i) = plot(R(i).pfa.time, coil(R(i).pfa, coil_names{k}) / 1e3, 'Color', colors(i,:));
        if coil_circ(k) > 0
            h_ref(i) = plot(R(i).csv.time, R(i).csv.KCURR_actual_ref(:, coil_circ(k)) / 1e3, '--', ...
                'Color', colors(i,:));
        end
    end
    xlim(t_lim); grid on
    title(coil_names{k}); ylabel('I [kA]');
    if k == 1
        lg = legend([h_run, h_ref], [strcat({'plant '}, {R.label}), strcat({'KCURR reference '}, {R.label})]);
        lg.Layout.Tile = 'east';
    end
end
xlabel('t [s]');

% ===== KCURR control error of each circuit =====
figure('Name', 'KCURR error');
tiledlayout(3, 4, 'TileSpacing', 'compact');
for k = 1:numel(circ_names)
    nexttile
    hold on
    for i = 1:numel(R)
        h_run(i) = plot(R(i).csv.time, R(i).csv.KCURR_CSPF_ctrl_e(:, k), 'Color', colors(i,:));
    end
    xlim(t_lim); grid on
    title(circ_names{k}); ylabel('e [A]');
    if k == 1
        lg = legend(h_run, {R.label});
        lg.Layout.Tile = 'east';
    end
end
xlabel('t [s]');

% ===== Power-supply voltages sent by the controller, with their limits =====
figure('Name', 'Supply voltages');
tiledlayout(4, 4, 'TileSpacing', 'compact');
for k = 1:numel(supply_names)
    nexttile
    hold on
    for i = 1:numel(R)
        h_run(i) = plot(R(i).ctrl.time, R(i).ctrl.supply_voltage(:, k), 'Color', colors(i,:));
    end
    h_lim = yline([-1 1] * vlim_supply(k), 'r--');
    xlim(t_lim); grid on
    title(supply_names{k}); ylabel('V [V]');
    if k == 1
        lg = legend([h_run, h_lim(1)], [{R.label}, {'limit'}]);
        lg.Layout.Tile = 'east';
    end
end
xlabel('t [s]');

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

function v = slice_of(file, path, k)
    % Time slice k of an IMAS dataset (time is its last dimension in MATLAB) as a column,
    % without reading the other slices.
    info = h5info(file, path);
    n = info.Dataspace.Size;       % in the order of h5read: [values, (1, 1,) time]
    v = double(h5read(file, path, [ones(1, numel(n) - 1) k], [n(1) ones(1, numel(n) - 1)]));
    v = v(:);
    v(v < -1e30) = NaN;            % IMAS "empty" value is -9e40
end

function tf = has_dataset(file, group, name)
    info = h5info(file, group);
    tf = any(strcmp({info.Datasets.Name}, name));
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
    % Numbers as double with the IMAS empty value as NaN, time on rows.
    if isnumeric(x)
        x = double(x);
        x(x < -1e30) = NaN;        % IMAS "empty" value is -9e40
    end
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

function v = per_time(v, t)
    % one value per time: a file read while the run writes it can have one more or one less
    % sample than time (cut, or padded with NaN)
    v = v(:);
    n = numel(t);
    if numel(v) >= n
        v = v(1:n);
    else
        v(end+1:n) = NaN;
    end
end
