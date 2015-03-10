from busbus import util

import itertools


class Queryable(util.Iterable):

    def __init__(self, it, query_funcs=None):
        self.it = iter(it)
        self.query_funcs = tuple(query_funcs) if query_funcs else ()

    def __next__(self):
        while True:
            value = next(self.it)
            if all(query_func(value) for query_func in self.query_funcs):
                return value

    def where(self, query_func=None, **kwargs):
        if not query_func and not kwargs:
            return self
        new_funcs = [query_func] if query_func else []
        for k, v in kwargs.items():
            new_funcs.append(lambda obj: (getattr(obj, k) == v
                                          if hasattr(obj, k) else False))
        return Queryable(self.it, self.query_funcs + tuple(new_funcs))

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
