%____________________________________________________________________%
%  PARSEXML Convert XML file to a MATLAB structure                   %
%                                                                    %
%  Developed in MATLAB R2023b                                        %
%                                                                    %
%  Author: [redacted]
%                                                                    %
%         e-Mail: [redacted]
%                                                                    %
%   Version: 1.0                                                     %
%   Modification, date: 16.7.24                                      %
%   Modification, author: [redacted]
% copyright 2024 by Max-Planck Institute for Plasmaphysics, Garching %
%                                                                    %
%____________________________________________________________________%

function [ParMatrix, OutMatrix, SegMatrix, SupMatrix, InMatrix] = parsePSXML(filename)
    % PARSEXML Convert XML file to a MATLAB structure.
    %filename='./assets/ne_testBT.xml';
    %filename='./assets/samplefile.xml';
    SIGNALNAME = 1;     % Index used for the variable name in all the four arrays used here
    DATATYPE = 2;       % Index for the data type used in the Parameter and Output cell array
    VALUE = 3;          % Index of the value for the parameters
    SIGNALTYPE = 3;     % Index for the output signal type
    DESCRIP = 4;        % Index for outyput signal description
    SEGID = 2;          % Index for the Segment Index
    SEGNAME = 3;        % Index for segment name in the segment table
    TRAJID = 4;         % Index for trajectory definition for a certain signal at a certain segment
    SCALEID = 5;        % Index for scale definition for a certain signal at a certain segment
    OFFSETID = 6;       % Index for offset definition for a certain signal at a certain segment
    EXECTYPE = 7;       % Index for the signal execution type
    TARGETTYPEID = 3;
    TARGETSEG = 5;
    
    try
       tree = xmlread(filename);
    catch ME
       error(['Failed to read XML file %s.' filename  '\n' ME.message]);
    end
    % Recurse over child nodes. This could run into problems 
     %with very deeply nested trees.
    try
       theStruct = parseChildNodes(tree);
    catch
       error('Unable to parse XML file %s.',filename);
    end
    [ParMatrix, OutMatrix, SegMatrix, SupMatrix, InMatrix]=convert2matrix(theStruct);
end

function strchildren = parseChildNodes(theNode)
    % Recurse over node children.
    strchildren = [];
    if theNode.hasChildNodes
       parentNode=char(theNode.getNodeName);
       childNodes = theNode.getChildNodes;
       numChildNodes = childNodes.getLength;
       allocCell = cell(1, numChildNodes);
        matchildren=[];
      strchildren = struct(             ...
          'Name', [], 'Attributes', [],    ...
          'Children', []);
        childrenindex=1;
        for count = 1:numChildNodes
            theChild = childNodes.item(count-1);
            if ~strcmp(char(theChild.getNodeName),'#text') && ~strcmp(char(theChild.getNodeName),'#comment')
                strchildren(childrenindex) = makeStructFromNode(theChild);
                childrenindex=childrenindex+1;
            end
        end

    end
end

function [ParMatrix, OutMatrix, SegMatrix, SupMatrix, InMatrix]=convert2matrix(Struct)
    % merge subtrees
    % extract trees and convert to matrix
    %NodeName=Struct.Attributes.Value;
    % check the number of behavior trees in the file. It could be that some
    % node corresponds to a new palette element

    count=1;
    ParMatrix = cell(0, 3);
    OutMatrix = cell(0, 4);
    SegMatrix = cell(0, 7);     % <segmentName>|<segmentID>|<signalName>|<trajectoryDef>|<Interpolation>|<typeend>
    SupMatrix = cell(0, 6);
    InMatrix = cell(0, 4);
    DeclarationsIdx = 0;
    SegmentsIdx = 0;
    for i=1:numel(Struct.Children)
        if strcmp(Struct.Children(i).Name,'DECLARATIONS')
            DeclarationsIdx = i;
        elseif strcmp(Struct.Children(i).Name,'SEGMENTS')
            SegmentsIdx = i;
        end
    end
    if DeclarationsIdx > 0
        % extract parameters and outputs
        childrenElem = Struct.Children(DeclarationsIdx).Children;
        for j = 1:numel(childrenElem)
            if strcmp(childrenElem(j).Name,'PARAMETERS')
                ParaStruct = childrenElem(j);
                ParMatrix = extractParameters(ParMatrix, ParaStruct);
                ListParams = ParMatrix(:,1);
            elseif strcmp(childrenElem(j).Name,'OUTPUTS')
                OutputsStruct = childrenElem(j);
                OutMatrix = extractOutputs(OutMatrix, OutputsStruct);
            elseif strcmp(childrenElem(j).Name,'INPUTS')
                InputsStruct = childrenElem(j);
                if ~isempty(InputsStruct.Children)
                    InMatrix = extractOutputs(InMatrix, InputsStruct);
                end
            end
        end
    end

   if SegmentsIdx > 0
        % extract segments
        childrenElem = Struct.Children(SegmentsIdx).Children;
        for j = 1:numel(childrenElem)
            try 
                [SegMatrix, SupMatrix] = extractSegments(SegMatrix, SupMatrix,childrenElem(j),OutMatrix, ParMatrix, ListParams);
            catch ME
                rethrow(ME)
            end
        end
        % -----------------------------------
        % TODO: Extract the list of segments with the id
        % TODO: Replace the name of the target segments for their IDs
        % -----------------------------------
   end
