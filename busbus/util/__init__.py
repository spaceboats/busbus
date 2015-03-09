from abc import ABCMeta, abstractmethod
import collections
import os
import six

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
        else:
            raise KeyError(key)


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
