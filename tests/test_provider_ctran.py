import busbus
from busbus.provider.ctran import CTranProvider
from .conftest import mock_gtfs_zip

import arrow
import pytest
import responses


@pytest.fixture(scope='module')
@responses.activate
def ctran_provider(engine):
    responses.add(responses.GET, CTranProvider.gtfs_url,
                  body=mock_gtfs_zip('ctran'), status=200,
                  content_type='application/zip')
    return CTranProvider(engine)


# test that we are indeed using our local abridged copy of the GTFS feed
def test_len_routes(ctran_provider):
    assert len(list(ctran_provider.routes)) == 28


@pytest.mark.parametrize('stop_id,count', [
    (u'2058', 4)
])
def test_43_to_eaton_hall(ctran_provider, stop_id, count):
    stop = ctran_provider.get(busbus.Stop, stop_id)
    route = ctran_provider.get(busbus.Route, u'46')
    assert len(list(ctran_provider.arrivals.where(
        stop=stop, route=route,
        start_time=arrow.get('2015-03-10T14:00:00-05:00'),
        end_time=arrow.get('2015-03-10T16:00:00-05:00')))) == count
