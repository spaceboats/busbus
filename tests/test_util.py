import busbus
from busbus import util

import pytest


def test_util_clsname():
    engine = busbus.Engine()
    assert util.clsname(engine) == 'busbus.Engine'


def test_util_entity_type_error():
    engine = busbus.Engine()
    with pytest.raises(TypeError):
        busbus.util.entity_type(engine)
