import busbus
from busbus.provider import ProviderBase
from busbus.provider.gtfs import GTFSMixin

import pytest
import six


class SampleGTFSProvider(GTFSMixin, ProviderBase):

    def __init__(self, engine=None):
        # https://developers.google.com/transit/gtfs/examples/gtfs-feed
        # FIXME We should eventually roll our own GTFS feed as well in order to
        # test everything
        gtfs_url = ('https://developers.google.com/transit/gtfs/examples/'
                    'sample-feed.zip')
        super(SampleGTFSProvider, self).__init__(engine, gtfs_url)


@pytest.fixture(scope='module')
def provider():
    return SampleGTFSProvider()


def test_provider_with_engine():
    SampleGTFSProvider(busbus.Engine())


def test_agencies_len(provider):
    assert len(list(provider.agencies)) == 1


def test_stops_len(provider):
    assert len(list(provider.stops)) == 9

    stop = next(provider.stops)
    # Empty CSV fields should be coerced to None
    assert stop.description is None
    # stops.txt inherits agency timezone if blank
    assert stop.timezone == 'America/Los_Angeles'


def test_routes_len(provider):
    assert len(list(provider.routes)) == 5


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
        assert len(stop.location) == 2
        assert isinstance(stop.location[0], float)
        assert isinstance(stop.location[1], float)


def test_routes_agency(provider):
    for route in provider.routes:
        assert route.agency.id == 'DTA'
