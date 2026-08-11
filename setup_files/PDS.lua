-- PDS meta-module (Lmod / EasyBuild style).
--
-- Goal: `git clone` this repo + `module load PDS` should be enough to run
-- the whole basic training end to end, with no per-user pds_setup.sh build.
--
-- Pins exact, known-good versions rather than bare unversioned module names,
-- so this doesn't silently drift onto a new (D)efault the next time SDCC's
-- module tree is updated. Re-verify and bump these deliberately.
--
-- Wires this checkout into PATH/PYTHONPATH so `pds-run` and `import pds`
-- work right after `module load PDS`, no separate `pip install -e .` step.
--
-- ACTOR CODES (NICE, IMAS-MUSCLE3, Waveform-Editor, TORAX-MUSCLE3) all come
-- from setup_files/custom_modules/build_*.sh, NOT the official SDCC modules,
-- for two independent reasons:
--
-- 1. RPATH conflict (NICE only): the official NICE/3.0.0-intel-2025b-DD-4.1.1
--    module's binaries are RPATH-linked to MUSCLE3/0.9.1 (verified with
--    `readelf -d`), which conflicts with IMAS-MUSCLE3/Waveform-Editor's
--    MUSCLE3/0.10.0 dependency. RPATH always wins over any modulefile trick,
--    so this can only be fixed by rebuilding, not by a smarter module.
--
-- 2. PYTHONPATH leak (IMAS-MUSCLE3, Waveform-Editor): the official modules
--    are EasyBuild "PythonPackage"-style installs -- a shared interpreter
--    plus a PYTHONPATH prepend, not a self-contained venv. Loading either one
--    pulls in MUSCLE3/0.10.0 as a `depends_on`, putting its PYTHONPATH in
--    *this* interactive shell -- and since venv activation for other actors
--    only prepends PATH (never resets PYTHONPATH), every actor subprocess
--    muscle_manager spawns from this shell would inherit it too. That's
--    exactly the leak bin/pds-run's own comment describes and was written to
--    avoid. A real venv (python -m venv) sidesteps this entirely: its own
--    bin/python already knows its own site-packages, no PYTHONPATH needed --
--    which is exactly what setup_files/custom_modules/build_imas_muscle3.sh /
--    build_waveform_editor.sh produce, PATH-only, same as pds-run's own
--    preferred self-contained-venv path.
--
-- TORAX-MUSCLE3 has neither problem itself, but is built the same way for
-- consistency, and because the official TORAX module (-foss-2025b only,
-- confirmed to conflict with the intel-2025b stack here, and missing the
-- MUSCLE3 actor wrapper anyway) isn't usable regardless.
--
-- muscle3-dashboard (muscle_dashboard/m3dash) is installed by
-- build_imas_muscle3.sh into the SAME venv as IMAS-MUSCLE3, not its own --
-- see docs/source/courses/basic/muscle3_dashboard.rst: a recorder tab's plot
-- file imports imas_muscle3.visualization, which needs imas_muscle3 and the
-- full IMAS stack in the dashboard's own venv to render, and this venv
-- already has that. So no separate module for it: loading IMAS-MUSCLE3
-- below is enough to get muscle_dashboard/m3dash on PATH too.
--
-- Building each one is a real, one-time compile/install (needs your
-- git.iter.org / GitHub access, and for NICE, real compile time) -- see
-- setup_files/custom_modules/README.md. Once built, fill in the version
-- strings below and this file works unmodified for every future clone.
--
-- METIS-IRFM stays on the official module: it's a MATLAB-driven actor, not a
-- Python one, so the PYTHONPATH concern above doesn't apply, and no version
-- conflict was found for it.
--
-- Deliberately does NOT load MUSCLE3 itself: bin/pds-run and
-- workflows/*/run_simulation.sh each `module load MUSCLE3` themselves,
-- scoped to that one invocation, precisely to avoid the leak described above.
--
-- workflows/lib/local_programs.ymmsl resolves actors via $EBROOT<NAME> from
-- these modules (already rewritten to do so, no longer uses
-- $PDS_REPO/run/<code>/venv) -- ci/run_test_workflows.sh and
-- workflows/inverse_convergence/postprocess_data.sh were updated to match.
--
-- Generated from a template. To (re-)deploy after moving/re-cloning this
-- checkout, from the checkout root run:
--
--   mkdir -p /home/ITER/blokhus/public/modules/PDS
--   sed "s|@@PDS_ROOT@@|$(pwd)|g" setup_files/PDS.lua \
--     > /home/ITER/blokhus/public/modules/PDS/1.0.lua
--
-- Anyone can then use it without cloning their own checkout:
--
--   module use /home/ITER/blokhus/public/modules
--   module load PDS

help([[
PDS (Pulse Design Simulator) meta-module.

Loads the newest verified cluster modules for the IMAS-PDS stack (IMAS-Core,
IMAS-Python, IDStools, UDA, METIS-IRFM), pinned by exact version, plus custom
builds of NICE/IMAS-MUSCLE3/Waveform-Editor/TORAX-MUSCLE3 (see
setup_files/custom_modules/), and wires this checkout into PATH/PYTHONPATH.

Also puts muscle_dashboard/m3dash on PATH (bundled into the IMAS-MUSCLE3
build, not a separate module -- see this file's source comments).

Wires PDS_REPO/PATH/PYTHONPATH to your own clone automatically if you `cd`
into it first (detected via bin/pds-run), or to an already-exported PDS_REPO;
otherwise defaults to: @@PDS_ROOT@@ (run output would then land in THAT
checkout, which only its owner can write to).

Does NOT load MUSCLE3 -- pds-run and run_simulation.sh load it themselves.
Does NOT load the official NICE/TORAX/IMAS-MUSCLE3/Waveform-Editor modules --
see this file's source comments (setup_files/PDS.lua) for why each one is
replaced by a custom build instead.

]])

whatis("Description: Meta-module for IMAS-PDS (github.com/iterorganization/IMAS-PDS): loads its module stack and wires this checkout into PATH/PYTHONPATH.")
whatis("URL: https://github.com/iterorganization/IMAS-PDS")

local pds_root = "@@PDS_ROOT@@"

-- IMAS core stack (official modules; no actor-isolation concern -- these
-- aren't spawned as isolated MUSCLE3 actor subprocesses the way the actor
-- codes below are)
load("IMAS-Core/5.7.1-intel-2025b")
load("IMAS-Python/2.3.0-intel-2025b")
load("IDStools/2.4.1-intel-2025b")   -- also provides plotscenario, idsdiff
load("UDA/2.9.3-intel-compilers-2025.2.0")
load("METIS-IRFM/11.0-intel-2025b-MATLAB-2025b-r1")

-- Actor codes: custom builds only, see the comment block above for why.
-- Built via setup_files/custom_modules/build_*.sh with these exact version
-- strings (2026-08-10).
load("NICE/3.0.0-pds-intel-2025b")
load("IMAS-MUSCLE3/1.0.0-pds-2026-08-10")
-- Built from feature/reference-tendency-old, NOT main: ci/run_test_workflows.sh
-- pins this same branch deliberately (main is missing something these
-- workflows' waveform configs need -- confirmed by a real failure building
-- from main: "'imports' is not a parameter of YamlGlobals").
load("Waveform-Editor/0.3.1-pds-ref-tendency-old")
load("TORAX-MUSCLE3/develop-2026-08-10")

-- Wire a checkout in, so `pds-run` and `import pds` work immediately.
-- Picks, in order:
--   1. An already-exported PDS_REPO (explicit override, e.g. set in your
--      shell profile before `module load PDS` runs anywhere).
--   2. The current directory, if it looks like a PDS checkout (has
--      bin/pds-run) -- covers the natural `cd ~/my-pds-clone && module load
--      PDS` case with no extra steps.
--   3. This file's own checkout (@@PDS_ROOT@@), as a last-resort default.
--
-- Without this, everyone loading this shared module would get run output
-- (workflows/*/scenarios/*/tmp/runs/...) forced into @@PDS_ROOT@@ regardless
-- of where they're actually working, which only its owner can write to --
-- confirmed: a second user hit exactly this as a permission-denied error.
local pds_repo = os.getenv("PDS_REPO")
if not pds_repo then
  local cwd = os.getenv("PWD")
  if cwd and isFile(pathJoin(cwd, "bin/pds-run")) then
    pds_repo = cwd
  else
    pds_repo = pds_root
  end
end
prepend_path("PATH", pathJoin(pds_repo, "bin"))
prepend_path("PYTHONPATH", pds_repo)
setenv("PDS_REPO", pds_repo)

-- Match run/imas_base_env
execute{cmd="ulimit -s unlimited", modeA={"load"}}
unsetenv("MPLBACKEND")
setenv("IMAS_VERSION", "4.0.0")
