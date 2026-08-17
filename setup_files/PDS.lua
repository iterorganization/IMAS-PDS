-- PDS meta-module (Lmod / EasyBuild style).
--
-- Goal: `git clone` this repo + `module load PDS` should be enough to (a) use
-- muscle_manager/muscle_dashboard/m3dash directly, and (b) run any workflow --
-- each of its actors loads its OWN environment when MUSCLE3 spawns it (see
-- "ACTOR CODES" below), so this module does not need to (and deliberately
-- does not) eagerly load every actor code up front.
--
-- Pins exact, known-good versions rather than bare unversioned module names,
-- so this doesn't silently drift onto a new (D)efault the next time SDCC's
-- module tree is updated. Re-verify and bump these deliberately.
--
-- Wires this checkout into PATH/PYTHONPATH so `pds-run` and `import pds`
-- work right after `module load PDS`, no separate `pip install -e .` step.
--
-- ACTOR CODES: this module deliberately does NOT eagerly load NICE, Waveform-
-- Editor, TORAX-MUSCLE3, or METIS-IRFM -- those are pure actor implementations,
-- never invoked by a human directly, so every actor entry in
-- workflows/lib/local_programs.ymmsl (and the workflow-specific .ymmsl.template
-- files) declares `base_env: clean` plus its own complete `modules:` list.
-- MUSCLE3 loads that fresh, from a clean slate, in the actor's own subprocess
-- when it spawns it -- completely independent of whatever this module loaded,
-- or of what any other actor in the same run needs. This is not an
-- optimisation, it's the load-bearing design decision: different workflows
-- (and even different actors within ONE workflow, e.g. NICE + a MATLAB/
-- IMAS-AL-Matlab-based controller) can and do need genuinely incompatible
-- toolchains, and there is no way to make all of that coexist in one eagerly-
-- loaded shared environment (confirmed: IMAS-AL-Matlab has no intel-2025b
-- build at all, only foss-2023b/intel-2023b -- there's no "upgrade the
-- module" escape hatch for that one). See setup_files/custom_modules/README.md
-- for how each PDS-<Name> module is built.
--
-- The one exception is PDS-IMAS-MUSCLE3, kept eager below: unlike the other
-- three, it is also a human-facing tool (muscle_manager, muscle_dashboard/
-- m3dash), not just an actor implementation, so `module load PDS` alone
-- should be enough to use those directly. Actors that also need
-- PDS-IMAS-MUSCLE3 for their own work still declare it explicitly in their
-- own `modules:` list too (redundant with this eager load today, but that's
-- deliberate: no actor should silently depend on what this module happens to
-- also load for the human-tool use case, so a future change to that eager
-- load can never silently break an actor that forgot to declare its own
-- dependency).
--
-- Why these four are custom builds, not the official SDCC modules:
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
-- 3. Bare-name collision with MUSCLE3's own per-actor module-load mechanism:
--    every actor declares its modules via MUSCLE3's own `modules:`/
--    `base_env: clean` mechanism (see above) -- if our custom builds used
--    bare names (NICE, IMAS-MUSCLE3, ...), `module load NICE` inside one of
--    those freshly-purged actor subprocesses could resolve to the official
--    (broken) module instead of ours, depending on Lmod's tie-breaking across
--    merged module trees -- a real risk, not hypothetical. So all four custom
--    builds are exposed as PDS-<Name> (PDS-NICE, PDS-IMAS-MUSCLE3,
--    PDS-Waveform-Editor, PDS-TORAX-MUSCLE3), structurally ruling out the
--    collision.
--
-- TORAX-MUSCLE3 has neither problem #1/#2 itself, but is built the same way
-- for consistency, and because the official TORAX module (-foss-2025b only,
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
-- IMAS-Python stays eager below: it's not spawned as an isolated actor
-- subprocess, and preprocess_data.sh/postprocess_data.sh (which run in the
-- orchestrator's own shell, not through MUSCLE3 at all) still assume it's
-- already loaded. Not revisited yet -- a workflow needing a genuinely
-- different version would need its own fix, same as the actor-code case
-- above, but that's out of scope for now.
--
-- IMAS-Core and UDA are NOT loaded explicitly here even though
-- preprocess/postprocess also depend on them: IMAS-Python/2.3.0-intel-2025b
-- already has `depends_on("IMAS-Core/5.7.1-intel-2025b")` baked into its own
-- modulefile, and IMAS-Core in turn `depends_on("UDA/2.9.3-intel-compilers-
-- 2025.2.0")` -- confirmed empirically: `module purge; module load
-- IMAS-Python` alone loads both as well (verified via `module list` and
-- their $EBROOT* vars). Pinning them here too would be pure duplication of a
-- version Lmod already resolves correctly on its own -- and would silently
-- go stale (unnoticed) if IMAS-Python's own dependency chain ever changes,
-- which is exactly the kind of implicit-correctness-by-accident this module
-- is designed to avoid. IDStools is NOT a dependency of IMAS-Python/
-- IMAS-Core, and nothing in this repo needs it loaded via PDS: its only use
-- (plotscenario, idsdiff) is in docs/source/courses/basic/build.rst, which
-- already has students `module load IDStools` themselves as its own step.
--
-- Deliberately does NOT load MUSCLE3 itself: bin/pds-run and
-- workflows/*/run_simulation.sh each `module load MUSCLE3` themselves,
-- scoped to that one invocation, precisely to avoid the leak described above.
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

Loads IMAS-Python, pinned by exact version (which in turn pulls in IMAS-Core
and UDA via their own module dependencies), plus the custom PDS-IMAS-MUSCLE3
build (see setup_files/custom_modules/) so muscle_manager and
muscle_dashboard/m3dash work right after `module load PDS` -- and wires this
checkout into PATH/PYTHONPATH.

Deliberately does NOT eagerly load NICE, Waveform-Editor, TORAX-MUSCLE3, or
METIS-IRFM: those are pure actor implementations (never run by a human
directly), so every actor declares its own `modules:` + `base_env: clean` in
workflows/lib/local_programs.ymmsl, and MUSCLE3 loads that fresh in the actor's own
subprocess when it spawns it. See this file's source comments for why this
matters: different actors (even within one workflow) can need genuinely
incompatible toolchains, and there is no single eagerly-loaded environment
that fits all of them.

Wires PDS_REPO/PATH/PYTHONPATH to your own clone automatically if you `cd`
into it first (detected via bin/pds-run), or to an already-exported PDS_REPO;
otherwise defaults to: @@PDS_ROOT@@ (run output would then land in THAT
checkout, which only its owner can write to).

Does NOT load MUSCLE3 -- pds-run and run_simulation.sh load it themselves.
Does NOT load the official NICE/TORAX/Waveform-Editor modules -- see this
file's source comments (setup_files/PDS.lua) for why each one is replaced by
a custom build instead.

]])

whatis("Description: Meta-module for IMAS-PDS (github.com/iterorganization/IMAS-PDS): loads its module stack and wires this checkout into PATH/PYTHONPATH.")
whatis("URL: https://github.com/iterorganization/IMAS-PDS")

local pds_root = "@@PDS_ROOT@@"

-- IMAS core stack (official module; not spawned as an isolated MUSCLE3 actor
-- subprocess, and preprocess_data.sh/postprocess_data.sh -- which run in the
-- orchestrator's own shell, not through MUSCLE3 -- still assume it's already
-- loaded; see the comment block above). Pulls in IMAS-Core and UDA itself via
-- `depends_on`, so they're deliberately not also listed here.
load("IMAS-Python/2.3.0-intel-2025b")

-- The one actor code kept eager: also a human-facing tool (muscle_manager,
-- muscle_dashboard/m3dash), not just an actor implementation. See the
-- comment block above for why every OTHER actor code is deliberately NOT
-- here, and why actors needing this one still declare it themselves too.
-- Named PDS-IMAS-MUSCLE3, not bare IMAS-MUSCLE3 -- see reason #3 above.
-- Built via setup_files/custom_modules/build_imas_muscle3.sh (2026-08-10).
load("PDS-IMAS-MUSCLE3/1.0.0-pds-2026-08-10")

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
prepend_path("YMMSL_PATH", pathJoin(pds_repo, "workflows"))

-- Env settings every workflow actor needs.
execute{cmd="ulimit -s unlimited", modeA={"load"}}
unsetenv("MPLBACKEND")
setenv("IMAS_VERSION", "4.0.0")