end
%%
function theMatrix = extractOutputs(theMatrix, theStruct)
    numPar = numel(theStruct.Children);
    % check if the struct has no values
    if numPar == 1
        if isempty(theStruct.Children(1).Name)
            return
        end
    end
    for i=1:numPar
        numberAtt=numel(theStruct.Children(i).Attributes);
        LastElem=size(theMatrix,1)+1;
        theMatrix{LastElem,5} = 1;
        for j=1:numberAtt
            if strcmp(theStruct.Children(i).Attributes(j).Name,'name')
                theMatrix{LastElem,1} = theStruct.Children(i).Attributes(j).Value;
            elseif strcmp(theStruct.Children(i).Attributes(j).Name,'signal_type')
                theMatrix{LastElem,2} = theStruct.Children(i).Attributes(j).Value;
            elseif strcmp(theStruct.Children(i).Attributes(j).Name,'type')
                theMatrix{LastElem,3} = strrep(theStruct.Children(i).Attributes(j).Value,'_t','');
            elseif strcmp(theStruct.Children(i).Attributes(j).Name,'value')
                theMatrix{LastElem,4} = theStruct.Children(i).Attributes(j).Value;
            elseif strcmp(theStruct.Children(i).Attributes(j).Name,'dimension')
                theMatrix{LastElem,5} = uint16(str2double(theStruct.Children(i).Attributes(j).Value));
            elseif strcmp(theStruct.Children(i).Attributes(j).Name,'comment')
                theMatrix{LastElem,6} = theStruct.Children(i).Attributes(j).Value;
            end
        end
        % adapt value
        try
        if theMatrix{LastElem,5} == 1
            theMatrix{LastElem,4} = cast(str2double(theMatrix{LastElem,4}), theMatrix{LastElem,3});
        else
            if contains(theMatrix{LastElem,4}, ',')
                temp = regexprep(theMatrix{LastElem,4}, '(|[|)|]','');
                temp = split(temp,',');
                %temp{theMatrix{LastElem,5}} = '0';
                temp = cellfun(@(x) cast(str2double(x),theMatrix{LastElem,3}),temp,'UniformOutput',false);
                theMatrix{LastElem,4} = cell2mat(temp);

            else
                temp = ones(theMatrix{LastElem,5},1)*cast(str2double(theMatrix{LastElem,4}), theMatrix{LastElem,3});
                theMatrix{LastElem,4} = temp;
            end
        end
        catch ME
            if contains(ME.identifier,"UnsupportedClass")
                try
                    if contains(class(evalin('base',theMatrix{LastElem,3})), 'Bus')
                        var_right_type = evalin('base',['Simulink.Bus.createMATLABStruct("',theMatrix{LastElem,3},'")']);
                        var_right_type.value = temp;
                        theMatrix{LastElem,4} = temp;
                    end
                catch ME
                    error ("Check the data type for variable " + theMatrix{LastElem,1})
                end
            end
        end
    end
end
%%
function theMatrix = extractParameters(theMatrix, theStruct)
    numPar = numel(theStruct.Children);
    for i=1:numPar
        numberAtt=numel(theStruct.Children(i).Attributes);
        LastElem=size(theMatrix,1)+1;
        for j=1:numberAtt
            if strcmp(theStruct.Children(i).Attributes(j).Name,'name')
                theMatrix{LastElem,1} = theStruct.Children(i).Attributes(j).Value;    % parameter name
            elseif strcmp(theStruct.Children(i).Attributes(j).Name,'type')
                theMatrix{LastElem,2} = strrep(theStruct.Children(i).Attributes(j).Value,'_t','');    % parameter data type
            elseif strcmp(theStruct.Children(i).Attributes(j).Name,'value')
                value = theStruct.Children(i).Attributes(j).Value;
                if isnumeric(value)
                    theMatrix{LastElem,3}=str2double(value);                          % parameter value
                else
                    theMatrix{LastElem,3}=value;                                      % parameter value
                end
            end
        end
    end
