import busbus

import os
import pytest
import tempfile


def test_engine_busbus_dir_exists():
    dir = tempfile.mkdtemp()
    engine = busbus.Engine({'busbus_dir': dir})
    os.rmdir(dir)


def test_engine_busbus_dir_other_error():
    outerdir = tempfile.mkdtemp()
    dir = os.path.join(outerdir, 'inner')
    os.mkdir(dir)
    old_mode = os.stat(outerdir).st_mode
    os.chmod(outerdir, int('400', 8))
    with pytest.raises(OSError):
        engine = busbus.Engine({'busbus_dir': dir})
    os.chmod(outerdir, old_mode)
    os.rmdir(dir)
    os.rmdir(outerdir)
