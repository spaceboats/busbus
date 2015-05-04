import busbus
from busbus.provider import ProviderBase
from busbus.provider.gtfs import GTFSMixin, GTFSArrivalGenerator
from busbus.util import RateLimitRequests
from busbus.util.arrivals import ArrivalQueryable, ArrivalGeneratorBase

import arrow
import heapq
import itertools
import six


class MBTAArrivalGenerator(ArrivalGeneratorBase):
    realtime = True

    def _build_iterable(self):
        self.gtfs_gen = GTFSArrivalGenerator(self.provider, self.stops,
                                             self.routes, self.start, self.end)

        if self.stops is None and self.routes is None:
            raise ValueError('Provide at least one stop or route for realtime '
                             'data, or set realtime=False')
        elif self.routes is None:
            def yield_predictions_by_stop(stop):
                cur = self.provider.conn.cursor()
                resp = self.provider._mbta_realtime_call('predictionsbystop',
                                                         {'stop': stop.id})
                if resp.status_code == 404:
                    return ()

                trips = {}
                for mode in resp.json()['mode']:
                    for route in mode['route']:
                        for direction in route['direction']:
                            for trip in direction['trip']:
                                query = cur.execute(
                                    '''select null from stop_times where
                                    stop_id=? and trip_id=? and _feed=?''',
                                    (stop.id, trip['trip_id'],
                                     self.provider.feed_id))
                                # if the query returns anything it's guaranteed
                                # to be 1 row
                                for row in query:
                                    trips[trip['trip_id']] = {
                                        'pre_dt': trip['pre_dt'],
                                        'trip_headsign': trip['trip_headsign'],
                                        'route_id': route['route_id'],
                                        'stop_id': stop.id,
                                    }

                routes = stop.routes

                return heapq.merge(*[self._merge_arrivals(stop, route, trips)
                                     for route in routes])

            its = list(six.moves.map(yield_predictions_by_stop,
                                     busbus.Stop.add_children(self.stops)))
        else:
            def yield_predictions_by_route(route):
                resp = self.provider._mbta_realtime_call('predictionsbyroute',
                                                         {'route': route.id})
                if resp.status_code == 404:
                    return ()

                if self.stops is None:
                    stops = route.stops
                else:
                    stops = self.stops
                stops = list(stops)

                trips = {stop.id: dict() for stop in stops}
                for dir in resp.json()['direction']:
                    for trip in dir['trip']:
                        for stop in trip['stop']:
                            if (stop['stop_sequence'] != '0' and
                                    stop['stop_id'] in trips):
                                trips[stop['stop_id']][trip['trip_id']] = {
                                    'pre_dt': stop['pre_dt'],
                                    'trip_headsign': trip['trip_headsign'],
                                    'route_id': route.id,
                                    'stop_id': stop['stop_id'],
                                }

                its = [self._merge_arrivals(stop, route, trips[stop.id])
                       for stop in stops if trips[stop.id]]
                return heapq.merge(*its)

            its = list(six.moves.map(yield_predictions_by_route, self.routes))
        return heapq.merge(*its)

    def _merge_arrivals(self, stop, route, trips):
        arrs = dict(self._build_scheduled_arrivals(stop, route))
        arrs.update(self._build_realtime_arrivals(stop, route, trips))
        arrs = arrs.values()
        return sorted(arrs)

    def _build_realtime_arrivals(self, stop, route, trips):
        for trip_id, trip in trips.items():
            if stop.id == trip['stop_id'] and route.id == trip['route_id']:
                time = arrow.get(trip['pre_dt']).to(self.provider._timezone)
                if self.start <= time <= self.end:
                    arr = busbus.Arrival(self.provider, realtime=True,
                                         stop=stop, route=route,
                                         time=time, departure_time=time,
                                         headsign=trip['trip_headsign'])
                    yield (trip_id, arr)

    def _build_scheduled_arrivals(self, stop, route):
        for stop_time in self.gtfs_gen._stop_times(stop, route):
            for arr in self.gtfs_gen._build_arrivals(stop, route, stop_time):
                yield (stop_time['trip_id'], arr)


class MBTAProvider(GTFSMixin, ProviderBase):
    """
    Provides data from the MBTA-realtime API v2 and the MBTA GTFS feed.

    http://realtime.mbta.com/

    An API key is required to access the MBTA-realtime API. MBTA provides a key
    you can use for development at:
        http://realtime.mbta.com/Portal/Content/Download/APIKey.txt
    This key is for development only -- MBTA requests you do not use this key
    in production; request a key instead.
    """

    legal = [
        ('http://www.massdot.state.ma.us/Portals/0/docs/developers/'
         'RelationshipPrinciples.pdf'),
        ('http://www.massdot.state.ma.us/Portals/0/docs/developers/'
         'develop_license_agree.pdf'),
    ]
    credit = 'MassDOT'
    credit_url = 'http://www.massdot.state.ma.us'
    country = 'US'

    gtfs_url = "http://www.mbta.com/uploadedfiles/MBTA_GTFS.zip"
    mbta_realtime_url = "http://realtime.mbta.com/developer/api/v2/"

    def __init__(self, mbta_api_key, engine=None):
        super(MBTAProvider, self).__init__(engine, self.gtfs_url)
        self.mbta_api_key = mbta_api_key

        # MBTA requires that "the same polling command" is not to be called
        # more often than every 10 seconds (API docs, "Use of MBTA data").
        self._requests = RateLimitRequests(url_interval=10)

    def _mbta_realtime_call(self, query, params):
        url = self.mbta_realtime_url + query
        params.update({'api_key': self.mbta_api_key, 'format': 'json'})
        return self._requests.get(url, params=params)

    @property
    def arrivals(self):
        return ArrivalQueryable(self, (MBTAArrivalGenerator,
                                       GTFSArrivalGenerator))
