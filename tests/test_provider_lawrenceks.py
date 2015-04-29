import busbus
from busbus.provider.lawrenceks import LawrenceTransitProvider

import arrow
import pytest


@pytest.fixture(scope='module')
def lawrenceks_provider(engine):
    return LawrenceTransitProvider(engine)


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
