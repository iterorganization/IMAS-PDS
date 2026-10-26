.. _`training/profiling`:

Profiling a workflow
=====================

Every run writes a ``performance.sqlite`` next to the manager log. MUSCLE3 fills it as the
run goes: how long each instance spent computing, transferring data and waiting for
messages, plus a timestamped event for every send and receive. It is on by default, so the
runs you did earlier in this training already have one.

The ``muscle3 profile`` command turns that database into plots. See the
`MUSCLE3 profiling documentation <https://muscle3.readthedocs.io/en/latest/profiling.html>`_
for what each plot shows and how the numbers are measured.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Take the ``inverse_convergence`` run for shot ``105092`` from
        :ref:`training/run_complex` and profile it:

        .. code-block:: bash

            RUN=cases/runs/inverse_convergence_105092

            muscle3 profile --instances $RUN/performance.sqlite
            muscle3 profile --resources $RUN/performance.sqlite
            muscle3 profile --timeline  $RUN/performance.sqlite

        Look at the three plots and answer for yourself:

        #. Which instance spends the most time computing, and how much of the run is that?
        #. What are the other actors doing meanwhile?
        #. Does the outer loop show up as a repeating pattern in the timeline?

