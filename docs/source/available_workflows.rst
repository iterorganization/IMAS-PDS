.. _`available_workflows`:

Available PDS workflows
=======================

Here we provide a brief explanation of the available workflows.


METIS-NICE workflow
-------------------

Starting from a DINA simulation, the workflow coupling METIS and NICE static inverse computes the plasma state with METIS in two modes:
1.	Interpretative: METIS uses the kinetic profiles for electron temperature and density and for ion temperature read from the DINA simulation and predict all other fields.
2.	Predictive: METIS predict all the quantities
In both cases, METIS reads its inputs from the DINA simulation (mainly the plasma current, the line averaged density, the LCFS and other references). 
Using the result from METIS (plasma current, LCFS poloidal flux and profiles P’ and FF’) and the constraint provided by the LCFS set of points read in DINA simulation, 
NICE inverse static computes the free boundary equilibrium and provides an updated LCFS and coil currents.

\* Interpretative mode
^^^^^^^^^^^^^^^^^^^^^^

To launch the workflow for the interpretative mode, the command is:
    bash run_workflow.sh metis_interpretative_nice_inverse_from_dina <simulation_Id>
for example:

.. code-block:: bash

    bash run_workflow.sh metis_interpretative_nice_inverse_from_dina 105084

\* Predictive mode
^^^^^^^^^^^^^^^^^^

To launch the workflow for the predictive mode, the command is:
    bash run_workflow.sh metis_predictive_nice_inverse_from_dina <simulation_Id>
for example:

.. code-block:: bash

    bash run_workflow.sh metis_predictive_nice_inverse_from_dina 105084


\* List of currently available <simulation_Id>
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following simulation Id are available:

  - 105073
  - 105078
  - 105084
  - 105092
  - 105099

\* Requirements:
^^^^^^^^^^^^^^^^

- Requires DDv4 input data (The preprocessing convert the DINA data if needed)
- Requires equilibrium, pf_active, pf_passive, iron_core and wall IDSs for NICE input (needs to get machine description from some reference)
- Requires pf_active IDS where each coil contains exactly one element in the elements AoS for NICE input (The preproccessing generate it if needed).
- Requires pf_active IDS to have coil objects with resistance values for NICE input.
- Requires summary,	pulse_schedule, equilibrium, core_profiles (alternatively if it is available plasma_profiles), core_sources (alternatively if it is available plasma_sources) IDSs for METIS inputs.
- Requires pulse_schedule filled for METIS code (see METIS documentation for details: https://github.com/IRFM/METIS/tree/main/doc/METIS_inputs_from_IMAS_IDSs.pdf, the preproccessing create it from DINA data if needed)


TORAX-NICE self-consistent transport
------------------------------------

This workflow takes a dataset with a preconfigured plasma shape.
It first runs the NICE code in inverse mode to obtain the coil currents necessary to obtain the desired shape
and recalculates the obtained plasma shape for these coil currents.
It then uses the NICE equilibrium IDS output to initialize the TORAX geometry provider
and runs TORAX with current evolution enabled from start to finish.
This workflow is meant to be rerun multiple times until the results are converged to a satisfactory degree.
This is done by hand by the user.
This workflow also offers the optional argument ``--rerun`` to run it from the output from the last run.

.. code-block:: bash

  bash run_workflow.sh torax_nice_self_consistent_transport 105084 --rerun


Requirements:

- Requires DDv4 input data.
- Requires equilibrium, pf_active, pf_passive, iron_core and wall IDS for NICE input.
- Requires pf_active IDS where each coil contains exactly one element in the elements AoS for NICE input.
- Requires pf_active IDS to have coil objects with resistance values for NICE input.
