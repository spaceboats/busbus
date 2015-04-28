import busbus
from busbus.util import clsname

from abc import ABCMeta, abstractmethod, abstractproperty
from cachecontrol import CacheControl
from cachecontrol.caches import FileCache
import hashlib
import requests
import six
import uuid


@six.add_metaclass(ABCMeta)
class ProviderBase(object):

    # Defines the minimum polling interval. Many transit data providers define
    # a minimum polling interval. Defaults to 30 seconds.
    poll_interval = 30

    def __init__(self, engine, **kwargs):
        self.id = hashlib.sha1(six.b(
            '{0}:{1!r}'.format(clsname(self), kwargs.get('__init_args__', {}))
        )).hexdigest()

        if engine:
            self.engine = engine
        else:
            self.engine = busbus.Engine()
        self.engine._register_provider(self)

        self._requests = requests.Session()

        # This requests session object, wrapped with CacheControl, is useful
        # for long-term storage of larger files, such as GTFS data.
        self._cached_requests = CacheControl(self._requests, cache=FileCache(
            self.engine.config['url_cache_dir']))

    def _new_entity(self, entity):
        """
        Method to receive knowledge of a new entity -- does nothing if not
        overridden
        """

    @abstractmethod
    def get(self, entity, id, default=None):
        """Return the requested entity, or default if it doesn't exist"""

    @abstractproperty
    def agencies(self):
        """Return an iterator of the agencies for this provider"""

    @abstractproperty
    def stops(self):
        """Return an iterator of the stops for this provider"""

    @abstractproperty
    def routes(self):
        """Return an iterator of the routes for this provider"""

    @abstractproperty
    def arrivals(self):
        """Return an iterator of the arrivals for this provider"""

    @property
    def alerts(self):
        """Return an iterator of current alerts for this provider"""
        return iter(())

    def __getitem__(self, name):
        try:
            return getattr(self, name)
        except AttributeError:
            raise KeyError(name)

    def keys(self):
        for attr in ('id', 'legal', 'credit', 'credit_url', 'country'):
            if getattr(self, attr, None) is not None:
                yield attr
