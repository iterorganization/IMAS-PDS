function [Rsepa_out,Zsepa_out] = metis4muscle3_resize_LCFS(Rsepa,Zsepa,nbpts)
% PDS override of the METIS copy of this file, on the MATLAB path ahead of
% $DIR_METIS4MUSCLE3. See the comment on the thc filter below. Remove once fixed upstream.

% initialisation
Rsepa_out = NaN * ones(size(Rsepa,1),nbpts);
Zsepa_out = NaN * ones(size(Zsepa,1),nbpts);
uni       =  linspace(0, 2.* pi,nbpts)';

% loop on time slices
for k= 1:size(Rsepa,1)
    
	% extraction de la sepa
	r = Rsepa(k,:);
	z = Zsepa(k,:);
	r = r(:);
	z = z(:);
    indbad = find(r <= 0);
    if ~isempty(indbad)
        r(indbad) = [];
        z(indbad) = [];
    end
% 	KH = sort(unique(convhull(r,z)));
% 	if (length(KH) ~= length(r))
% 	    index_full = 1:length(r);
% 	    r = r(KH);
% 	    z = z(KH);
% 	    r = interp1(KH,r,index_full,'linear');
% 	    z = interp1(KH,z,index_full,'linear');
% 	    indbad_lcfs = find(~isfinite(r) | ~isfinite(z));
% 	    if ~isempty(indbad_lcfs)
% 		r(indbad_lcfs) = [];
% 		z(indbad_lcfs) = [];
% 	    end
% 	    r = r(:);
% 	    z = z(:);
% 	end

	r0   = (min(r) + max(r)) ./ 2;
	%mask    = (r == max(r));
	%z0   = sum(z .* mask) ./ max(1,sum(mask));
	z0   = (min(z) + max(z)) ./ 2;
	cc   = (r - r0) + sqrt(-1) .* (z - z0);
	thc  = unwrap(angle(cc));
	thc(thc <0) = thc(thc<0) + 2 .* pi;
	rhoc = abs(cc);
	[thc,indc] = sort(thc);
	rhoc       = rhoc(indc);
	rhoc = cat(1,rhoc,rhoc,rhoc);
	thc = cat(1,thc -2.*pi,thc,thc+2.*pi);
	% Keep a strictly increasing thc. The original did one pass of
	% `indnok = find(diff(thc)<=0)` and deleted those indices, which drops the EARLIER
	% element of each non-increasing pair and never re-checks: on a theta sequence that
	% backtracks, e.g. [1 2 1 2], it leaves [1 1 2] and spline() rejects the duplicate.
	% A running-maximum filter gives the postcondition the original was reaching for.
	keep = false(size(thc));
	last = -Inf;
	for kk = 1:numel(thc)
		if thc(kk) > last
			keep(kk) = true;
			last = thc(kk);
		end
	end
	ndrop = numel(thc) - sum(keep) - 2;   % 2 duplicates are expected at the +-2pi joins
	if ndrop > 0
		fprintf('METIS4MUSCLE3: resize_LCFS dropped %d non-monotonic boundary point(s)\n',ndrop);
	end
	thc = thc(keep);
	rhoc = rhoc(keep);
	rho = spline(thc,rhoc,uni); 
    
    
    % new LCFS for METIS
	Rsepa_out(k,:) = (r0 + rho .* cos(uni)).';
	Zsepa_out(k,:) = (z0 + rho .* sin(uni)).';
end

%figure(21);clf;plot(Rsepa_out,Zsepa_out,'b',Rsepa,Zsepa,'.r');drawnow

