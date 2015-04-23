from __future__ import division

import busbus
import busbus.entity
from busbus.queryable import Queryable
from busbus import util
from busbus.util.csv import CSVReader

import arrow
import datetime
import hashlib
import heapq
import itertools
import operator
import os
import phonenumbers
from pkg_resources import resource_string
import six
import sqlite3
import zipfile


# This must be the same as the user_version pragma in gtfs.sql
SCHEMA_USER_VERSION = 2015020201


def parse_gtfs_time(timestr):
    """
    GTFS time strings are HH:MM:SS (or H:MM:SS if the hours field is less than
    10). The time is relative to noon on a given day, and the hours field can
    go over 23 to represent a time on the following day (GTFS time never
    decreases in a given trip).

    This function is not quite that picky, but its behavior is undefined if
    it's given a string not following the specification.

    This function returns a timedelta, which contains the number of seconds
    since noon represented by a time on a given day.
    """
    split = [int(x) for x in timestr.split(':')[-3:]]
    split = [0] * (3 - len(split)) + split
    return datetime.timedelta(hours=split[0] - 12, minutes=split[1],
                              seconds=split[2])


def fix_type(value, typename):
    return {
        'date': lambda s: arrow.get(s, 'YYYYMMDD').date(),
        'gtfstime': lambda s: parse_gtfs_time(s).total_seconds(),
        'integer': int,
        'real': float,
        'timedelta': int,
    }.get(typename, lambda s: s)(value) if value else None


for typename in ('gtfstime', 'timedelta'):
    sqlite3.register_converter(typename,
                               lambda s: datetime.timedelta(seconds=float(s)))


class SQLEntityMixin(object):

    def __eq__(self, other):
        if not isinstance(other, SQLEntityMixin):
            return False
        return (self.id == getattr(other, 'id', not self.id) and
                self.provider == getattr(other, 'provider', not self.provider))

    @classmethod
    def _build_select(cls, columns, named_params=False):
        query = 'select {0} from {1}'.format(
            ', '.join('{1} as {0}'.format(k, v)
                      for k, v in cls.__field_map__.items()),
            cls.__table__)
        if columns:
            if named_params:
                query += ' where {0}'.format(
                    ' and '.join('{0}=:{0}'.format(c) for c in columns))
            else:
                query += ' where {0}'.format(
                    ' and '.join('{0}=?'.format(c) for c in columns))
        return query

    def _query(self, **kwargs):
        return self.provider._query(self.__class__, **kwargs)

    @classmethod
    def from_id(cls, provider, id, default=None):
        """
        Special case of _query that doesn't require an instantiated object
        and to fetch by a specific column name.
        """
        id_field = cls.__field_map__['id']
        result = provider._query(cls, **{id_field: id}).fetchone()
        if result is None:
            return default
        else:
            return cls(provider, **dict(result))


class GTFSAgency(SQLEntityMixin, busbus.Agency):
    __table__ = 'agency'
    __field_map__ = {
        'id': 'agency_id',
        'name': 'agency_name',
        'url': 'agency_url',
        'timezone': 'agency_timezone',
        'lang': 'agency_lang',
        'phone_human': 'agency_phone',
        'fare_url': 'agency_fare_url',
    }

    def __init__(self, provider, **data):
        if data.get('lang'):
            data['lang'] = data['lang'].lower()
        if data.get('phone_human') and getattr(provider, 'country'):
            phone = phonenumbers.parse(data['phone_human'], provider.country)
            data['phone_e164'] = phonenumbers.format_number(
                phone, phonenumbers.PhoneNumberFormat.E164)

        super(GTFSAgency, self).__init__(provider, **data)


class GTFSStop(SQLEntityMixin, busbus.Stop):
    __table__ = 'stops'
    __field_map__ = {
        'id': 'stop_id',
        'code': 'stop_code',
        'name': 'stop_name',
        'description': 'stop_desc',
        'latitude': 'stop_lat',
        'longitude': 'stop_lon',
        'url': 'stop_url',
        '_parent_id': 'parent_station',
        'timezone': 'stop_timezone',
        '_accessible': 'wheelchair_boarding',
    }

    def __init__(self, provider, **data):
        if data.get('_parent_id'):
            data['parent'] = busbus.entity.LazyEntityProperty(
                provider.get, busbus.Stop, data['_parent_id'])
        if not data.get('timezone'):
            data['timezone'] = provider._timezone
        if '_accessible' in data:
            pass  # FIXME

        super(GTFSStop, self).__init__(provider, **data)

    @property
    def children(self):
        result = self._query(parent_station=self.id)
        return Queryable(GTFSStop(**dict(row)) for row in result)


