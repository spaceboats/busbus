import busbus
from busbus.provider import ProviderBase
from busbus.provider.gtfs import GTFSMixin

import arrow
try:
    # prefer the stdlib version of mock (>= 3.3)
    import unittest.mock as mock
except ImportError:
    import mock
import pytest


class SampleGTFSProvider(GTFSMixin, ProviderBase):

    def __init__(self, engine=None):
        # https://developers.google.com/transit/gtfs/examples/gtfs-feed
        # FIXME We should eventually roll our own GTFS feed as well in order to
        # test everything
        gtfs_url = ('https://developers.google.com/transit/gtfs/examples/'
                    'sample-feed.zip')
        super(SampleGTFSProvider, self).__init__(engine, gtfs_url)

    @property
    def arrivals(self):
        # Set a current time that fits within the sample feed's dates
        with mock.patch('arrow.now') as mock_now:
            mock_now.return_value = arrow.get('2007-06-03T06:45:00-07:00')
            return super(SampleGTFSProvider, self).arrivals


@pytest.fixture(scope='session')
def engine_config():
    return {
        'gtfs_db_path': ':memory:',
    }


@pytest.fixture(scope='session')
def engine(engine_config):
    return busbus.Engine(engine_config)


@pytest.fixture(scope='session')
def provider(engine):
    return SampleGTFSProvider(engine)
