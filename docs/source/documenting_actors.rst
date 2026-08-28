.. _`documenting_actors`:

Documenting PDS actors
======================

The outline every PDS actor's documentation should follow. Worked examples are on
`Confluence <https://confluence.iter.org/display/IMP/PDS+Muscle3+Actors>`__.

Summary
   What the actor does and what it is for.

Operational modes
   If it has more than one, introduce them here and show how each is selected. Omit
   otherwise.

Settings
   For each: name, data type, mandatory or optional, which modes it applies to, what it
   does, and the default if optional. Usually split into mandatory and optional sections.

Ports
   For each: name, operator (``f_init``, ``o_i``, ``s``, ``o_f``), mandatory or optional,
   which modes it applies to, what it carries, and the behaviour if it is left
   unconnected. Split by mandatory/optional, or by operator.

Required input and output fields per IDS
   Which fields the actor reads and which it fills. This is what tells someone whether
   two actors can be coupled at all, so it is the section not to skip.

General info
   Anything else worth knowing -- compatible Data Dictionary versions, for instance.