class GTFSRoute(SQLEntityMixin, busbus.Route):
    __table__ = 'routes'
    __field_map__ = {
        'id': 'route_id',
        '_agency_id': 'agency_id',
        'short_name': 'route_short_name',
        'name': 'route_long_name',
        'description': 'route_desc',
        '_type': 'route_type',
        'url': 'route_url',
        'color': 'route_color',
        'text_color': 'route_text_color',
    }

    def __init__(self, provider, **data):
        if '_agency_id' in data:
            data['agency'] = busbus.entity.LazyEntityProperty(
                provider.get, busbus.Agency, data['_agency_id'])
        if '_type' in data:
            pass  # FIXME

        super(GTFSRoute, self).__init__(provider, **data)

    @property
    def directions(self):
        hashes = []
        t_query = """select trip_headsign, trip_short_name, bikes_allowed,
        trip_id from trips where route_id=:route_id and _feed_url=:_feed_url"""
        t_filter = {'route_id': self.id, '_feed_url': self.provider.gtfs_url}
        for trip in self.provider.conn.execute(t_query, t_filter):
            direction = {}
            result = self.provider.conn.execute(
                """select s.* from stop_times as st join stops as s
                on st.stop_id=s.stop_id and st._feed_url=s._feed_url
                where st.trip_id=:t_id and st._feed_url=:_feed_url""",
                {'t_id': trip['trip_id'], '_feed_url': self.provider.gtfs_url})
            direction['stops'] = [GTFSStop(self.provider, **dict(row))
                                  for row in result]
            if trip['trip_headsign'] is not None:
                direction['headsign'] = trip['trip_headsign']
            if trip['trip_short_name'] is not None:
                direction['short_name'] = trip['trip_short_name']
            if trip['bikes_allowed'] is not None:
                direction['bikes_ok'] = trip['bikes_allowed']
            h = util.freezehash(direction)
            if h not in hashes:
                hashes.append(h)
                yield direction


class ArrivalIterator(util.Iterable):
    """
    Private class to build arrivals, in order of arrival time, given a list of
    stops and routes.
    """

    def __init__(self, provider, stops, routes, start, end):
        self.provider = provider
        self.stops = stops
        self.routes = routes
        self.start = (arrow.now() if start is None
                      else arrow.get(start)).to(provider._timezone)
        self.end = (self.start.replace(hours=3) if end is None
                    else arrow.get(end)).to(provider._timezone)
        self.service_cache = {}
        self.freq_cache = {}
        self.it = None

    def __next__(self):
        if self.it is None:
            st_query = """select distinct min_arrival_time, service_id,
                trip_headsign, trip_short_name, bikes_allowed,
                coalesce(st.arrival_time, st._arrival_interpolate) as arr,
                departure_time, st.trip_id as trip_id
            from trips_v as t join stop_times as st on
                t.trip_id=st.trip_id and t._feed_url=st._feed_url
            where route_id=:route_id and stop_id=:stop_id and
                t._feed_url=:_feed_url order by arrival_time asc"""
            iters = []
            for stop, route in itertools.product(self.stops, self.routes):
                for stop_time in self.provider.conn.execute(st_query, {
                        'route_id': route.id, 'stop_id': stop.id,
                        '_feed_url': self.provider.gtfs_url}):
                    iters.append(self._build_arrivals(stop, route, stop_time))
            self.it = heapq.merge(*iters)
        return next(self.it)

    def _build_arrivals(self, stop, route, stop_time):
        def build_arr(day, offset=None):
            if offset is None:
                offset = datetime.timedelta()
            time = day + datetime.timedelta(seconds=stop_time['arr']) + offset
            if not (self.start <= time <= self.end):
                return
            dep = (day + stop_time['departure_time'] + offset if
                   stop_time['departure_time'] else None)
            bikes_ok = {1: True, 2: False}.get(stop_time['bikes_allowed'])
            return busbus.Arrival(self.provider, stop=stop, route=route,
                                  time=time, departure_time=dep,
                                  headsign=stop_time['trip_headsign'],
                                  short_name=stop_time['trip_short_name'],
                                  bikes_ok=bikes_ok)

        days = filter(self._valid_date_filter(stop_time['service_id']),
                      arrow.Arrow.range('day', self.start.floor('day'),
                                        self.end.ceil('day')))
        freqs = self._frequencies(stop_time['trip_id'])
        trip_start = datetime.timedelta(seconds=stop_time['min_arrival_time'])
        for day in days:
            # GTFS time is relative to noon
            day = day.replace(hours=12)
            for freq in freqs:
                freq_start = day + freq['start_time']
                freq_end = day + freq['end_time']
                rel_time = freq_start - (day + trip_start)
                offset = datetime.timedelta()
                while freq_start + offset <= freq_end:
                    arrival = build_arr(day, offset + rel_time)
                    if arrival:
                        yield arrival
                    offset += freq['headway_secs']
            if not freqs:
                arrival = build_arr(day)
                if arrival:
                    yield arrival

    def _valid_date_filter(self, service_id):
        def valid_date(day):
            serv = self._service(service_id)
            weekday = day.format('dddd').lower()
            day = day.date()  # convert from Arrow to datetime.date
            # schedule exceptions: 1 = added, 2 = removed
            return ((serv['start_date'] <= day <= serv['end_date']) and
                    (serv['exceptions'].get(day, 0) != 2) and
                    (serv[weekday] or serv['exceptions'].get(day, 0) == 1))
        return valid_date

    def _frequencies(self, trip_id):
        if trip_id not in self.freq_cache:
            query = """select start_time, end_time, headway_secs
            from frequencies where trip_id=:trip_id and
            _feed_url=:_feed_url order by start_time asc"""
            filter = {'trip_id': trip_id, '_feed_url': self.provider.gtfs_url}
            self.freq_cache[trip_id] = self.provider.conn.execute(
                query, filter).fetchall()
        return self.freq_cache[trip_id]

    def _service(self, id):
        if id not in self.service_cache:
            c_query = """select start_date, end_date, monday, tuesday,
            wednesday, thursday, friday, saturday, sunday from calendar
            where service_id=:service_id and _feed_url=:_feed_url"""
            c_filter = {'service_id': id,
                        '_feed_url': self.provider.gtfs_url}
            self.service_cache[id] = dict(self.provider.conn.execute(
                c_query, c_filter).fetchone())

            cd_query = """select date, exception_type from calendar_dates
            where service_id=:service_id and _feed_url=:_feed_url"""
            cd_result = self.provider.conn.execute(cd_query, c_filter)
            self.service_cache[id]['exceptions'] = {r[0]: r[1]
                                                    for r in cd_result}
        return self.service_cache[id]


