from busbus import util

from copy import copy
import itertools


def check_obj_attrs(obj, mapping):
    for k, v in mapping.items():
        if hasattr(obj, k):
            if getattr(obj, k) != v:
                return False
        elif (hasattr(obj, '__getitem__') and
              hasattr(obj, '__contains__')):
            if not (k in obj and obj[k] == v):
                return False
        else:
            return False
    return True


class Queryable(util.Iterable):

    def __init__(self, it, query_funcs=None, **kwargs):
        self.it = iter(it)
        self.query_funcs = tuple(query_funcs) if query_funcs else ()
        self.kwargs = kwargs

    def __next__(self):
        while True:
            value = next(self.it)
            if (check_obj_attrs(value, self.kwargs) and
                    all(query_func(value) for query_func in self.query_funcs)):
                return value

    def _new(self, query_funcs, kwargs):
        return Queryable(self.it, query_funcs, **kwargs)

    def where(self, query_func=None, **kwargs):
        if not query_func and not kwargs:
            return self
        new_funcs = self.query_funcs + ((query_func,) if query_func else ())
        new_kwargs = copy(self.kwargs)
        new_kwargs.update(kwargs)
        return self._new(new_funcs, new_kwargs)

    @staticmethod
    def chain(*its):
        return ChainedQueryable(*its)


class ChainedQueryable(Queryable):

    def __init__(self, *its):
        self.its = its
        self.it = itertools.chain(*its)

    def __next__(self):
        return next(self.it)

    def where(self, query_func=None, **kwargs):
        its = []
        for it in self.its:
            its.append(it.where(query_func, **kwargs))
        return ChainedQueryable(*its)
