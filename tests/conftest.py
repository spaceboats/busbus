import busbus
from busbus.provider import ProviderBase
from busbus.provider.gtfs import GTFSMixin

import arrow
import contextlib
try:
    # prefer the stdlib version of mock (>= 3.3)
    import unittest.mock as mock
except ImportError:
    import mock
import os
from pkg_resources import resource_listdir, resource_string
import pytest
import responses
import six
import zipfile


def mock_gtfs_zip(name):
    path = os.path.join('data', name, 'gtfs')
    with contextlib.closing(six.BytesIO()) as zipdata:
        with zipfile.ZipFile(zipdata, 'w') as z:
            for filename in resource_listdir(__name__, path):
                s = resource_string(__name__, os.path.join(path, filename))
                z.writestr(filename, s)
        return zipdata.getvalue()


class SampleGTFSProvider(GTFSMixin, ProviderBase):
    gtfs_url = ('https://developers.google.com/transit/gtfs/examples/'
                'sample-feed.zip')

    def __init__(self, engine=None):
        # https://developers.google.com/transit/gtfs/examples/gtfs-feed
        # FIXME We should eventually roll our own GTFS feed as well in order to
        # test everything
        super(SampleGTFSProvider, self).__init__(engine, self.gtfs_url)

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
@responses.activate
def provider(engine):
    responses.add(responses.GET, SampleGTFSProvider.gtfs_url,
                  body=mock_gtfs_zip('_sample'), status=200,
                  content_type='application/zip')
    return SampleGTFSProvider(engine)
