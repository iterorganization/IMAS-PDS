.. _`code style and linting`:

Code style and linting
======================


Code style, linting and import sorting
----------------------------------------

PDS uses `Ruff <https://docs.astral.sh/ruff/>`_ for formatting, linting and import
sorting. Ruff's formatter is a drop-in, much faster replacement for Black, and its
linter covers the rules previously provided by flake8 and isort. All Python files
should be formatted and free of Ruff violations (this is checked in
:ref:`CI <ci configuration>`).

In some exceptions we can ignore a violation. For example, if a violation cannot be
avoided, or fixing it would result in less readable code. This should be avoided as much
as possible though; see the ``[tool.ruff.lint]`` section in ``pyproject.toml`` for the
project's ignore list.


Why Ruff?
'''''''''

Ruff gives us a single, fast tool that replaces Black (formatting), flake8 (linting) and
isort (import sorting), so code style is uniform across all Python files regardless of
the developer that created the code 🙂.

This improves efficiency of developers working on the project:

-   Uniform code style makes it easier to read, review and understand other's code.
-   Autoformatting code means that developers can save time and mental energy for the
    important matters.
-   One tool and one configuration section instead of three.

More reasons for using Ruff can be found on `their website
<https://docs.astral.sh/ruff/>`_.


Using Ruff
''''''''''

The easiest way to work with Ruff is by using an integration with your editor. See
https://docs.astral.sh/ruff/editors/.

You can also install it (e.g. ``uv pip install ruff``) and run it every time before
committing (manually or with pre-commit hooks):

.. code-block:: console

    $ ruff format pds
    2 files reformatted, 64 files left unchanged
    $ ruff check pds
    All checks passed!

``ruff check --fix pds`` will also sort imports and fix other auto-fixable violations.


Type checking
-------------
PDS uses type hinting which is checked using `ty <https://docs.astral.sh/ty/>`_, a
fast type checker from the same team as Ruff and uv. This tool can spot typing bugs
and makes for easier code maintenance and debugging.

Using ty
''''''''

.. code-block:: console

    $ ty check pds
    All checks passed!

Docstring style
---------------
While not enforced, we recommend using `napoleon style docstrings <https://sphinxcontrib-napoleon.readthedocs.io/en/latest/>`_
