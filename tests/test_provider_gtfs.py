from conftest import SampleGTFSProvider

import busbus
from busbus.provider.gtfs import GTFSService

import arrow
import datetime
import pytest
import six


def test_provider_without_engine():
    SampleGTFSProvider()


def test_engine_has_one_provider(engine, provider):
    assert len(engine._providers) == 1


def test_provider_get_default(provider):
    assert provider.get(GTFSService, u'The weather in london', None) == None


entity_len_params = [
    ('agencies', 1),
    ('stops', 9),
    ('routes', 5),
    # keep in mind this is from 2007-06-03T06:45:00-07:00 to 09:45:00
    ('arrivals', 141),
]


@pytest.mark.parametrize('attr,count', entity_len_params)
def test_entity_len_engine(engine, attr, count):
    assert len(list(getattr(engine, attr))) == count


@pytest.mark.parametrize('attr,count', entity_len_params)
def test_entity_len_provider(provider, attr, count):
    assert len(list(getattr(provider, attr))) == count


def test_stops_etc(provider):
    stop = next(provider.stops)
    # Empty CSV fields should be coerced to None
    assert stop.description is None
    # stops.txt inherits agency timezone if blank
    assert stop.timezone == 'America/Los_Angeles'


def test_stops_no_children(provider):
    # none of the stops have children
    for stop in provider.stops:
        assert len(list(stop.children)) == 0


def test_agencies_unicode(provider):
    """
    Our CSV parser should be reading everything in as Unicode.
    """
    for agency in provider.agencies:
        for attr in agency.__attrs__:
            if getattr(agency, attr):
                assert isinstance(getattr(agency, attr), six.text_type)


def test_stops_latlon(provider):
    for stop in provider.stops:
        assert isinstance(stop.latitude, float)
        assert isinstance(stop.longitude, float)


def test_routes_agency(provider):
    for route in provider.routes:
        assert route.agency.id == 'DTA'


def test_service(provider):
    assert len(provider._gtfs_entities[GTFSService]) == 2
    fullw = provider.get(GTFSService, u'FULLW')
    assert len(fullw.removed_dates) == 1


@pytest.mark.parametrize('time,stop_id,count', [
    # for STAGECOACH, 06:45-09:45:
    # STBA: 6 arrivals (every half hour)
    # CITY1: 2 arrivals from 06:45-07:59 (every half hour)
    #       10 arrivals from 08:00-09:45 (every 10 minutes)
    # CITY2: same, plus another arrival from the 06:30 trip
    # Sunday
    ('2007-06-03T06:45:00-07:00', u'STAGECOACH', 31),
    ('2007-06-03T06:45:00-07:00', u'AMV', 1),
    # Monday (FULLW exception)
    ('2007-06-04T06:45:00-07:00', u'STAGECOACH', 0),
    ('2007-06-04T06:45:00-07:00', u'AMV', 0),
    # Tuesday
    ('2007-06-05T06:45:00-07:00', u'STAGECOACH', 31),
    ('2007-06-05T06:45:00-07:00', u'AMV', 0)
])
def test_valid_arrivals(provider, time, stop_id, count):
    time = arrow.get(time)
    stop = provider.get(busbus.Stop, stop_id)
    assert (len(list(provider.arrivals.where(stop=stop, start_time=time))) ==
            count)


@pytest.mark.parametrize('time,count', [
    (arrow.get('2007-06-03T06:45:00-07:00'), 6),
    # becomes 2007-06-02T17:00:00-07:00
    (datetime.date(2007, 6, 3), 7),
    # becomes 2007-06-03T06:45:00-07:00
    (datetime.datetime(2007, 6, 3, 13, 45), 6),
])
def test_arrivals_weird_kwargs(provider, time, count):
    stop = provider.get(busbus.Stop, u'STAGECOACH')
    route = provider.get(busbus.Route, u'STBA')
    assert (len(list(provider.arrivals.where(stop=stop, route=route,
                                             start_time=time))) == count)


def test_arrivals_end_before_start(provider):
    assert (len(list(provider.arrivals.where(
        start_time=arrow.now(),
        end_time=arrow.now().replace(hours=-3)))) == 0)
