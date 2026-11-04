function [total_cmd] = controller_output_preprocess(cspfout, vs1out, vs3out)
% Controller outputs -> the 14 voltages of pfa.supply{i}.voltage, power-supply order
% (as NICE evolutive reads them): [CS3U CS2U CS1U CS1L CS2L CS3L PF1..PF5 VS1 PF6 VS3].
% CS1 (one circuit, two coils) is split in half on CS1U and CS1L.


cspf_cmd = [cspfout(1:2); cspfout(3)/2; cspfout(3)/2; cspfout(4:11)];

total_cmd = [cspf_cmd(1:11); vs1out; cspf_cmd(12); vs3out];
total_cmd = [cspf_cmd(1:11); vs1out; cspf_cmd(12); vs3out];
if evalin('base','nice_signs')
    total_cmd= -total_cmd;
end



