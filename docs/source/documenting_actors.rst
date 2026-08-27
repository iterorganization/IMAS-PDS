.. _`documenting_actors`:

Documenting PDS actors
======================

Here we provide the general outline for documentation of PDS actors.
Some examples are provided `here <https://confluence.iter.org/display/IMP/PDS+Muscle3+Actors>`__.

Actor Summary
-------------

Summary of what the actor does and what it can be used for.

Optional: available operational modes
-------------------------------------

If the actor has multiple operational modes, introduce them here and
show how these different modes are implemented.

Available Settings
------------------

Show any settings that the actor uses. Often divided in a mandatory
section and an optional section. 
For each setting show:

* Name
* Data type
* Mandatory/optional
* Relevant for which operation modes
* Explanation of effect
* Default value if optional

Available Ports
---------------

Show all the available ports for your actor.
Often divided in a mandatory section and an optional section.
Can also be divided into subsections per operator.
For each port show:

* Name
* Port (f_init, o_i, s, o_f)
* Mandatory/optional
* Relevant for which operational modes
* Explanation
* Default behavior if optional

Required input/output fields per IDS
------------------------------------

Document which fields per IDS are required as input for this actor
and which fields are available in the output.
This is necessary to check the compatibility of different actors.

General Info
------------

Any other information that might be useful.
(For example, compatible Data Dictionary versions)
