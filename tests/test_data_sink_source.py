from pathlib import Path

import ymmsl
from imaspy import DBEntry

from libmuscle.manager.manager import Manager
from libmuscle.manager.run_dir import RunDir
from pds import get_project_root


def test_source_to_sink(tmpdir, core_profiles):
    data_source_path = (Path(tmpdir) / "source_component_data").absolute()
    data_sink_path = (Path(tmpdir) / "sink_component_data").absolute()
    source_uri = f"imas:hdf5?path={data_source_path}"
    sink_uri = f"imas:hdf5?path={data_sink_path}"
    with DBEntry(source_uri, "w") as entry:
        entry.put(core_profiles)
    tmppath = Path(str(tmpdir))
    # make config
    ymmsl_text = (
        "ymmsl_version: v0.1\n"
        "model:\n"
        "  name: test_model\n"
        "  components:\n"
        "    source_component:\n"
        "      implementation: source_component\n"
        "      ports:\n"
        "        o_i: [core_profiles_out]\n"
        "    sink_component:\n"
        "      implementation: sink_component\n"
        "      ports:\n"
        "        f_init: [core_profiles_in]\n"
        "  conduits:\n"
        "    source_component.core_profiles_out: sink_component.core_profiles_in\n"
        "settings:\n"
        f"  source_component.source_uri: {source_uri}\n"
        f"  sink_component.sink_uri: {sink_uri}\n"
        "implementations:\n"
        "  sink_component:\n"
        "    executable: python\n"
        "    args: -u -m pds.utils.sink_component\n"
        "  source_component:\n"
        "    executable: python\n"
        "    args: -u -m pds.utils.source_component\n"
        "resources:\n"
        "  source_component:\n"
        "    threads: 1\n"
        "  sink_component:\n"
        "    threads: 1\n"
    )

    config = ymmsl.load(ymmsl_text)

    # set up
    run_dir = RunDir(tmppath / "run")

    # launch MUSCLE Manager with simulation
    manager = Manager(config, run_dir)
    manager.start_instances()
    success = manager.wait()

    # check that all went well
    assert success

    assert data_sink_path.exists()
    with DBEntry(sink_uri, "r") as entry:
        assert all(entry.get("core_profiles").time == core_profiles.time)


def test_source_to_hybrid_to_sink(tmpdir, core_profiles):
    data_source_path = (Path(tmpdir) / "source_component_data").absolute()
    data_sink_path = (Path(tmpdir) / "sink_component_data").absolute()
    data_hybrid_source_path = (Path(tmpdir) / "source_hybrid_component_data").absolute()
    data_hybrid_sink_path = (Path(tmpdir) / "sink_hybrid_component_data").absolute()
    source_uri = f"imas:hdf5?path={data_source_path}"
    sink_uri = f"imas:hdf5?path={data_sink_path}"
    hybrid_source_uri = f"imas:hdf5?path={data_hybrid_source_path}"
    hybrid_sink_uri = f"imas:hdf5?path={data_hybrid_sink_path}"
    with DBEntry(source_uri, "w") as entry:
        entry.put(core_profiles)
    with DBEntry(hybrid_source_uri, "w") as entry:
        entry.put(core_profiles)
    tmppath = Path(str(tmpdir))
    # make config
    ymmsl_text = (
        "ymmsl_version: v0.1\n"
        "model:\n"
        "  name: test_model\n"
        "  components:\n"
        "    source_component:\n"
        "      implementation: source_component\n"
        "      ports:\n"
        "        o_i: [core_profiles_out]\n"
        "    sink_component:\n"
        "      implementation: sink_component\n"
        "      ports:\n"
        "        f_init: [core_profiles_in]\n"
        "    hybrid_component:\n"
        "      implementation: hybrid_component\n"
        "      ports:\n"
        "        f_init: [core_profiles_in]\n"
        "        o_f: [core_profiles_out]\n"
        "  conduits:\n"
        "    source_component.core_profiles_out: hybrid_component.core_profiles_in\n"
        "    hybrid_component.core_profiles_out: sink_component.core_profiles_in\n"
        "settings:\n"
        f"  source_component.source_uri: {source_uri}\n"
        f"  sink_component.sink_uri: {sink_uri}\n"
        f"  hybrid_component.source_uri: {hybrid_source_uri}\n"
        f"  hybrid_component.sink_uri: {hybrid_sink_uri}\n"
        "implementations:\n"
        "  sink_component:\n"
        "    executable: python\n"
        "    args: -u -m pds.utils.sink_component\n"
        "  source_component:\n"
        "    executable: python\n"
        "    args: -u -m pds.utils.source_component\n"
        "  hybrid_component:\n"
        "    executable: python\n"
        "    args: -u -m pds.utils.sink_source_component\n"
        "resources:\n"
        "  source_component:\n"
        "    threads: 1\n"
        "  sink_component:\n"
        "    threads: 1\n"
        "  hybrid_component:\n"
        "    threads: 1\n"
    )

    config = ymmsl.load(ymmsl_text)

    # set up
    run_dir = RunDir(tmppath / "run")

    # launch MUSCLE Manager with simulation
    manager = Manager(config, run_dir)
    manager.start_instances()
    success = manager.wait()

    # check that all went well
    assert success

    assert data_sink_path.exists()
    assert data_hybrid_sink_path.exists()
    with DBEntry(sink_uri, "r") as entry:
        assert all(entry.get("core_profiles").time == core_profiles.time)
    with DBEntry(hybrid_sink_uri, "r") as entry:
        assert all(entry.get("core_profiles").time == core_profiles.time)
