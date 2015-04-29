from .conftest import SampleGTFSProvider

import busbus
from busbus.provider import ProviderBase
from busbus.provider.gtfs import SQLEntityMixin
from busbus.util import Config

import arrow
from collections import OrderedDict
import datetime
import mock
import pytest
import six


def test_provider_without_engine():
    class TestProvider(ProviderBase):

        def get(self, *args, **kwargs):
            raise NotImplementedError

        @property
        def agencies(self):
            raise NotImplementedError

        @property
        def routes(self):
            raise NotImplementedError

        @property
        def stops(self):
            raise NotImplementedError

        @property
        def arrivals(self):
            raise NotImplementedError

    TestProvider(None)


def test_default_gtfs_db_path():
    c = Config({'busbus_dir': '/tmp/busbus'})
    assert c['gtfs_db_path'] == '/tmp/busbus/gtfs.sqlite3'


def test_already_imported(provider):
    e = busbus.Engine({'gtfs_db_path': provider.conn})
    p = SampleGTFSProvider(e)
    assert provider.feed_id == p.feed_id
    assert len(list(provider.agencies)) == 1


def test_engine_has_one_provider(engine, provider):
    assert len(engine._providers) == 1


@pytest.mark.parametrize('entity', (None, busbus.Stop, busbus.Arrival))
def test_provider_get_default(provider, entity):
    assert provider.get(entity, u'The weather in london',
                        'asdfjkl') == 'asdfjkl'


def test_sql_entity_mixin_build_select():
    class FakeEntity(SQLEntityMixin):
        __table__ = 'fake'
        __field_map__ = OrderedDict([
            ('lorem', 'ipsum'),
            ('foo', 'bar'),
        ])

    assert (FakeEntity._build_select([]) ==
            'select ipsum as lorem, bar as foo from fake')
    assert (FakeEntity._build_select(['_feed_url', 'fake_id']) ==
            ('select ipsum as lorem, bar as foo from fake '
             'where _feed_url=? and fake_id=?'))


def test_sql_entity_eq(provider):
    class FakeEntity(SQLEntityMixin):
        pass

    a1 = provider.get(busbus.Agency, u'DTA')
    assert a1 == a1
    assert a1 is a1
    assert a1 != 'the weather in london'
    assert a1 != FakeEntity()
    a2 = provider.get(busbus.Agency, u'DTA')
    assert a1 == a2
    assert a2 == a1
    assert a1 is not a2


entity_len_params = [
    ('agencies', 1),
    ('stops', 9),
    ('routes', 5),
    # keep in mind this is from 2007-06-03T06:45:00-07:00 to 09:45:00
    ('arrivals', 139),
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


def test_stops_no_children_base(provider):
    stop = next(provider.stops)
    stop = busbus.Stop(**dict(stop))
    print(type(stop))
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


@pytest.mark.parametrize('time,stop_id,count', [
    # for STAGECOACH, 06:45-09:45:
    # STBA: 6 arrivals (every half hour)
    # CITY1: 2 arrivals from 06:45-07:59 (every half hour)
    #       10 arrivals from 08:00-09:45 (every 10 minutes)
    # CITY2: 3 arrivals from 06:45-07:59 (trip start time)
    #        9 arrivals from 08:00-09:45 (trip start time)
    # Sunday
    ('2007-06-03T06:45:00-07:00', u'STAGECOACH', 30),
    ('2007-06-03T06:45:00-07:00', u'AMV', 1),
    # Monday (FULLW exception)
    ('2007-06-04T06:45:00-07:00', u'STAGECOACH', 0),
    ('2007-06-04T06:45:00-07:00', u'AMV', 0),
    # Tuesday
    ('2007-06-05T06:45:00-07:00', u'STAGECOACH', 30),
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
    # test dotted kwargs
    assert (len(list(provider.arrivals.where(
        **{'stop.id': u'STAGECOACH', 'route.id': u'STBA', 'start_time': time}
    ))) == count)


def test_arrivals_end_before_start(provider):
    assert (len(list(provider.arrivals.where(
        start_time=arrow.now(),
        end_time=arrow.now().replace(hours=-3)))) == 0)
