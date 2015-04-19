import busbus
from busbus.provider import ProviderBase
from busbus.provider.gtfs import GTFSMixin

import arrow
import pytest


class SampleGTFSProvider(GTFSMixin, ProviderBase):

    def __init__(self, engine=None):
        # https://developers.google.com/transit/gtfs/examples/gtfs-feed
        # FIXME We should eventually roll our own GTFS feed as well in order to
        # test everything
        gtfs_url = ('https://developers.google.com/transit/gtfs/examples/'
                    'sample-feed.zip')
        super(SampleGTFSProvider, self).__init__(engine, gtfs_url)

    def _build_arrivals(self, kw):
        # Set a default start_time that fits within the sample feed's dates
        if 'start_time' not in kw:
            kw['start_time'] = arrow.get('2007-06-03T06:45:00-07:00')
        return super(SampleGTFSProvider, self)._build_arrivals(kw)


@pytest.fixture(scope='session')
def engine():
    return busbus.Engine()


@pytest.fixture(scope='session')
def provider(engine):
    return SampleGTFSProvider(engine)
