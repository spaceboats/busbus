from __future__ import division

import busbus
import busbus.entity
from busbus.queryable import Queryable
from busbus import util
from busbus.util.arrivals import ArrivalQueryable, ArrivalGeneratorBase
from busbus.util.csv import CSVReader

import apsw
import arrow
import collections
import datetime
import hashlib
import heapq
import itertools
import operator
import os
import phonenumbers
from pkg_resources import resource_string
import six
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
    split = timestr.split(':')
    seconds = int(split[-1])
    minutes = int(split[-2]) if len(split) > 1 else 0
    hours = int(split[-3]) if len(split) > 2 else 0
    return (hours - 12) * 3600 + minutes * 60 + seconds


def date_to_sql_string(datestr):
    return '-'.join((datestr[:4], datestr[4:6], datestr[6:]))


FIX_TYPE_MAP = {
    'date': date_to_sql_string,
    'gtfstime': parse_gtfs_time,
    'integer': int,
    'real': float,
    'timedelta': int,
    'text': lambda s: s,
}


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
    def routes(self):
        result = self.provider.conn.cursor().execute(
            '''select route_id from _stops_routes where
            stop_id=? and _feed=?''',
            (self.id, self.provider.feed_id))
        return Queryable(self.provider.get(busbus.Route, row['route_id'])
                         for row in result)

    @property
    def children(self):
        result = self._query(parent_station=self.id)
        return Queryable(GTFSStop(self.provider, **dict(row))
                         for row in result)


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
        if data.get('name') is None:
            data['name'] = data.pop('short_name')

        super(GTFSRoute, self).__init__(provider, **data)

    @property
    def stops(self):
        result = self.provider.conn.cursor().execute(
            '''select stop_id from _stops_routes where
            route_id=? and _feed=?''',
            (self.id, self.provider.feed_id))
        return Queryable(self.provider.get(busbus.Stop, row['stop_id'])
                         for row in result)

    @property
    def directions(self):
        hashes = []
        t_query = """select trip_headsign, trip_short_name, bikes_allowed,
        trip_id from trips where route_id=:route_id and _feed=:_feed"""
        t_filter = {'route_id': self.id, '_feed': self.provider.feed_id}
        cur = self.provider.conn.cursor()
        for trip in cur.execute(t_query, t_filter):
            direction = {}
            innercur = self.provider.conn.cursor()
            result = innercur.execute(
                """select s.* from stop_times as st join stops as s
                on st.stop_id=s.stop_id and st._feed=s._feed
                where st.trip_id=:t_id and st._feed=:_feed""",
                {'t_id': trip['trip_id'], '_feed': self.provider.feed_id})
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


