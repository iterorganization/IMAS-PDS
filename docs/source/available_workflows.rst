.. _`available_workflows`:

Available PDS workflows
=======================

Here we provide a brief explanation of the available workflows.

METIS-NICE interpretative
-------------------------

<METIS-NICE DESCRIPTION PLACEHOLDER>

METIS-NICE predictive
---------------------

<METIS-NICE DESCRIPTION PLACEHOLDER>

TORAX-NICE self-consistent transport
------------------------------------

This workflow takes a dataset with a preconfigured plasma shape.
It first runs the NICE code in inverse mode to obtain the coil currents necessary to obtain the desired shape
and recalculates the obtained plasma shape for these coil currents.
It then uses the NICE equilibrium IDS output to initialize the TORAX geometry provider
and runs TORAX with current evolution enabled from start to finish.
This workflow is meant to be rerun multiple times until the results are converged to a satisfactory degree.
This is done by hand by the user.

Requirements:

- Requires DDv4 input data.
- Requires equilibrium, pf_active, pf_passive, iron_core and wall IDS for NICE input.
- Requires pf_active IDS where each coil contains exactly one element in the elements AoS for NICE input.
- Requires pf_active IDS to have coil objects with resistance values for NICE input.
