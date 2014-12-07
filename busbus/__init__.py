from busbus.entity import BaseEntity

import errno
import os
import six


class Engine(object):
    """
    The busbus.Engine manages data providers and allows querying entities and
    subscribing to entity events the providers.
    """
    providers = []
    config = {}

    def __init__(self):
        self.config['busbus_dir'] = os.path.join(os.getenv('HOME'), '.busbus')

        try:
            os.mkdir(self.config['busbus_dir'])
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise

        # The saved CacheControl objects are pickled using the highest
        # protocol, which is different between Python 2 and 3.
        self.config['url_cache_dir'] = os.path.join(
            self.config['busbus_dir'], 'cache3' if six.PY3 else 'cache')

    def register_provider(self, provider):
        self.providers.append(provider)


class Agency(BaseEntity):
    __attrs__ = ('id', 'name', 'url', 'timezone', 'lang', 'phone_e164',
                 'phone_human', 'fare_url')


class Stop(BaseEntity):
    __attrs__ = ('id', 'code', 'name', 'description', 'location', 'zone',
                 'url', 'parent', 'timezone', 'accessible')

    @property
    def children(self):
        return self._provider.stops.where(lambda s: s.parent == self)


class Route(BaseEntity):
    __attrs__ = ('id', 'agency', 'short_name', 'name', 'description', 'type',
                 'url', 'color', 'text_color')


ENTITIES = (Agency, Stop, Route)
