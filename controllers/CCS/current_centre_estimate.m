function [rc, zc, source] = current_centre_estimate(ts)
% Current centre (R, Z) of an equilibrium time slice, for codes that leave
% global_quantities.current_centre empty (NICE): the j_phi-weighted centroid of the
% current density on NICE's mesh (ggd j_phi on the nodes ggd r, z), linear on the
% triangles of the nodes' Delaunay triangulation, computed once per mesh. Its integral is
% Ip within ~1 %. source is 'ggd', or '' with NaN when the slice has no mesh data.

[rc, zc] = centre_from_ggd(ts);
source = 'ggd';
if isnan(zc)
    source = '';
end
end


function [rc, zc] = centre_from_ggd(ts)
persistent nodes tri area rm zm     % triangulation of the last mesh seen
rc = NaN;
zc = NaN;
if ~isfield(ts, 'ggd') || isempty(ts.ggd)
    return
end
g = first(ts.ggd);
j = ggd_values(g, 'j_phi');
r = ggd_values(g, 'r');
z = ggd_values(g, 'z');
n = numel(j);
if n < 3 || numel(r) ~= n || numel(z) ~= n || ~all(isfinite([r; z]))
    return
end
if ~isequal(nodes, [r z])
    nodes = [r z];
    tri = delaunay(r, z); %extract mesh triangles
    %x and y positions for the mesh triangles
    x = r(tri); 
    y = z(tri);
    area = abs((x(:,2) - x(:,1)).*(y(:,3) - y(:,1)) - (x(:,3) - x(:,1)).*(y(:,2) - y(:,1)))/2;
    rm = mean(x, 2);
    zm = mean(y, 2);
end
j(~isfinite(j) | abs(j) > 1e30) = 0;

%Zc = int(j_phi*z*dS)/Ip
%Rc = int(j_phi*r*dS)/Ip

dI = mean(j(tri), 2).*area; % current in each triangle
Ip = sum(dI);
if sum(dI) ~= 0
    rc = sum(rm.*dI)/Ip;
    zc = sum(zm.*dI)/Ip;
end
end


function v = ggd_values(g, name)
v = [];
if isfield(g, name) && ~isempty(g.(name))
    q = first(g.(name));
    if isfield(q, 'values')
        v = double(q.values(:));
    end
end
end


function x = first(aos)
if iscell(aos)
    x = aos{1};
else
    x = aos(1);
end
end
