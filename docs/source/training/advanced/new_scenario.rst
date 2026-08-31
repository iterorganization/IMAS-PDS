.. _`training/new_scenario`:

Adding a new scenario
======================

Bringing a new scenario into the PDS
--------------------------------------

Sooner or later you will want to run a pulse that is not in ``pds-scenarios`` yet -- a new
DINA output, say. The work splits in two, and it is worth knowing which half is which,
because most of it is not in this repository at all.

**In pds-scenarios.** A shot directory is not the raw DINA output; it is that output
converted into the layout every PDS workflow expects. Each shot carries a ``source.env``
naming where its raw data came from, and the repository's own ``tools/`` turn that into the
``data/in`` and ``data/in_md`` DBEntries you looked at in :ref:`training/understanding`. Adding
a shot means adding it there, following the shots already present as a template.

**In the PDS.** Usually nothing. The workflows take the shot number as a parameter -- every
path in ``workflows/<name>/settings.ymmsl`` is written with ``${SHOT}`` in it -- so as soon as
the scenario exists, ``bin/pds-create-case <workflow> <new-shot>`` works.

You only come back to this repository when the new shot needs something the generic settings
do not give it, and then it goes in one file:
``cases/overrides/<workflow>_<newshot>.ymmsl``. Look at the existing overrides to see what
that is in practice -- mostly a loop window that suits the pulse, and sometimes a calibrated
solver configuration.

There is one loose end that catches people out. The validation plotting in each workflow's
``postprocess.sh`` picks its comparison times from a per-shot list, and a shot that is not in
that list makes the job fail *after* a perfectly good simulation. If you add a shot, add it
there too.

.. md-tab-set::

    .. md-tab-item:: Exercise

        Without adding anything, work out what would be needed to run ``prescribed_transport``
        on a shot that is currently only used by ``metis_nice_inverse_from_dina``.

    .. md-tab-item:: Solution

        The scenario data already exists, so ``bin/pds-create-case prescribed_transport
        <shot>`` builds a case straight away -- the generic settings fill in the shot number
        and it runs.

        Whether the *result* is any good is a separate question: no override has been tuned
        for that combination, so the loop window and the solver configuration are whatever the
        workflow's defaults are. And unless the shot happens to be in
        ``prescribed_transport/postprocess.sh``'s list, the run will finish and the plotting
        step will not.

With that, you have seen the whole path: running a premade case, configuring it, watching it,
building a workflow out of existing actors, writing an actor of your own, and adding the
scenario it runs on.
