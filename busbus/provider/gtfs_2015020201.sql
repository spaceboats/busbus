-- this must be the same as SCHEMA_USER_VERSION in gtfs.py
pragma user_version = 2015020201;

-- TABLES ---------------------------------------------------------------------

create table _feeds (
    id integer not null,
    url text not null,
    sha256sum text not null,
    primary key (id)
);

create table agency (
    _feed integer not null,
    agency_id text,
    agency_name text not null,
    agency_url text not null,
    agency_timezone text not null,
    agency_lang text,
    agency_phone text,
    agency_fare_url text,
    primary key (_feed, agency_id),
    foreign key (_feed) references _feeds (url)
);

create table stops (
    _feed integer not null,
    stop_id text not null,
    stop_code text,
    stop_name text not null,
    stop_desc text,
    stop_lat real not null,
    stop_lon real not null,
    zone_id text,
    stop_url text,
    location_type integer,
    parent_station text,
    stop_timezone text,
    wheelchair_boarding text,
    primary key (_feed, stop_id),
    foreign key (_feed) references _feeds (url),
    foreign key (_feed, parent_station) references stops (_feed, stop_id)
);

create table routes (
    _feed integer not null,
    route_id text not null,
    agency_id text,
    -- "At least one of route_short_name or route_long_name must be specified"
    route_short_name text,
    route_long_name text,
    route_desc text,
    route_type integer not null,
    route_url text,
    route_color text,
    route_text_color text,
    primary key (_feed, route_id),
    foreign key (_feed, agency_id) references agencies (_feed, agency_id)
);

create table trips (
    _feed integer not null,
    route_id text not null,
    service_id text not null,
    trip_id text not null,
    trip_headsign text,
    trip_short_name text,
    direction_id integer,
    block_id text,
    shape_id text,
    wheelchair_accessible integer,
    bikes_allowed integer,
    primary key (_feed, trip_id),
    foreign key (_feed, route_id) references routes (_feed, route_id),
    foreign key (_feed, service_id) references calendar (_feed, service_id)
);

create table stop_times (
    _feed integer not null,
    trip_id text not null,
    -- GTFS says arrival_time/departure_time are required but they're actually
    -- not; if missing they are to be interpolated
    arrival_time gtfstime,
    _arrival_interpolate gtfstime,
    departure_time gtfstime,
    stop_id text not null,
    stop_sequence integer not null,
    stop_headsign text,
    pickup_type integer,
    drop_off_type integer,
    shape_dist_traveled real,
    timepoint integer,
    primary key (_feed, trip_id, stop_sequence),
    foreign key (_feed, trip_id) references trips (_feed, trip_id),
    foreign key (_feed, stop_id) references stops (_feed, stop_id)
);

create table calendar (
    _feed integer not null,
    service_id text not null,
    monday integer not null,
    tuesday integer not null,
    wednesday integer not null,
    thursday integer not null,
    friday integer not null,
    saturday integer not null,
    sunday integer not null,
    start_date date not null,
    end_date date not null,
    primary key (_feed, service_id)
);

create table calendar_dates (
    _feed integer not null,
    service_id text not null,
    date date not null,
    exception_type integer not null,
    foreign key (_feed, service_id) references calendar (_feed, service_id)
);

/*
create table fare_attributes (
    _feed integer not null,
    fare_id text not null,
    price text not null, -- text is deliberate; floating point currency is a nightmare
    currency_type text not null,
    payment_method integer not null,
    transfers integer not null,
    transfer_duration timedelta,
    primary key (_feed, fare_id)
);

create table fare_rules (
    _feed integer not null,
    fare_id text not null,
    route_id text,
    origin_id text,
    destination_id text,
    contains_id text,
    foreign key (_feed, fare_id) references fare_attributes (_feed, fare_id)
);

create table shapes (
    _feed integer not null,
    shape_id text not null,
    shape_pt_lat real not null,
    shape_pt_lon real not null,
    shape_pt_sequence integer not null,
    shape_dist_traveled real,
    primary key (_feed, shape_id, shape_pt_sequence)
);
*/

create table frequencies (
    _feed integer not null,
    trip_id text not null,
    start_time gtfstime not null,
    end_time gtfstime not null,
    headway_secs timedelta not null,
    exact_times integer
);

/*
create table transfers (
    _feed integer not null,
    from_stop_id text not null,
    to_stop_id text not null,
    transfer_type integer not null,
    min_transfer_time timedelta,
    foreign key (_feed, from_stop_id) references stops (_feed, stop_id),
    foreign key (_feed, to_stop_id) references stops (_feed, stop_id)
);

create table feed_info (
    _feed integer not null,
    feed_publisher_name text not null,
    feed_publisher_url text not null,
    feed_lang text not null,
    feed_start_date date,
    feed_end_date date,
    feed_version text
);
*/

-- VIEWS ----------------------------------------------------------------------

create view trips_v as
    select t.*, st.min_arrival_time from trips as t join
        (select _feed, trip_id, min(coalesce(arrival_time, _arrival_interpolate)) as min_arrival_time
            from stop_times group by trip_id) as st
        on t.trip_id=st.trip_id and t._feed=st._feed;