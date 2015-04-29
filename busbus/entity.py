import busbus.provider
from busbus import util

import arrow
import collections
import json
from six.moves import reduce


class LazyEntityProperty(object):

    def __init__(self, f, *args, **kwargs):
        self.f = f
        self.args = args
        self.kwargs = kwargs

    def __call__(self):
        return self.f(*self.args, **self.kwargs)


class BaseEntity(collections.Mapping):
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
        except (AttributeError, TypeError):
            raise KeyError(name)

    def __iter__(self):
        yield 'provider'
        for attr in self.__attrs__:
            if getattr(self, attr, None) is not None:
                yield attr

    def __len__(self):
        return 1 + sum([1 for attr in self.__attrs__
                        if getattr(self, attr, None) is not None])


class BaseEntityJSONEncoder(json.JSONEncoder):

    def default(self, o):
        if isinstance(o, (BaseEntity, busbus.provider.ProviderBase)):
            return dict(o)
        elif isinstance(o, arrow.Arrow):
            return o.timestamp
        elif isinstance(o, collections.Iterable):
            return list(o)
        return super(BaseEntityJSONEncoder, self).default(o)
