.. _`training/advanced`:

Advanced PDS training
======================

This is the advanced counterpart to the :ref:`PDS training <training/intro>`, aimed at
developers rather than end users of PDS workflows: it shows how to build your own workflow
out of existing support and simulation actors, how to write a new actor of your own, and how
to bring a new scenario into the PDS.

.. important::
    This training assumes you have access to ITER's SDCC, as all dependencies will be
    available as modules.

Training contents
------------------

:ref:`Building a workflow from scratch <training/workflow_from_scratch>`
    Assemble a MUSCLE3 workflow out of existing actors step by step, from a simple
    source/sink pipeline up to a full NICE/TORAX coupling.

:ref:`Setting up a MUSCLE3 actor for the PDS <training/build_own_actor>`
    Write a new actor of your own, and learn how it is configured and pointed at a build.

:ref:`Adding a new scenario <training/new_scenario>`
    Bring a new shot into the PDS.

.. toctree::
    :hidden:
    :maxdepth: 1

    workflow_from_scratch
    muscle3_actor
    new_scenario
