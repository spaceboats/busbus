import busbus
from busbus.queryable import Queryable
from busbus import util

from abc import ABCMeta, abstractmethod
import arrow
import datetime
import six


@six.add_metaclass(ABCMeta)
class ArrivalGeneratorBase(util.Iterable):

    def __init__(self, provider, stops, routes, start, end):
        self.provider = provider
        self.stops = stops
        self.routes = routes
        self.start = (arrow.now() if start is None
                      else arrow.get(start)).to(provider._timezone)
        self.end = (self.start.replace(hours=3) if end is None
                    else arrow.get(end)).to(provider._timezone)

    @abstractmethod
    def __next__(self):
        """Provide the next arrival."""


class ArrivalQueryable(Queryable):

    def __init__(self, provider, arrival_gen, query_funcs=None, **kwargs):
        self.provider = provider
        self.arrival_gen = arrival_gen

        if 'stop' in kwargs:
            stops = [kwargs.pop('stop')]
        elif 'stop.id' in kwargs:
            stop = provider.get(busbus.Stop, kwargs.pop('stop.id'), None)
            stops = [] if stop is None else [stop]
        else:
            stops = provider.stops

        if 'route' in kwargs:
            routes = [kwargs.pop('route')]
        elif 'route.id' in kwargs:
            route = provider.get(busbus.Route, kwargs.pop('route.id'), None)
            routes = [] if route is None else [route]
        else:
            routes = provider.routes

        for attr in ('start_time', 'end_time'):
            if attr in kwargs:
                if isinstance(kwargs[attr], datetime.datetime):
                    kwargs[attr] = arrow.Arrow.fromdatetime(kwargs[attr])
                elif isinstance(kwargs[attr], datetime.date):
                    kwargs[attr] = arrow.Arrow.fromdate(kwargs[attr])
        start_time = kwargs.pop('start_time', None)
        end_time = kwargs.pop('end_time', None)

        it = arrival_gen(provider, stops, routes, start_time, end_time)
        super(ArrivalQueryable, self).__init__(it, query_funcs)

    def _new(self, query_funcs, kwargs):
        return ArrivalQueryable(self.provider, self.arrival_gen,
                                query_funcs, **kwargs)
