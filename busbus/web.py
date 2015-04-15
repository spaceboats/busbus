import busbus
from busbus.entity import BaseEntityJSONEncoder
from busbus.provider import ProviderBase

import cherrypy
import collections
import itertools
import math
import types


def json_handler(*args, **kwargs):
    value = cherrypy.serving.request._json_inner_handler(*args, **kwargs)
    return BaseEntityJSONEncoder().encode(value).encode('utf-8')
cherrypy.config['tools.json_out.handler'] = json_handler


EXPAND_TYPES = {
    'providers': ProviderBase,
    'agencies': busbus.Agency,
    'stops': busbus.Stop,
    'routes': busbus.Route,
    'arrivals': busbus.Arrival,
}


def unexpand_init(result, to_expand):
    return ({attr: unexpand(value, to_expand)
             for attr, value in dict(obj).items()}
            for obj in result)


def unexpand(obj, to_expand):
    for name, cls in EXPAND_TYPES.items():
        if isinstance(obj, cls):
            if name not in to_expand:
                return {'id': obj.id}
            else:
                return {attr: unexpand(value, to_expand)
                        for attr, value in dict(obj).items()}
    if isinstance(obj, dict):
        return {attr: unexpand(value, to_expand)
                for attr, value in obj.items()}
    if isinstance(obj, (list, tuple, collections.Iterator)):
        return (unexpand(value, to_expand) for value in obj)
    return obj


class APIError(Exception):

    def __init__(self, msg):
        self.msg = msg


class Engine(busbus.Engine):

    def __init__(self, *args, **kwargs):
        # perhaps fix this to use a decorator somehow?
        self._entity_actions = {
            ('stops', 'find'): (self.stops_find, 'stops'),
            ('routes', 'directions'): (self.routes_directions, 'directions'),
        }
        super(Engine, self).__init__(*args, **kwargs)

    @cherrypy.popargs('entity', 'action')
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def default(self, entity=None, action=None, **kwargs):
        if entity is None:
            return self.help()

        response = {
            'request': {
                'status': 'ok',
                'entity': entity,
                'params': kwargs,
            }
        }
        to_expand = (kwargs.pop('_expand').split(',')
                     if '_expand' in kwargs else [])
        if to_expand:
            response['request']['expand'] = to_expand
        if action:
            response['request']['action'] = action
            if (entity, action) in self._entity_actions:
                func, entity = self._entity_actions[(entity, action)]
                try:
                    response[entity] = unexpand_init(func(**kwargs), to_expand)
                except APIError as exc:
                    response['request']['status'] = 'error'
                    response['error'] = exc.msg
                    cherrypy.response.status = 500
                return response
        else:
            entity_func = getattr(super(Engine, self), entity, None)
            if entity_func is not None:
                result = getattr(super(Engine, self), entity).where(**kwargs)
                if '_limit' in kwargs:
                    limit = int(kwargs['_limit'])
                    result = itertools.islice(result, limit)
                response[entity] = unexpand_init(result, to_expand)
                return response

        # if we get here, endpoint was not found
        response['request']['status'] = 'error'
        response['error'] = 'Endpoint /{0} not found'.format(
            entity + '/' + action if action else entity)
        cherrypy.response.status = 404
        return response

    def help(self):
        return {
            'request': {
                'status': 'help',
            },
            '_entities': EXPAND_TYPES.keys(),
            '_actions': self._entity_actions.keys(),
        }

    def stops_find(self, **kwargs):
        def dist(lat1, lon1, lat2, lon2):
            lat1, lon1, lat2, lon2 = map(math.radians,
                                         (lat1, lon1, lat2, lon2))
            return math.acos(math.sin(lat1) * math.sin(lat2) +
                             math.cos(lat1) * math.cos(lat2) *
                             math.cos(abs(lon2 - lon1))) * 6371000

        expected = ('latitude', 'longitude', 'distance')
        if all(x in kwargs for x in expected):
            for x in expected:
                kwargs[x] = float(kwargs[x])
            return super(Engine, self).stops.where(
                lambda s: (dist(kwargs['latitude'], kwargs['longitude'],
                                s.latitude, s.longitude) <=
                           kwargs['distance']))
        else:
            raise APIError('missing attributes: ' + ','.join(
                x for x in expected if x not in kwargs))

    def routes_directions(self, **kwargs):
        expected = ('route.id', 'provider.id')
        missing = [x for x in expected if x not in kwargs]
        if missing:
            raise APIError('missing attributes: ' + ','.join(missing))
        provider = self._providers[kwargs['provider.id']]
        route = provider.get(busbus.Route, kwargs['route.id'])
        return route.directions