class GTFSArrivalGenerator(ArrivalGeneratorBase):
    realtime = False

    def __init__(self, provider, stops, routes, start, end):
        super(GTFSArrivalGenerator, self).__init__(provider, stops, routes,
                                                   start, end)

        if self.stops is None:
            if self.routes is None:
                self.stops = self.provider.stops
                self.routes = self.provider.routes
            else:
                stops_dict = {}
                for route in self.routes:
                    for stop in route.stops:
                        stops_dict[stop.id] = stop
                self.stops = stops_dict.values()
        else:
            if self.routes is None:
                routes_dict = {}
                for stop in self.stops:
                    for route in stop.routes:
                        routes_dict[route.id] = route
                self.routes = routes_dict.values()

        self.service_cache = {}
        self.freq_cache = {}
        self.it = None

    def _stop_times(self, stop, route):
        return self.provider.conn.cursor().execute(
            '''select t.*, arr, departure_time from
                (select trip_id, _min_arrival_time, service_id, trip_headsign,
                trip_short_name, bikes_allowed from trips where
                route_id=:route_id and _feed=:_feed) as t
            join
                (select trip_id, coalesce(arrival_time, _arrival_interpolate)
                as arr, departure_time from stop_times where stop_id=:stop_id
                and _feed=:_feed) as st
            on t.trip_id=st.trip_id order by arr asc''',
            {'stop_id': stop.id, 'route_id': route.id,
             '_feed': self.provider.feed_id})

    def _build_iterable(self):
        iters = []
        stops = busbus.Stop.add_children(self.stops)
        for stop, route in itertools.product(stops, self.routes):
            for stop_time in self._stop_times(stop, route):
                iters.append(self._build_arrivals(stop, route, stop_time))
        return heapq.merge(*iters)

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
                                  bikes_ok=bikes_ok, realtime=False)

        days = filter(self._valid_date_filter(stop_time['service_id']),
                      arrow.Arrow.range('day', self.start.floor('day'),
                                        self.end.ceil('day')))
        freqs = self._frequencies(stop_time['trip_id'])
        trip_start = stop_time['_min_arrival_time']
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
            _feed=:_feed order by start_time asc"""
            filter = {'trip_id': trip_id, '_feed': self.provider.feed_id}
            cur = self.provider.conn.cursor()
            self.freq_cache[trip_id] = cur.execute(query, filter).fetchall()
        return self.freq_cache[trip_id]

    def _service(self, id):
        if id not in self.service_cache:
            c_query = """select start_date, end_date, monday, tuesday,
            wednesday, thursday, friday, saturday, sunday from calendar
            where service_id=:service_id and _feed=:_feed"""
            c_filter = {'service_id': id, '_feed': self.provider.feed_id}
            cur = self.provider.conn.cursor()
            self.service_cache[id] = dict(next(cur.execute(c_query, c_filter)))

            cd_query = """select date, exception_type as e from calendar_dates
            where service_id=:service_id and _feed=:_feed"""
            cd_result = cur.execute(cd_query, c_filter)
            self.service_cache[id]['exceptions'] = {r['date']: r['e']
                                                    for r in cd_result}
        return self.service_cache[id]


def gtfs_row_tracer(cur, row):
    type_map = {
        'date': lambda s: datetime.date(int(s[:4]), int(s[5:7]), int(s[8:])),
        'gtfstime': lambda i: datetime.timedelta(seconds=i),
        'timedelta': lambda i: datetime.timedelta(seconds=i),
    }
    desc = cur.getdescription()
    return {desc[i][0]: (type_map.get(desc[i][1], lambda s: s)(x)
                         if row[i] is not None else None)
            for i, x in enumerate(row)}


class GTFSMixin(object):
    """
    Mixin to parse transit data from a General Transit Feed Specification feed.

    GTFS is defined at https://developers.google.com/transit/gtfs/
    """

    def __init__(self, engine, gtfs_url):
        super(GTFSMixin, self).__init__(engine)

        if isinstance(self.engine.config['gtfs_db_path'], apsw.Connection):
            self.conn = self.engine.config['gtfs_db_path']
        else:
            self.conn = apsw.Connection(self.engine.config['gtfs_db_path'])
        self.conn.setrowtrace(gtfs_row_tracer)
        cur = self.conn.cursor()

        version = next(cur.execute('pragma user_version'))['user_version']
        if version == 0:
            script = resource_string(
                __name__, 'gtfs_{0}.sql'.format(SCHEMA_USER_VERSION))
            if isinstance(script, six.binary_type):
                script = script.decode('utf-8')
            cur.execute(script)
        elif version < SCHEMA_USER_VERSION:
            raise NotImplementedError()
        elif version > SCHEMA_USER_VERSION:
            raise RuntimeError('Database version is {0}, but only version {1} '
                               'is known'.format(version, SCHEMA_USER_VERSION))

        tables = [r['name'] for r in cur.execute('select name from '
                                                 'sqlite_master where '
                                                 'type="table"')
                  if not r['name'].startswith('_')]

        if isinstance(gtfs_url, six.binary_type):
            gtfs_url = gtfs_url.decode('utf-8')
        resp = self._cached_requests.get(gtfs_url)
        zip = six.BytesIO(resp.content).getvalue()
        hash = hashlib.sha256(zip).hexdigest()

        resp = [x['id'] for x in cur.execute(
            'select id from _feeds where url=? AND sha256sum=?',
            (gtfs_url, hash))]
        if len(resp) == 1:
            self.feed_id = resp[0]
        else:
            cur.execute('begin transaction')
            old_ids = [(x['id'],) for x in cur.execute(
                '''select id from _feeds where url=?''', (gtfs_url,))]
            cur.executemany('delete from _feeds where id=?', old_ids)
            for table in tables:
                cur.executemany('delete from {0} where _feed=?'.format(table),
                                old_ids)

            cur.execute('insert into _feeds (url, sha256sum) '
                        'values (?, ?)', (gtfs_url, hash))
            self.feed_id = self.conn.last_insert_rowid()
            with zipfile.ZipFile(six.BytesIO(zip)) as z:
                for table in tables:
                    filename = table + '.txt'
                    if filename not in z.namelist():
                        continue
                    with z.open(filename) as f:
                        data = CSVReader(f)
                        columns = []
                        coldata = []
                        for x in cur.execute(
                                'pragma table_info({0})'.format(table)):
                            if x['name'] in data.header:
                                columns.append(x['name'])
                                coldata.append((
                                    x['type'], data.header.index(x['name'])))
                        # _feed must be at end
                        columns.append('_feed')

                        stmt = ('insert into {0} ({1}) values ({2})'
                                .format(table, ', '.join(columns),
                                        ', '.join(('?',) * len(columns))))

                        def row_gen(row):
                            for t, idx in coldata:
                                if idx < len(row) and row[idx] is not None:
                                    yield FIX_TYPE_MAP[t](row[idx])
                                else:
                                    yield None
                            yield self.feed_id
                        cur.executemany(stmt, (row_gen(row) for row in data))
            cur.execute('commit transaction')

            cur.execute('begin transaction')
            for row in cur.execute(
                    '''select trip_id from trips where _feed=?''',
                    (self.feed_id,)):
                innercur = self.conn.cursor()
                trip_id = row['trip_id']

                # interpolate missing stop times
                known_times = {r['seq']: dict(r) for r in innercur.execute(
                    '''select arrival_time as a, departure_time as d,
                    stop_sequence as seq from stop_times where trip_id=:trip_id
                    and _feed=:_feed and arrival_time is not null
                    order by stop_sequence asc''',
                    {'trip_id': trip_id, '_feed': self.feed_id})}
                if not known_times:
                    # this trip is headway only
                    continue
                unknown_times = [r['stop_sequence'] for r in innercur.execute(
                    '''select stop_sequence from stop_times where
                    trip_id=:trip_id and _feed=:_feed and
                    arrival_time is null order by stop_sequence asc''',
                    {'trip_id': trip_id, '_feed': self.feed_id})]
                for i, seq in enumerate(unknown_times):
                    left = max(filter(lambda k: k < seq, known_times))
                    right = min(filter(lambda k: k > seq, known_times))
                    start = known_times[left].get('d', known_times[left]['a'])
                    gap = known_times[right]['a'] - start
                    count = len(list(filter(lambda k: left < k < right,
                                            unknown_times))) + 1
                    time = ((gap.total_seconds() * (i + 1) / count) +
                            start.total_seconds())
                    innercur.execute(
                        '''update stop_times set _arrival_interpolate=:a where
                        trip_id=:trip_id and _feed=:_feed and
                        stop_sequence=:seq''',
                        {'trip_id': trip_id, '_feed': self.feed_id,
                         'a': time, 'seq': seq})

                # fill in _min_arrival_time
                min_time = innercur.execute(
                    '''select min(coalesce(arrival_time, _arrival_interpolate))
                    as min_time from stop_times where trip_id=? and _feed=?''',
                    (trip_id, self.feed_id)).fetchone()['min_time']
                innercur.execute('''update trips set _min_arrival_time=?
                                 where trip_id=? and _feed=?''',
                                 (min_time, trip_id, self.feed_id))

            cur.execute(
                '''insert into _stops_routes (stop_id, route_id, _feed)
                select distinct st.stop_id, t.route_id, t._feed from
                (select trip_id, stop_id from stop_times where _feed=:_feed)
                as st join
                (select trip_id, route_id, _feed from trips where _feed=:_feed)
                as t on st.trip_id=t.trip_id''', {'_feed': self.feed_id})
            cur.execute('commit transaction')

    def _query(self, cls, **kwargs):
        if '_feed' not in kwargs:
            kwargs['_feed'] = self.feed_id
        cur = self.conn.cursor()
        return cur.execute(cls._build_select(
            kwargs.keys(), named_params=True), kwargs)

    def _entity_builder(self, cls, **kwargs):
        query = self._query(cls, **kwargs)
        return Queryable(cls(self, **row) for row in query)

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
        return ArrivalQueryable(self, GTFSArrivalGenerator)
