import busbus
from busbus.provider.mbta import MBTAProvider
from .conftest import mock_gtfs_zip

import arrow
import pytest
import responses


@pytest.fixture(scope='module')
@responses.activate
def mbta_provider(engine):
    responses.add(responses.GET, MBTAProvider.gtfs_url,
                  body=mock_gtfs_zip('mbta'), status=200,
                  content_type='application/zip')
    return MBTAProvider('fake API key', engine)


# test that we are indeed using our local abridged copy of the GTFS feed
def test_len_routes(mbta_provider):
    assert len(list(mbta_provider.routes)) == 5


def test_agency_phoneword_e164(mbta_provider):
    agency = mbta_provider.get(busbus.Agency, id=u'2')
    assert agency.phone_e164 == '+18002356426'


def test_bu_central_children(mbta_provider):
    children = list(mbta_provider.get(busbus.Stop, u'place-bucen').children)
    ids = set(c.id for c in children)
    assert ids == set((u'70144', u'70145'))
    for child in children:
        assert child.parent.id == u'place-bucen'


def test_green_to_bu_gtfs(mbta_provider):
    stop = mbta_provider.get(busbus.Stop, u'70144')
    route = mbta_provider.get(busbus.Route, u'Green-B')
    assert len(list(mbta_provider.arrivals.where(
        stop=stop, route=route, realtime=False,
        start_time=arrow.get('2015-03-10T14:00:00-04:00'),
        end_time=arrow.get('2015-03-10T16:00:00-04:00')))) == 17
