import busbus

from abc import ABCMeta, abstractmethod, abstractproperty
from cachecontrol import CacheControl
from cachecontrol.caches import FileCache
import requests
import six


@six.add_metaclass(ABCMeta)
class ProviderBase(object):

    # Defines the minimum polling interval. Many transit data providers define
    # a minimum polling interval. Defaults to 30 seconds.
    poll_interval = 30

    def __init__(self, engine):
        if engine:
            self.engine = engine
        else:
            self.engine = busbus.Engine()
        self.engine.register_provider(self)

        self._requests = requests.Session()

        # This requests session object, wrapped with CacheControl, is useful
        # for long-term storage of larger files, such as GTFS data.
        self._cached_requests = CacheControl(self._requests, cache=FileCache(
            self.engine.config['url_cache_dir']))

    @abstractmethod
    def _new_entity(self, entity):
        return NotImplemented

    @abstractmethod
    def get(self, entity, id, default=None):
        return NotImplemented

    @abstractproperty
    def agencies(self):
        return NotImplemented

    @abstractproperty
    def stops(self):
        return NotImplemented

    @abstractproperty
    def routes(self):
        return NotImplemented