end
%%
function attrib = extractSegAttr(Attributes)
    attrib = struct();
    numberAtt=numel(Attributes);
    for i=1:numberAtt
        if strcmp(Attributes(i).Name,'id')
            attrib.id = convertCharsToStrings(Attributes(i).Value);
        elseif strcmp(Attributes(i).Name,'name')
            attrib.name = Attributes(i).Value;
        else
            attrib.(Attributes(i).Name) = Attributes(i).Value;
        end
    end
end

function [theSegMatrix, theSupMatrix] = extractSegments(theSegMatrix, theSupMatrix, theStruct,OutMatrix, ParMatrix, ListParams)
    numPar = numel(theStruct.Children);
    segAttr = extractSegAttr(theStruct.Attributes);
    for i=1:numPar
        if strcmp(theStruct.Children(i).Name,'SIGNAL_TRAJECTORIES')
            try
                theSegMatrix = extractSegList(theSegMatrix, theStruct.Children(i).Children, segAttr.name, segAttr.id, OutMatrix, ParMatrix, ListParams);
            catch ME
                rethrow(ME)
            end
         elseif strcmp(theStruct.Children(i).Name,'SUPERVISION')
            theSupMatrix = extractSupList(theSupMatrix, theStruct.Children(i).Children, segAttr.name, segAttr.id);
        end
    end
end

function SegMatrix = extractSegList(SegMatrix, SegStruct, SegName, segID, OutMatrix, ParMatrix, ListParams)
    numPar = numel(SegStruct);
    for i=1:numPar
        LastElem=size(SegMatrix,1)+1;
        SegMatrix{LastElem,1} = SegName;                        % segment name
        SegMatrix{LastElem,2} = segID;                          % segment id
        SegMatrix{LastElem,3} = SegStruct(i).Attributes.Value;  % signal name
        % extract data type and dimension to ensure the values in the
        % trajectory are fine
        signalProperties = OutMatrix(strcmp(OutMatrix(:,1),SegMatrix{LastElem,3}),:);
        if isempty(signalProperties)
             errordlg(['The signal ' SegMatrix{LastElem,3} ' in the segment ' SegName ' is not declared'], 'Missing signal declaration');
             ME = MException('component:MissingSignalDeclaration', ...
                ['The signal ' SegMatrix{LastElem,3} ' in the segment ' SegName ' is not declared']);
            throw(ME)
        end
        if size(signalProperties,1) > 1
            % The variable has been defined twice
            signalProperties = signalProperties(1,:);
            warndlg (['The variable ' , signalProperties{1} , ' has been defined twice in the PS. Only the first definition is used. correct the PS'])
        end
        childElem = SegStruct(i).Children;
        for j=1:numel(childElem)
            if strcmp(childElem(j).Name,'REFERENCE')
                % if children point then trajectory
                % if child <SIGNAL> then signal name
                TrajDef = extractTraj(childElem(j).Children,signalProperties, ParMatrix, ListParams, SegName);
                SegMatrix{LastElem,4} = TrajDef;
            elseif strcmp(childElem(j).Name,'ENTRY_RULE')
                SegMatrix{LastElem,5} = childElem(j).Attributes.Value;
            elseif strcmp(childElem(j).Name,'EXECUTION_RULE')
                SegMatrix{LastElem,6} = childElem(j).Attributes.Value;
            elseif strcmp(childElem(j).Name,'EXIT_RULE')
                SegMatrix{LastElem,7} = childElem(j).Attributes.Value;
            end
        end
    end
end

function SupMatrix = extractSupList(SupMatrix, SupStruct, SegName, SegID)
    numSup = numel(SupStruct);
    for j=1:numSup
        structTemp = struct;
        LastElem=size(SupMatrix,1)+1;
        numPar= numel(SupStruct(j).Attributes);
        for i=1:numPar
            if strcmp(SupStruct(j).Attributes(i).Name,'program')
                SupMatrix{LastElem,1}=SupStruct(j).Attributes(i).Value;
            elseif strcmp(SupStruct(j).Attributes(i).Name,'type')
                SupMatrix{LastElem,2}=SupStruct(j).Attributes(i).Value;
            elseif strcmp(SupStruct(j).Attributes(i).Name,'targetSegment')
                SupMatrix{LastElem,3}=SupStruct(j).Attributes(i).Value;
            else
                value = SupStruct(j).Attributes(i).Value;
                if isnumeric(value)
                    structTemp.(SupStruct(j).Attributes(i).Name) = str2double(value);
                else
                    structTemp.(SupStruct(j).Attributes(i).Name) = value;
                end
            end
        end
        SupMatrix{LastElem,5}=SegName;
        SupMatrix{LastElem,6}=SegID;
        SupMatrix{LastElem,4} = structTemp;
    end
