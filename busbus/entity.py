import busbus.provider
from busbus import util

import arrow
import collections
import json


class LazyEntityProperty(object):

    def __init__(self, f, *args, **kwargs):
        self.f = f
        self.args = args
        self.kwargs = kwargs

    def __call__(self):
        return self.f(*self.args, **self.kwargs)


class BaseEntity(object):
    __repr_attrs__ = ('id',)
    __derived__ = False

    def __init__(self, provider, **kwargs):
        self.provider = provider
        self._lazy_properties = {}

        for attr in getattr(self, '__attrs__', []):
            if isinstance(kwargs.get(attr, None), LazyEntityProperty):
                self._lazy_properties[attr] = kwargs[attr]
            else:
                setattr(self, attr, kwargs.get(attr, None))

        if not self.__derived__:
            provider._new_entity(self)

    def __repr__(self):
        return u'<{0}({1})>'.format(
            util.clsname(self), ','.join(
                '{0}={1!r}'.format(i, getattr(self, i))
                for i in self.__repr_attrs__))

    def __getattr__(self, name):
        if name in self._lazy_properties:
            value = self._lazy_properties[name]()
            del self._lazy_properties[name]
            setattr(self, name, value)
            return value
        if '.' in name:  # nested attribute
            return reduce(getattr, name.split('.'), self)
        raise AttributeError(name)

    def __getitem__(self, name):
        try:
            return getattr(self, name)
        except AttributeError:
            raise KeyError(name)

    def keys(self):
        yield 'provider'
        for attr in self.__attrs__:
            if getattr(self, attr):
                yield attr


class BaseEntityJSONEncoder(json.JSONEncoder):

    def default(self, o):
        if isinstance(o, BaseEntity):
            return dict(o)
        elif isinstance(o, busbus.provider.ProviderBase):
            keys = ('id', 'legal', 'credit', 'credit_url', 'country')
            return dict((k, getattr(o, k)) for k in keys if hasattr(o, k))
        elif isinstance(o, arrow.Arrow):
            return o.timestamp
        elif isinstance(o, collections.Iterable):
            return list(o)
        return super(BaseEntityJSONEncoder, self).default(o)
