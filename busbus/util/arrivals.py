import busbus
from busbus.queryable import Queryable
from busbus import util

from abc import ABCMeta, abstractmethod, abstractproperty
import arrow
import collections
import datetime
import heapq
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
        self.it = None

    @abstractproperty
    def realtime(self):
        """
        True if this generator's Arrival objects can represent realtime data,
        otherwise False.

        Setting this to True doesn't necessarily mean that all the generated
        arrivals will be realtime.

        You don't have to define a property function -- just set the class
        property during the definition, like this:

        class MyArrivalGenerator(ArrivalGeneratorBase):
            realtime = False
        """

    @abstractmethod
    def _build_iterable(self):
        """
        Build an iterator that provides arrivals.

        This is done in a separate function rather than in __init__ so that
        this generator can be lazily evaluated.
        """

    def __next__(self):
        if self.it is None:
            self.it = self._build_iterable()
        return next(self.it)


class ArrivalQueryable(Queryable):

    def __init__(self, provider, arrival_gens, query_funcs=None, **kwargs):
        self.provider = provider

        if isinstance(arrival_gens, collections.Iterable):
            self.arrival_gens = tuple(arrival_gens)
        else:
            self.arrival_gens = (arrival_gens,)

        if 'realtime' in kwargs:
            realtime = bool(kwargs['realtime'])
        else:
            realtime = any(gen.realtime for gen in self.arrival_gens)

        if 'stop' in kwargs:
            stops = [kwargs.pop('stop')]
        elif 'stop.id' in kwargs:
            stop = provider.get(busbus.Stop, kwargs.pop('stop.id'), None)
            stops = [] if stop is None else [stop]
        else:
            stops = None

        if 'route' in kwargs:
            routes = [kwargs.pop('route')]
        elif 'route.id' in kwargs:
            route = provider.get(busbus.Route, kwargs.pop('route.id'), None)
            routes = [] if route is None else [route]
        else:
            routes = None

        for attr in ('start_time', 'end_time'):
            if attr in kwargs:
                if isinstance(kwargs[attr], datetime.datetime):
                    kwargs[attr] = arrow.Arrow.fromdatetime(kwargs[attr])
                elif isinstance(kwargs[attr], datetime.date):
                    kwargs[attr] = arrow.Arrow.fromdate(kwargs[attr])
        start = kwargs.pop('start_time', None)
        end = kwargs.pop('end_time', None)

        it = heapq.merge(*[gen(provider, stops, routes, start, end)
                           for gen in self.arrival_gens
                           if gen.realtime == realtime])
        super(ArrivalQueryable, self).__init__(it, query_funcs, **kwargs)

    def _new(self, query_funcs, kwargs):
        return ArrivalQueryable(self.provider, self.arrival_gens,
                                query_funcs, **kwargs)
