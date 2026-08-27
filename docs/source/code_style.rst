.. _`code style and linting`:

Code style and linting
======================

Code style
----------

PDS uses `Ruff <https://docs.astral.sh/ruff/>`_ for both code formatting and linting
(including import sorting). All Python files must be formatted and linted using the
``ruff`` command-line tool. This is enforced in :ref:`CI <ci configuration>`.

In some exceptions we can ignore a violation. For example, if a violation cannot be
avoided, or fixing it would result in less readable code. This should be avoided as
much as possible though; see the ``[tool.ruff.lint]`` section in ``pyproject.toml``
for the project's ignore list.

Why Ruff?
'''''''''

We use Ruff to ensure that code style is uniform across all Python files, regardless
of the developer who wrote the code. Ruff replaces what used to be three separate
tools (Black, flake8 and isort) with a single, much faster tool and configuration
section.

This improves the efficiency of developers working on the project:

- Uniform code style makes it easier to read, review, and understand others' code.
- Autoformatting code reduces time spent on style decisions, allowing developers to
  focus on logic and functionality.
- Static analysis detects common issues before runtime, preventing certain classes of
  bugs.

Using Ruff
''''''''''

The easiest way to work with Ruff is via editor integration. See
https://docs.astral.sh/ruff/editors/#editor-integrations for details.

You can also install Ruff and run it manually before committing:

.. code-block:: console

    $ ruff format .       # Format code
    $ ruff check .        # Lint code

``ruff check --fix .`` will also sort imports and fix other auto-fixable violations.

Type checking
-------------

PDS uses type hinting which is checked using `ty <https://docs.astral.sh/ty/>`_, a
fast type checker from the same team as Ruff and uv. This tool can spot typing bugs
and makes for easier code maintenance and debugging. This is also enforced in
:ref:`CI <ci configuration>`.

Using ty
''''''''

.. code-block:: console

    $ uv run ty check .
    All checks passed!

Docstring style
---------------

While not enforced, we recommend using `Napoleon-style docstrings
<https://sphinxcontrib-napoleon.readthedocs.io/en/latest/>`_.
