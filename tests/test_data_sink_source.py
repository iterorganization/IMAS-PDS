from pathlib import Path

import ymmsl
from imaspy import DBEntry

from libmuscle.manager.manager import Manager
from libmuscle.manager.run_dir import RunDir


def test_source_to_sink(tmpdir, core_profiles):
    tmppath = Path(str(tmpdir))
    with DBEntry(f"imas:hdf5?path=macro_source", "w") as entry:
        entry.put(core_profiles)
    # make config
    ymmsl_text = (
        'ymmsl_version: v0.1\n'
        'model:\n'
        '  name: test_model\n'
        '  components:\n'
        '    macro:\n'
        '      ports:\n'
        '        o_f: core_profiles_out\n'
        '      implementation: sink_source\n'
        '    micro:\n'
        '      ports:\n'
        '        f_init: core_profiles_in\n'
        '      implementation: sink_source\n'
        '  conduits:\n'
        '    macro.core_profiles_out: micro.core_profiles_in\n'
        'settings:\n'
        '  macro.source_uri: imas:hdf5?path=macro_source\n'
        '  micro.sink_uri: imas:hdf5?path=micro_sink\n'
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

    assert (tmppath / 'micro_sink').exists()
    with DBEntry("imas:hdf5?path=micro_sink", "r") as entry:
        assert entry.get('core_profiles') == core_profiles
