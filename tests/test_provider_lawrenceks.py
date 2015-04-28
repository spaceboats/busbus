import busbus
from busbus.provider.lawrenceks import LawrenceTransitProvider
from .conftest import mock_gtfs_zip

import arrow
import pytest
import responses


@pytest.fixture(scope='module')
@responses.activate
def lawrenceks_provider(engine):
    responses.add(responses.GET, LawrenceTransitProvider.gtfs_url,
                  body=mock_gtfs_zip('lawrenceks'), status=200,
                  content_type='application/zip')
    return LawrenceTransitProvider(engine)


# test that we are indeed using our local abridged copy of the GTFS feed
def test_len_routes(lawrenceks_provider):
    assert len(list(lawrenceks_provider.routes)) == 1


def test_agency_phone_e164(lawrenceks_provider):
    agency = next(lawrenceks_provider.agencies)
    assert agency.phone_e164 == '+17858644644'


@pytest.mark.parametrize('stop_id,count', [
    (u'15TH_SPAHR_WB', 13),
    (u'SNOW_HALL_WB', 14),
])
def test_43_to_eaton_hall(lawrenceks_provider, stop_id, count):
    stop = lawrenceks_provider.get(busbus.Stop, stop_id)
    route = lawrenceks_provider.get(busbus.Route, u'RT_43')
    assert len(list(lawrenceks_provider.arrivals.where(
        stop=stop, route=route,
        start_time=arrow.get('2015-03-10T14:00:00-05:00'),
        end_time=arrow.get('2015-03-10T16:00:00-05:00')))) == count
