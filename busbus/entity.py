from busbus import util


class LazyEntityProperty(object):

    def __init__(self, f, *args, **kwargs):
        self.f = f
        self.args = args
        self.kwargs = kwargs

    def __call__(self):
        return self.f(*self.args, **self.kwargs)


class BaseEntity(object):

    def __init__(self, provider, **kwargs):
        self._provider = provider
        self._lazy_properties = {}

        for attr in getattr(self, '__attrs__', []):
            if isinstance(kwargs.get(attr, None), LazyEntityProperty):
                self._lazy_properties[attr] = kwargs[attr]
            else:
                setattr(self, attr, kwargs.get(attr, None))

        provider._new_entity(self)

    def __repr__(self, args=['id']):
        return u'<{0}({1})>'.format(
            util.clsname(self),
            ','.join('{0}={1!r}'.format(i, getattr(self, i)) for i in args))

    def __getattr__(self, name):
        if name in self._lazy_properties:
            value = self._lazy_properties[name]()
            del self._lazy_properties[name]
            setattr(self, name, value)
            return value
        else:
            raise AttributeError()

    def to_dict(self):
        return dict((attr, getattr(self, attr)) for attr in self.__attrs__
                    if getattr(self, attr))
