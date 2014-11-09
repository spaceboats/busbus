from busbus import util


class Queryable(util.Iterable):

    def __init__(self, it, query_funcs=None):
        self.it = iter(it)
        if query_funcs:
            self.query_funcs = tuple(query_funcs)
        else:
            self.query_funcs = ()

    def __next__(self):
        while True:
            value = next(self.it)
            if not self.query_funcs or \
                    any(query_func(value) for query_func in self.query_funcs):
                return value

    def where(self, query_func):
        return Queryable(self.it, self.query_funcs + (query_func,))
