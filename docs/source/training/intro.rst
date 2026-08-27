.. _`training/intro`:

PDS training
============

Introduction
------------

In this PDS training we introduce you to the basic concepts and features of the PDS ecosystem.
The training is intended to be worked through in order, as more complicated topics will be
covered in the later sections.

.. important::
    This training assumes you have access to ITER's SDCC, as all dependencies will be 
    available as modules. Moreover, you will need access to a graphical environment to visualize
    the simulation results. It is recommended to follow this training through the NoMachine client.

The final two sections, :ref:`training/advanced` and :ref:`training/build_own_actor`, are aimed at
developers: they show how to build your own workflow out of existing support and simulation
actors, and how to write a new actor of your own. The rest of the training is relevant to
any PDS user.

We assume you have some basic knowledge of `IMAS <https://imas-data-dictionary.readthedocs.io/en/latest/>`_.
You will also need some basic familiarity with Python.
For a refresher, see the `Python tutorial <https://docs.python.org/3/tutorial/>`_.
We also assume some basic knowledge of `MUSCLE3 <https://muscle3.readthedocs.io/en/latest/>`_.
For more information on the visualization actor, see the `IMAS-MUSCLE3 training <https://imas-muscle3.readthedocs.io/en/latest/training.html>`_.
For more information on the waveform-editor, see the `Waveform-Editor training <https://waveform-editor.readthedocs.io/en/latest/training/training.html>`_.

Training contents
-----------------

The sections are meant to be followed in order:

:ref:`Setting up the PDS <training/setup>`
    Getting the PDS ready on SDCC

:ref:`Understanding the PDS <training/understanding>`
    Learn what scenarios, workflows and runs are, and how the PDS architecture works

:ref:`Running your first PDS workflow <training/run_first>`
    Run your first workflow and follow it live in the MUSCLE3 dashboard

:ref:`Running existing workflows <training/run_complex>`
    Run some of the premade ITER scenario workflows

:ref:`Configuring existing workflows <training/configuring>`
    Learn how to configure an existing scenario and analyze the results

:ref:`Visualizing workflows <training/visualization>`
    Learn how to visualize the data flowing between actors during a run

:ref:`Advanced: building your own workflows <training/advanced>`
    Advanced training for developers: learn how to assemble a workflow out of existing 
    actors step by step, and create a new actor of your own.

.. toctree::
    :hidden:
    :maxdepth: 1

    setup
    understanding
    run_first
    run_complex
    configuring
    visualization
    advanced
