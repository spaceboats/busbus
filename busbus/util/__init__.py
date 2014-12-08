from abc import ABCMeta, abstractmethod
import six

import busbus


@six.add_metaclass(ABCMeta)
class Iterable(object):

    def __iter__(self):
        return self

    @abstractmethod
    def __next__(self):
        return NotImplemented

    # Python 2 compatibility
    def next(self):
        return self.__next__()


def entity_type(obj):
    try:
        if not isinstance(obj, type):
            obj = type(obj)
        return next(x for x in obj.mro() if x in busbus.ENTITIES)
    except StopIteration:
        raise TypeError


def clsname(obj):
    return '{0}.{1}'.format(type(obj).__module__, type(obj).__name__)
