import busbus
import busbus.entity
from busbus.queryable import Queryable
from busbus import util
import busbus.util.csv as utilcsv

import arrow
from collections import OrderedDict
import itertools
import operator
import phonenumbers
import six
import zipfile


def parse_gtfs_time(timestr):
    """
    GTFS time strings are HH:MM:SS (or H:MM:SS if the hours field is less than
    10). The hours field can go over 23 to represent a time on the following
    day (GTFS time never decreases in a given trip).

    This function is not quite that picky, but its behavior is undefined if
    it's given a string not following the specification.

    This function returns a tuple: (hours, minutes, seconds).
    """
    split = [int(x) for x in timestr.split(':')[-3:]]
    split = [0] * (3 - len(split)) + split
    for i in (2, 1):
        if split[i] >= 60:
            split[i-1] += split[i] // 60
            split[i] %= 60
    return tuple(split)


class GTFSAgency(busbus.Agency):

    def __init__(self, provider, **data):
        if 'lang' in data:
            data['lang'] = data['lang'].lower()
        if 'phone_human' in data and 'country' in data:
            phone = phonenumbers.parse(data['phone_human'],
                                       data['country'])
            data['phone_e164'] = phonenumbers.format_number(
                phone, phonenumbers.PhoneNumberFormat.E164)

        super(GTFSAgency, self).__init__(provider, **data)


class GTFSStop(busbus.Stop):

    def __init__(self, provider, **data):
        if '_lat' in data and '_lon' in data:
            try:
                data['location'] = (float(data['_lat']),
                                    float(data['_lon']))
            except ValueError:
                data['location'] = None
        if '_zone_id' in data:
            pass  # FIXME
        if '_parent_id' in data:
            data['parent'] = busbus.entity.LazyEntityProperty(
                provider.get, busbus.Stop, data['_parent_id'])
            provider._add_relation(busbus.Stop, data['_parent_id'],
                                   'children', self)
        if not data.get('timezone', None):
            for agency in provider.agencies:
                if agency.timezone:
                    data['timezone'] = agency.timezone
                    break
        if '_accessible' in data:
            pass  # FIXME

        super(GTFSStop, self).__init__(provider, **data)

    @property
    def children(self):
        return iter(self._provider._get_relation(self, 'children'))


class GTFSRoute(busbus.Route):

    def __init__(self, provider, **data):
        if '_agency_id' in data:
            data['agency'] = provider.get(busbus.Agency, data['_agency_id'])
        if '_type' in data:
            pass  # FIXME

        super(GTFSRoute, self).__init__(provider, **data)


class GTFSArrival(busbus.Arrival):

    def __init__(self, provider, **data):
        super(GTFSArrival, self).__init__(provider, **data)


class GTFSService(busbus.entity.BaseEntity):
    __attrs__ = ('id', 'days', 'start_date', 'end_date', 'added_dates',
                 'removed_dates')

    def __init__(self, provider, **data):
        # Days of the week: 1 = Monday, 7 = Sunday (ISO 8601)
        days = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday',
                'saturday', 'sunday')
        data['days'] = list(i + 1 for i, day in enumerate(days)
                            if data.get(day) == u'1')
        for attr in ('start_date', 'end_date'):
            if attr in data:
                data[attr] = arrow.get(data[attr], 'YYYYMMDD').date()

        super(GTFSService, self).__init__(provider, **data)

    @classmethod
    def handle_calendar_dates(cls, provider, **data):
        if not all(x in data for x in ('id', 'date', 'type')):
            return
        service = provider.get(cls, data['id'])
        attr = {u'1': 'added_dates', u'2': 'removed_dates'}[data['type']]
        if getattr(service, attr) is None:
            setattr(service, attr, set())
        getattr(service, attr).add(arrow.get(data['date'], 'YYYYMMDD').date())


class GTFSTrip(busbus.entity.BaseEntity):
    __attrs__ = ('id', 'route', 'direction', 'service', 'headsign',
                 'short_name', 'block', 'shape', 'accessible', 'bikes_ok')

    def __init__(self, provider, **data):
        data['route'] = provider.get(busbus.Route, data['_route_id'])
        data['service'] = provider.get(GTFSService, data['_service_id'])
        if 'direction' in data:
            try:
                data['direction'] = int(data['direction'])
            except ValueError:
                pass
        if '_block_id' in data:
            pass  # FIXME
        if '_shape_id' in data:
            pass  # FIXME
        if '_accessible' in data:
            pass  # FIXME
        if '_bikes' in data:
            data['bikes_ok'] = {u'0': None, u'1': True,
                                u'2': False}[data['_bikes']]
        super(GTFSTrip, self).__init__(provider, **data)

    @property
    def frequencies(self):
        return iter(self._provider._get_relation(self, 'frequencies'))

    @property
    def stop_times(self):
        return sorted(self._provider._get_relation(self, 'stop_times'),
                      key=operator.attrgetter('sequence'))


