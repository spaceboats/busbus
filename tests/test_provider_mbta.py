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
    stop = mbta_provider.get(busbus.Stop, u'place-bucen')
    route = mbta_provider.get(busbus.Route, u'Green-B')
    assert len(list(mbta_provider.arrivals.where(
        stop=stop, route=route, realtime=False,
        start_time=arrow.get('2015-03-10T14:00:00-04:00'),
        end_time=arrow.get('2015-03-10T16:00:00-04:00')))) == 32


def test_realtime_too_many_requests(mbta_provider):
    with pytest.raises(ValueError):
        next(mbta_provider.arrivals)


def realtime_response_arrs(p, start, stop_id=None, route_id=None):
    status = 200
    kwargs = {'start_time': arrow.get(start)}

    if stop_id is None and route_id is None:
        raise ValueError()
    elif route_id is None:
        endpoint = 'predictionsbystop'
        filename = '{0}_{1}_{2}.json'.format(endpoint, stop_id, start)
    else:
        endpoint = 'predictionsbyroute'
        filename = '{0}_{1}_{2}.json'.format(endpoint, route_id, start)

    if filename == ('predictionsbyroute_Logan-22_'
                    '2015-05-01T17:12:21-05:00.json'):
        status = 404

    if stop_id is not None:
        kwargs['stop'] = p.get(busbus.Stop, stop_id)
    if route_id is not None:
        kwargs['route'] = p.get(busbus.Route, route_id)

    url = p.mbta_realtime_url + endpoint
    data = resource_string(__name__, os.path.join('data', 'mbta', filename))

    responses.add(responses.GET, url, status=status, body=data,
                  content_type='application/json; charset=utf-8')
    return p.arrivals.where(**kwargs)


@responses.activate
def test_realtime_39(mbta_provider):
    arrs = list(realtime_response_arrs(
        mbta_provider, '2015-05-01T15:10:23-05:00', route_id='39'))
    assert arrs[0].realtime is True
    assert arrs[0].time == arrow.get(1430511060)
    assert len(set(arr.stop.id for arr in arrs)) > 1


@responses.activate
def test_realtime_39_forest_hills(mbta_provider):
    arrs = list(realtime_response_arrs(
        mbta_provider, '2015-05-01T15:10:23-05:00',
        route_id='39', stop_id='8750'))
    assert len(arrs) == 57
    assert arrs[0].realtime is True
    assert arrs[0].time == arrow.get(1430511060)
    # MBTA doesn't provide realtime data for ~3 hours into the future
    assert arrs[-1].realtime is False


@responses.activate
def test_realtime_downtown_crossing(mbta_provider):
    arrs = list(realtime_response_arrs(
        mbta_provider, '2015-05-02T00:04:05-05:00', stop_id='place-dwnxg'))
    # this query was performed late at night when all remaining arrivals should
    # have realtime data (5 orange line, 5 red line arrivals returned)
    assert len(arrs) == 5
    assert all(arr.realtime is True for arr in arrs)
    # although the response contains red line arrivals, we removed the red line
    # from our abridged version of the feed
    assert all(arr.route.id == 'Orange' for arr in arrs)


@responses.activate
def test_realtime_logan_22(mbta_provider):
    arrs = list(realtime_response_arrs(
        mbta_provider, '2015-05-01T17:12:21-05:00', route_id='Logan-22'))
    assert len(arrs) == 120
    assert all(arr.realtime is False for arr in arrs)


@responses.activate
def test_predictionsbyroute_children(mbta_provider):
    arrs = list(realtime_response_arrs(
        mbta_provider, '2015-05-01T15:08:18-05:00',
        stop_id='place-dwnxg', route_id='Orange'))
    assert len(arrs) > 0
