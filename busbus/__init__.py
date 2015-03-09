from busbus.entity import BaseEntity
from busbus.queryable import Queryable
from busbus.util import Config

import errno
import os
import six


class Engine(object):
    """
    The busbus.Engine manages data providers and allows querying entities and
    subscribing to entity events the providers.
    """

    def __init__(self, config=None):
        self.config = Config(config)
        self.providers = {}

        try:
            os.mkdir(self.config['busbus_dir'])
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise

    def _register_provider(self, provider):
        self.providers[provider._uuid] = provider

    @property
    def agencies(self):
        return Queryable.chain(*[p.agencies for p in self.providers.values()])

    @property
    def stops(self):
        return Queryable.chain(*[p.stops for p in self.providers.values()])

    @property
    def routes(self):
        return Queryable.chain(*[p.routes for p in self.providers.values()])

    @property
    def arrivals(self):
        return Queryable.chain(*[p.arrivals for p in self.providers.values()])


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


class Arrival(BaseEntity):
    __attrs__ = ('route', 'stop', 'time', 'departure_time', 'headsign',
                 'short_name', 'bikes_ok')
    __repr_attrs__ = ('route', 'stop', 'time')


ENTITIES = (Agency, Stop, Route, Arrival)