class GTFSArrivalQueryable(Queryable):
    """
    Private class to build the GTFSMixin.arrivals Queryable.
    """

    def __init__(self, provider, query_funcs=None, **kwargs):
        self.provider = provider

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

        it = ArrivalIterator(provider, stops, routes, start_time, end_time)
        super(GTFSArrivalQueryable, self).__init__(it, query_funcs)
        self.kwargs = kwargs

    def where(self, query_func=None, **kwargs):
        new_funcs = (self.query_funcs + (query_func,) if query_func else
                     self.query_funcs)
        new_kwargs = self.kwargs.copy()
        new_kwargs.update(kwargs)
        return GTFSArrivalQueryable(self.provider, new_funcs, **new_kwargs)


class GTFSMixin(object):
    """
    Mixin to parse transit data from a General Transit Feed Specification feed.

    GTFS is defined at https://developers.google.com/transit/gtfs/
    """

    def __init__(self, engine, gtfs_url):
        super(GTFSMixin, self).__init__(engine)

        db_path = self.engine.config.get(
            'gtfs_db_path',
            os.path.join(self.engine.config['busbus_dir'], 'gtfs.sqlite3'))
        self.conn = sqlite3.connect(db_path, isolation_level='DEFERRED',
                                    detect_types=(sqlite3.PARSE_DECLTYPES |
                                                  sqlite3.PARSE_COLNAMES))
        self.conn.row_factory = sqlite3.Row

        version = self.conn.execute('pragma user_version').fetchone()[0]
        if version == 0:
            script = resource_string(
                __name__, 'gtfs_{0}.sql'.format(SCHEMA_USER_VERSION))
            if isinstance(script, six.binary_type):
                script = script.decode('utf-8')
            self.conn.executescript(script)
        elif version < SCHEMA_USER_VERSION:
            raise NotImplementedError()
        elif version > SCHEMA_USER_VERSION:
            raise RuntimeError('Database version is {0}, but only version {1} '
                               'is known'.format(version, SCHEMA_USER_VERSION))

        tables = [r[0] for r in self.conn.execute('SELECT name FROM '
                                                  'sqlite_master WHERE '
                                                  'type="table"')
                  if not r[0].startswith('_')]

        if isinstance(gtfs_url, six.binary_type):
            gtfs_url = gtfs_url.decode('utf-8')
        self.gtfs_url = gtfs_url
        resp = self._cached_requests.get(gtfs_url)
        zip = six.BytesIO(resp.content).getvalue()
        hash = hashlib.sha256(zip).hexdigest()

        count = (self.conn.execute('SELECT count(*) FROM _feeds WHERE '
                                   'url=? AND sha256sum=?', (gtfs_url, hash))
                 .fetchone()[0])
        if count != 1:
            self.conn.execute('DELETE FROM _feeds WHERE url=?', (gtfs_url,))
            for table in tables:
                self.conn.execute(
                    'DELETE FROM {0} WHERE _feed_url=?'.format(table),
                    (gtfs_url,))
            self.conn.execute('INSERT INTO _feeds (url, sha256sum) '
                              'VALUES (?, ?)', (gtfs_url, hash))
            with zipfile.ZipFile(six.BytesIO(zip)) as z:
                for table in tables:
                    filename = table + '.txt'
                    if filename not in z.namelist():
                        continue
                    with z.open(filename) as f:
                        data = six.moves.map(lambda d: dict(itertools.chain(
                            d, [(u'_feed_url', gtfs_url)])), CSVReader(f))
                        columns = {x[1]: x[2] for x in self.conn.execute(
                            'pragma table_info({0})'.format(table))}
                        stmt = ('INSERT INTO {0} ({1}) VALUES ({2})'
                                .format(table, ', '.join(columns),
                                        ', '.join(':' + c for c in columns)))
                        self.conn.executemany(
                            stmt, ({k: fix_type(row.get(k), columns[k])
                                    for k in columns} for row in data))
            self.conn.commit()

            # interpolate missing stop times
            for row in self.conn.execute(
                    '''select distinct trip_id from stop_times where
                    arrival_time is null and _feed_url=?''', (self.gtfs_url,)):
                trip_id = row['trip_id']
                known_times = {r['seq']: dict(r) for r in self.conn.execute(
                    '''select arrival_time as a, departure_time as d,
                    stop_sequence as seq from stop_times where trip_id=:trip_id
                    and _feed_url=:_feed_url and arrival_time is not null
                    order by stop_sequence asc''',
                    {'trip_id': trip_id, '_feed_url': self.gtfs_url})}
                if not known_times:
                    # this trip is headway only
                    continue
                unknown_times = [r['stop_sequence'] for r in self.conn.execute(
                    '''select stop_sequence from stop_times where
                    trip_id=:trip_id and _feed_url=:_feed_url and
                    arrival_time is null order by stop_sequence asc''',
                    {'trip_id': trip_id, '_feed_url': self.gtfs_url})]
                for i, seq in enumerate(unknown_times):
                    left = max(filter(lambda k: k < seq, known_times))
                    right = min(filter(lambda k: k > seq, known_times))
                    start = known_times[left].get('d', known_times[left]['a'])
                    gap = known_times[right]['a'] - start
                    count = len(list(filter(lambda k: left < k < right,
                                            unknown_times))) + 1
                    time = ((gap.total_seconds() * (i + 1) / count) +
                            start.total_seconds())
                    self.conn.execute(
                        '''update stop_times set _arrival_interpolate=:a where
                        trip_id=:trip_id and _feed_url=:_feed_url and
                        stop_sequence=:seq''',
                        {'trip_id': trip_id, '_feed_url': self.gtfs_url,
                         'a': time, 'seq': seq})
            self.conn.commit()

    def __del__(self):
        self.conn.close()

    def _query(self, cls, **kwargs):
        if '_feed_url' not in kwargs:
            kwargs['_feed_url'] = self.gtfs_url
        return self.conn.execute(
            cls._build_select(kwargs.keys(), named_params=True), kwargs)

    def _entity_builder(self, cls, **kwargs):
        return Queryable(cls(self, **dict(row))
                         for row in self._query(cls))

    def get(self, cls, id, default=None):
        typemap = {
            busbus.Agency: GTFSAgency,
            busbus.Stop: GTFSStop,
            busbus.Route: GTFSRoute,
        }
        try:
            cls = util.entity_type(cls)
        except TypeError:
            return default
        if cls in typemap:
            return typemap[cls].from_id(self, id, default)
        else:
            return default

    @property
    def _timezone(self):
        for agency in self.agencies:
            if agency.timezone:
                return agency.timezone
        return None

    @property
    def agencies(self):
        return self._entity_builder(GTFSAgency)

    @property
    def stops(self):
        return self._entity_builder(GTFSStop)

    @property
    def routes(self):
        return self._entity_builder(GTFSRoute)

    @property
    def arrivals(self):
        return GTFSArrivalQueryable(self)
