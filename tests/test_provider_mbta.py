import busbus
from busbus.provider.mbta import MBTAProvider
from .conftest import mock_gtfs_zip

import arrow
import os
from pkg_resources import resource_string
import pytest
import responses
from six.moves import urllib


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


@responses.activate
def test_realtime_39_forest_hills(mbta_provider):
    stop = mbta_provider.get(busbus.Stop, u'8750')
    route = mbta_provider.get(busbus.Route, u'39')
    start = '2015-05-01T15:10:23-05:00'

    endpoint = 'predictionsbyroute'
    url = mbta_provider.mbta_realtime_url + endpoint

    filename = '{0}_{1}_{2}.json'.format(endpoint, route.id, start)
    data = resource_string(__name__, os.path.join('data', 'mbta', filename))

    responses.add(responses.GET, url, status=200, body=data,
                  content_type='application/json; charset=utf-8')

    arrs = list(mbta_provider.arrivals.where(
        stop=stop, route=route, start_time=arrow.get(start)))
    assert arrs[0].realtime == True
    assert arrs[0].time == arrow.get(1430511060)
    # MBTA doesn't provide realtime data for ~3 hours into the future
    assert arrs[-1].realtime == False