end

function TrajDef = extractTraj(TrajStruct, signalProperties, ParMatrix, ListParams, SegName)
    childNum = numel(TrajStruct);
    TrajDef = struct;
    trajArray={};
    Signal = '';
    Function = '';
    Parameters = struct;
    
    if strcmp(TrajStruct(1).Name,'POINT')
       for i=1:childNum
           for j=1:2
               if strcmp(TrajStruct(i).Attributes(j).Name, 'time')
                    time = str2double(TrajStruct(i).Attributes(j).Value);
               elseif strcmp(TrajStruct(i).Attributes(j).Name, 'value')
                    value = convertCharsToStrings(TrajStruct(i).Attributes(j).Value);
                    if signalProperties{5} == 1
                        if strcmp(signalProperties{3},"double")
                            value = str2double(value);
                        elseif contains(signalProperties{3},"uint")
                            value = uint32(str2double(value));
                        elseif contains(signalProperties{3},"int")
                            value = int32(str2double(value));
                        end
                    else
                        if contains(value, ',')
                            temp = regexprep(value, '\(|\)|\[|\]','');
                            temp = split(temp,',');
                            temp = cellfun(@(x) cast(str2double(x),signalProperties{3}),temp,'UniformOutput',false);
                            value = cell2mat(temp);
                        else                     
                            temp = ones(signalProperties{5},1)*cast(str2double(signalProperties{4}), signalProperties{3});
                            value = temp;
                        end
                    end
                    
               end
           end
           trajArray = [trajArray;{time, value}];
       end
    elseif strcmp(TrajStruct(1).Name,'FUNCTION')
        %if isinstance(TrajStruct(1).Attributes)
        %end
        numPar = numel(TrajStruct(1).Attributes);
        for attrID=1:numPar
            if strcmp(TrajStruct(1).Attributes(attrID).Name, 'code')
                Function = TrajStruct(1).Attributes(attrID).Value;
                % identify DP constants are replace
                for parIdx=1:numel(ListParams)
                    valueParam = ParMatrix(strcmp(ParMatrix(:,1),ListParams{parIdx}),3);
                    Function = strrep(Function,ListParams{parIdx},valueParam);
                end
            end
        end       
    else
        errordlg(['REFERENCE definition incorrect for signal ' signalProperties{1} ' in segment ' SegName])
        ME = MException('Configuration:Incorrect',['REFERENCE definition incorrect for signal ' signalProperties{1} ' in segment ' SegName]);
        throw(ME);
    end
    TrajDef.Values = trajArray;
    TrajDef.Code = Function;
end

function nodeStruct = makeStructFromNode(theNode)
    % Create structure of node info.
    nodeStruct = struct(                        ...
       'Name', char(theNode.getNodeName),       ...
       'Attributes', parseAttributes(theNode),  ...
       'Children', parseChildNodes(theNode));
   % nodeID, nodeName, nodeType, nodeParameter, NodeDesc, Children, Parent
end

function attributes = parseAttributes(theNode)
    % Create attributes structure.
    attributes = [];
    if theNode.hasAttributes
       theAttributes = theNode.getAttributes;
       numAttributes = theAttributes.getLength;
       allocCell = cell(1, numAttributes);
       attributes = struct('Name', allocCell, 'Value', ...
                           allocCell);

       for count = 1:numAttributes
          attrib = theAttributes.item(count-1);
          attributes(count).Name = char(attrib.getName);
          attributes(count).Value = char(attrib.getValue);
       end
    end
end

function theMatrix=renameNodes(theMatrix)
    for treesind=1:size(theMatrix,1)
        for nodeind=1:size(theMatrix{treesind,2},1)
            theMatrix{treesind,2}{nodeind,1}=[num2str(treesind),'-',num2str(theMatrix{treesind,2}{nodeind,1})];    % change nodeid
            theMatrix{treesind,2}{nodeind,7}=[num2str(treesind),'-',num2str(theMatrix{treesind,2}{nodeind,7})];    % change nodeparent
            for j=1:numel(theMatrix{treesind,2}{nodeind,3})
                theMatrix{treesind,2}{nodeind,3}{j}=[num2str(treesind),'-',num2str(theMatrix{treesind,2}{nodeind,3}{j})];    % change nodechildren
            end
        end
    end
end
