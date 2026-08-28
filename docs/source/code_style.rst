.. _`code style and linting`:

Code style and linting
======================

Code style
----------

PDS uses `Ruff <https://docs.astral.sh/ruff/>`_ for formatting, linting and import
sorting -- one tool where there used to be Black, flake8 and isort. It is enforced in
:ref:`CI <ci configuration>`.

.. code-block:: console

    $ ruff format .       # format
    $ ruff check .        # lint
    $ ruff check --fix .  # lint, and apply the auto-fixable violations

Easiest through `editor integration
<https://docs.astral.sh/ruff/editors/#editor-integrations>`_.

A violation can be ignored where fixing it would make the code less readable, but keep
that rare; see ``[tool.ruff.lint]`` in ``pyproject.toml`` for the current ignore list.

Type checking
-------------

Type hints are checked with `ty <https://docs.astral.sh/ty/>`_, from the same team as
Ruff and uv. Also enforced in :ref:`CI <ci configuration>`.

.. code-block:: console

    $ uv run ty check .
    All checks passed!

Docstring style
---------------

Not enforced, but prefer `Napoleon-style docstrings
<https://sphinxcontrib-napoleon.readthedocs.io/en/latest/>`_.
