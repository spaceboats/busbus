import busbus
import busbus.entity
from busbus.queryable import Queryable
from busbus import util
import busbus.util.csv as utilcsv

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
            data['parent'] = util.Lazy(provider.get, busbus.Stop,
                                       data['_parent_id'])
            if data['_parent_id'] not in provider._gtfs_stop_child_index:
                provider._gtfs_stop_child_index[data['_parent_id']] = []
            provider._gtfs_stop_child_index[data['_parent_id']].append(self)
        if '_accessible' in data:
            pass  # FIXME

        super(GTFSStop, self).__init__(provider, **data)

    @property
    def children(self):
        return iter(self._provider._gtfs_stop_child_index.get(self.id, []))


class GTFSRoute(busbus.Route):

    def __init__(self, provider, **data):
        if '_agency_id' in data:
            data['agency'] = util.Lazy(provider.get, busbus.Agency,
                                       data['_agency_id'])
        if '_type' in data:
            pass  # FIXME

        super(GTFSRoute, self).__init__(provider, **data)


GTFS_FILENAME_MAP = {
    'agency.txt': {
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
    },
    'stops.txt': {
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
    },
    'routes.txt': {
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
    },
}


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
        self._gtfs_id_index[(cls, entity.id)] = entity

    def get(self, cls, id, default=None):
        try:
            return self._gtfs_id_index[cls][id]
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
