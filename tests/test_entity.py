import busbus
from busbus.entity import BaseEntityJSONEncoder

import json
import pytest


@pytest.fixture(scope='module')
def agency(provider):
    return next(provider.agencies)


def test_entity_repr(agency):
    assert 'DTA' in repr(agency)


def test_entity_failed_getattr(agency):
    with pytest.raises(AttributeError):
        agency.the_weather_in_london


def test_entity_failed_getitem(agency):
    with pytest.raises(KeyError):
        agency['the_weather_in_london']


def test_entity_to_dict(agency):
    assert dict(agency)['id'] == 'DTA'


def test_entity_to_json(provider):
    json_str = BaseEntityJSONEncoder().encode(next(provider.arrivals))
    json.loads(json_str)


def test_bad_json():
    with pytest.raises(TypeError):
        BaseEntityJSONEncoder().encode(busbus.Engine)