class GTFSTripFrequency(busbus.entity.BaseEntity):
    __attrs__ = ('trip', 'start_time', 'end_time', 'headway', 'exact_times')
    __repr_attrs__ = ('trip', 'start_time', 'end_time')

    def __init__(self, provider, **data):
        data['trip'] = provider.get(GTFSTrip, data['_trip_id'])
        for attr in ('start_time', 'end_time'):
            data[attr] = parse_gtfs_time(data[attr])
        data['headway'] = int(data['headway'])
        if 'exact_times' in data:
            data['exact_times'] = bool(int(data['exact_times']))
        provider._add_relation(GTFSTrip, data['_trip_id'], 'frequencies', self)
        super(GTFSTripFrequency, self).__init__(provider, **data)


class GTFSStopTime(busbus.entity.BaseEntity):
    __attrs__ = ('trip', 'stop', 'arrival_time', 'departure_time', 'sequence',
                 'headsign', 'pickup', 'dropoff', 'shape_dist_traveled',
                 'exact_times')

    def __init__(self, provider, **data):
        data['trip'] = provider.get(GTFSTrip, data['_trip_id'])
        data['stop'] = provider.get(GTFSTrip, data['_stop_id'])
        for attr in ('arrival_time', 'departure_time'):
            if attr in data:
                data[attr] = parse_gtfs_time(data[attr])
        data['sequence'] = int(data['sequence'])
        if 'pickup' in data:
            pass  # FIXME
        if 'dropoff' in data:
            pass  # FIXME
        if 'shape_dist_traveled' in data:
            data['shape_dist_traveled'] = float(data['shape_dist_traveled'])
        if 'exact_times' in data:
            data['exact_times'] = {u'0': False, u'1': True}.get(
                data['exact_times'], True)
        provider._add_relation(GTFSTrip, data['_trip_id'], 'stop_times', self)
        provider._add_relation(busbus.Stop, data['_stop_id'], 'trips',
                               data['trip'])
        super(GTFSStopTime, self).__init__(provider, **data)


GTFS_FILENAME_MAP = OrderedDict([
    ('agency.txt', {
        'rewriter': {
            'agency_id': 'id',
            'agency_name': 'name',
            'agency_url': 'url',
            'agency_timezone': 'timezone',
            'agency_lang': 'lang',
            'agency_phone': 'phone_human',
            'agency_fare_url': 'fare_url',
        },
        'class': GTFSAgency,
    }),
    ('stops.txt', {
        'rewriter': {
            'stop_id': 'id',
            'stop_code': 'code',
            'stop_name': 'name',
            'stop_desc': 'description',
            'stop_lat': '_lat',
            'stop_lon': '_lon',
            'zone_id': '_zone_id',
            'stop_url': 'url',
            'parent_station': '_parent_id',
            'stop_timezone': 'timezone',
            'accessible': '_accessible',
        },
        'class': GTFSStop,
    }),
    ('routes.txt', {
        'rewriter': {
            'route_id': 'id',
            'agency_id': '_agency_id',
            'route_short_name': 'short_name',
            'route_long_name': 'name',
            'route_desc': 'description',
            'route_type': '_type',
            'route_url': 'url',
            'route_color': 'color',
            'route_text_color': 'text_color',
        },
        'class': GTFSRoute,
    }),
    ('calendar.txt', {
        'rewriter': {
            'service_id': 'id',
            'monday': 'monday',
            'tuesday': 'tuesday',
            'wednesday': 'wednesday',
            'thursday': 'thursday',
            'friday': 'friday',
            'saturday': 'saturday',
            'sunday': 'sunday',
            'start_date': 'start_date',
            'end_date': 'end_date',
        },
        'class': GTFSService,
    }),
    ('calendar_dates.txt', {
        'rewriter': {
            'service_id': 'id',
            'date': 'date',
            'exception_type': 'type',
        },
        'function': GTFSService.handle_calendar_dates,
    }),
    ('trips.txt', {
        'rewriter': {
            'route_id': '_route_id',
            'service_id': '_service_id',
            'trip_id': 'id',
            'trip_headsign': 'headsign',
            'trip_short_name': 'short_name',
            'direction_id': 'direction',
            'block_id': '_block_id',
            'shape_id': '_shape_id',
            'wheelchair_accessible': '_accessible',
            'bikes_allowed': '_bikes',
        },
        'class': GTFSTrip,
    }),
    ('frequencies.txt', {
        'rewriter': {
            'trip_id': '_trip_id',
            'start_time': 'start_time',
            'end_time': 'end_time',
            'headway_secs': 'headway',
            'exact_times': 'exact_times',
        },
        'class': GTFSTripFrequency,
    }),
    ('stop_times.txt', {
        'rewriter': {
            'trip_id': '_trip_id',
            'stop_id': '_stop_id',
            'arrival_time': 'arrival_time',
            'departure_time': 'departure_time',
            'stop_sequence': 'sequence',
            'stop_headsign': 'headsign',
            'pickup_type': 'pickup',
            'drop_off_type': 'dropoff',
            'shape_dist_traveled': 'shape_dist_traveled',
            'timepoint': 'exact_times',
        },
        'class': GTFSStopTime,
    }),
])


