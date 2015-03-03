import busbus
import busbus.entity
from busbus.queryable import Queryable
from busbus import util
import busbus.util.csv as utilcsv

from collections import OrderedDict
import itertools
import phonenumbers
import six
import zipfile


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
            if data['_parent_id'] not in provider._gtfs_stop_child_index:
                provider._gtfs_stop_child_index[data['_parent_id']] = []
            provider._gtfs_stop_child_index[data['_parent_id']].append(self)
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
        return iter(self._provider._gtfs_stop_child_index.get(self.id, []))


class GTFSRoute(busbus.Route):

    def __init__(self, provider, **data):
        if '_agency_id' in data:
            data['agency'] = busbus.entity.LazyEntityProperty(
                provider.get, busbus.Agency, data['_agency_id'])
        if '_type' in data:
            pass  # FIXME

        super(GTFSRoute, self).__init__(provider, **data)


class GTFSArrival(busbus.Arrival):

    def __init__(self, provider, **data):
        super(GTFSArrival, self).__init__(provider, **data)


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
        return GTFSArrivalQueryable(self.provider, new_funcs, self.kwargs)


class GTFSMixin(object):
    """
    Mixin to parse transit data from a General Transit Feed Specification feed.

    GTFS is defined at https://developers.google.com/transit/gtfs/
    """

    def __init__(self, engine, gtfs_url):
        super(GTFSMixin, self).__init__(engine)
        self._gtfs_entities = {e: list() for e in busbus.ENTITIES}
        self._gtfs_id_index = {}
        self._gtfs_stop_child_index = {}

        resp = self._cached_requests.get(gtfs_url)

        with zipfile.ZipFile(six.BytesIO(resp.content)) as z:
            for filename, mapping in GTFS_FILENAME_MAP.items():
                with z.open(filename) as f:
                    dataset = (self._rewrite(data, mapping['rewriter'])
                               for data in utilcsv.CSVReader(f))
                    cls = mapping['class']
                    basecls = util.entity_type(cls)
                    self._gtfs_entities[basecls] = [cls(self, **data)
                                                    for data in dataset]

    @staticmethod
    def _rewrite(data, rewriter):
        return {rewriter[col]: datum for col, datum in data
                if datum and col in rewriter}

    def _new_entity(self, entity):
        cls = util.entity_type(entity)
        if 'id' in cls.__attrs__:
            self._gtfs_id_index[(cls, entity.id)] = entity

    def _build_arrivals(self, stop, route):
        yield GTFSArrival(self, stop=stop, route=route)

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
