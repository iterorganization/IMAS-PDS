from pathlib import Path

import ymmsl
from imaspy import DBEntry

from libmuscle.manager.manager import Manager
from libmuscle.manager.run_dir import RunDir
from pds import get_project_root


def test_source_to_sink(tmpdir, core_profiles):
    data_source_path = (Path(get_project_root()) / 'macro_source').absolute()
    data_sink_path = (Path(get_project_root()) / 'micro_sink').absolute()
    source_uri = f"imas:hdf5?path={data_source_path}"
    sink_uri = f"imas:hdf5?path={data_sink_path}"
    with DBEntry(source_uri, "w") as entry:
        entry.put(core_profiles)
    tmppath = Path(str(tmpdir))
    # make config
    ymmsl_text = (
        'ymmsl_version: v0.1\n'
        'model:\n'
        '  name: test_model\n'
        '  components:\n'
        '    macro:\n'
        '      implementation: sink_source\n'
        '      ports:\n'
        '        o_i: [core_profiles_out]\n'
        '    micro:\n'
        '      implementation: sink_source\n'
        '      ports:\n'
        '        f_init: [core_profiles_in]\n'
        '  conduits:\n'
        '    macro.core_profiles_out: micro.core_profiles_in\n'
        'settings:\n'
        f"  macro.source_uri: {source_uri}\n"
        f"  micro.sink_uri: {sink_uri}\n"
        'implementations:\n'
        '  sink_source:\n'
        '    executable: python\n'
        '    args: -u -m pds.utils.data_sink_source\n'
        'resources:\n'
        '  macro:\n'
        '    threads: 1\n'
        '  micro:\n'
        '    threads: 1\n'
    )

    config = ymmsl.load(ymmsl_text)

    # set up
    run_dir = RunDir(tmppath / 'run')

    # launch MUSCLE Manager with simulation
    manager = Manager(config, run_dir)
    manager.start_instances()
    success = manager.wait()

    # check that all went well
    assert success

    assert data_sink_path.exists()
    with DBEntry(sink_uri, "r") as entry:
        assert entry.get('core_profiles') == core_profiles