class GTFSArrivalQueryable(Queryable):
    """
    Private class to build the GTFSMixin.arrivals Queryable.
    """

    def __init__(self, provider, query_funcs=None, **kwargs):
        self.provider = provider
        if 'stop_id' in kwargs:
            stop_id = kwargs.pop('stop_id')
            kwargs['stop'] = provider.get(busbus.Stop, stop_id)
        if 'route_id' in kwargs:
            route_id = kwargs.pop('route_id')
            kwargs['route'] = provider.get(busbus.Route, route_id)
        it = itertools.chain.from_iterable(
            provider._build_arrivals(stop, route)
            for stop in ((kwargs['stop'],) if 'stop' in kwargs
                         else provider.stops)
            for route in ((kwargs['route'],) if 'route' in kwargs
                          else provider.routes))
        self.kwargs = kwargs
        super(GTFSArrivalQueryable, self).__init__(it, query_funcs)

    def where(self, query_func=None, **kwargs):
        new_funcs = (self.query_funcs + (query_func,) if query_func else
                     self.query_funcs)
        new_kwargs = copy(self.kwargs)
        new_kwargs.update(kwargs)
        return GTFSArrivalQueryable(self.provider, new_funcs, new_kwargs)


class GTFSMixin(object):
    """
    Mixin to parse transit data from a General Transit Feed Specification feed.

    GTFS is defined at https://developers.google.com/transit/gtfs/
    """

    def __init__(self, engine, gtfs_url):
        super(GTFSMixin, self).__init__(engine)
        self._gtfs_entities = {e: list() for e in busbus.ENTITIES}
        self._gtfs_id_index = {}
        self._gtfs_rel_index = {}

        resp = self._cached_requests.get(gtfs_url)

        with zipfile.ZipFile(six.BytesIO(resp.content)) as z:
            for filename, mapping in GTFS_FILENAME_MAP.items():
                with z.open(filename) as f:
                    dataset = (self._rewrite(data, mapping['rewriter'])
                               for data in utilcsv.CSVReader(f))
                    if 'class' in mapping:
                        cls = mapping['class']
                        basecls = util.entity_type(cls)
                        self._gtfs_entities[basecls] = [cls(self, **data)
                                                        for data in dataset]
                    elif 'function' in mapping:
                        for data in dataset:
                            mapping['function'](self, **data)

    @staticmethod
    def _rewrite(data, rewriter):
        return {rewriter[col]: datum for col, datum in data
                if len(datum) > 0 and col in rewriter}

    def _new_entity(self, entity):
        cls = util.entity_type(entity)
        if 'id' in cls.__attrs__:
            self._gtfs_id_index[(cls, entity.id)] = entity

    def _build_arrivals(self, stop, route):
        yield GTFSArrival(self, stop=stop, route=route)

    def _add_relation(self, cls, id, relation, other):
        rel = (util.entity_type(cls), relation)
        if rel not in self._gtfs_rel_index:
            self._gtfs_rel_index[rel] = {}
        if id not in self._gtfs_rel_index[rel]:
            self._gtfs_rel_index[rel][id] = set()
        self._gtfs_rel_index[rel][id].add(other)

    def _get_relation(self, obj, relation):
        rel = (util.entity_type(obj), relation)
        if rel in self._gtfs_rel_index:
            return self._gtfs_rel_index[rel].get(obj.id, [])
        else:
            return []

    def get(self, cls, id, default=None):
        try:
            return self._gtfs_id_index[(cls, id)]
        except KeyError:
            return default

    @property
    def agencies(self):
        return Queryable(self._gtfs_entities[busbus.Agency])

    @property
    def stops(self):
        return Queryable(self._gtfs_entities[busbus.Stop])

    @property
    def routes(self):
        return Queryable(self._gtfs_entities[busbus.Route])

    @property
    def arrivals(self):
        return GTFSArrivalQueryable(self)
