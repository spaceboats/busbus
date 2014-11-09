from busbus import util


class BaseEntity(object):

    def __init__(self, provider, **kwargs):
        self._provider = provider

        for attr in getattr(self, '__attrs__', []):
            setattr(self, attr, kwargs.get(attr, None))

        provider._new_entity(self)

    def __repr__(self, args=['id']):
        return u'<{0}({1})>'.format(
            util.clsname(self),
            ','.join('{0}={1!r}'.format(i, getattr(self, i)) for i in args))

    def to_dict(self):
        return dict((attr, getattr(self, attr)) for attr in self.__attrs__
                    if getattr(self, attr))
