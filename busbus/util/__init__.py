from abc import ABCMeta, abstractmethod
import collections
from datetime import datetime, timedelta
import math
import os
import requests
import six
import time

import busbus.entity


@six.add_metaclass(ABCMeta)
class Iterable(object):

    def __iter__(self):
        return self

    @abstractmethod
    def __next__(self):
        """Provide the next item from the iterator in this method."""

    # Python 2 compatibility
    def next(self):
        return self.__next__()


class Config(collections.defaultdict):

    def __init__(self, config=None):
        if config:
            for k, v in config.items():
                self[k] = v
        super(Config, self).__init__()

    def __missing__(self, key):
        if key == 'busbus_dir':
            if os.getenv('HOME'):
                return os.path.join(os.getenv('HOME'), '.busbus')
            else:
                return os.path.join(os.getcwd(), '.busbus')
        elif key == 'url_cache_dir':
            return os.path.join(self['busbus_dir'], 'cache')
        elif key == 'gtfs_db_path':
            return os.path.join(self['busbus_dir'], 'gtfs.sqlite3')
        else:
            raise KeyError(key)


class RateLimitRequests(requests.Session):
    """
    requests.Session subclass that implements rate limiting, both for all
    requests on this session as well as separate rate limits for each
    individual request.
    """

    def __init__(self, interval=0, url_interval=0):
        self._cache = {}
        self._last_request = datetime.min
        self._interval = timedelta(seconds=interval)
        self._url_interval = timedelta(seconds=url_interval)

        super(RateLimitRequests, self).__init__()

    def request(self, *args, **kwargs):
        key = freezehash((args, kwargs))
        if key in self._cache:
            t, resp = self._cache[key]
            if datetime.now() - t <= self._url_interval:
                return resp
        time.sleep(max((self._last_request + self._interval -
                        datetime.now()).total_seconds(), 0))
        resp = super(RateLimitRequests, self).request(*args, **kwargs)
        t = datetime.now()
        self._cache[key] = (t, resp)
        self._last_request = t
        return resp


def entity_type(obj):
    """Return the type just above BaseEntity in method resolution order."""
    if not isinstance(obj, type):
        obj = type(obj)
    mro = obj.mro()
    if busbus.entity.BaseEntity in mro:
        index = mro.index(busbus.entity.BaseEntity)
        if index == 0:
            raise TypeError(obj)
        else:
            return mro[index - 1]
    else:
        raise TypeError(obj)


def clsname(obj):
    return '{0}.{1}'.format(type(obj).__module__, type(obj).__name__)


def freezehash(obj):
    if isinstance(obj, (dict, collections.Mapping)):
        return hash(frozenset((k, freezehash(v)) for k, v in obj.items()))
    elif isinstance(obj, (tuple, list, set)):
        return hash(frozenset(freezehash(x) for x in obj))
    else:
        return hash(obj)


def dist(lat1, lon1, lat2, lon2):
    """
    Returns the distance between two latitude/longitude pairs in
    meters.
    """
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    return math.acos(math.sin(lat1) * math.sin(lat2) +
                     math.cos(lat1) * math.cos(lat2) *
                     math.cos(abs(lon2 - lon1))) * 6371000
