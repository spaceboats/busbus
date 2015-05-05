import busbus
from busbus.entity import BaseEntityJSONEncoder
from busbus.provider import ProviderBase
from busbus.queryable import Queryable

import cherrypy
import collections
import itertools
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

    def __init__(self, msg, error_code=500):
        self.msg = msg
        self.error_code = error_code


class EndpointNotFoundError(APIError):

    def __init__(self, entity, action=None):
        super(EndpointNotFoundError, self).__init__(
            'Endpoint /{0} not found'.format(
                entity + '/' + action if action else entity), 404)


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

        try:
            to_expand = (kwargs.pop('_expand').split(',')
                         if '_expand' in kwargs else [])
            if to_expand:
                response['request']['expand'] = to_expand

            limit = kwargs.pop('_limit', None)
            if limit:
                try:
                    limit = int(limit)
                    if limit <= 0:
                        raise ValueError()
                except ValueError:
                    raise APIError('_limit must be a positive integer', 422)
                response['request']['limit'] = limit

            if 'realtime' in kwargs:
                if kwargs['realtime'] in ('y', 'Y', 'yes', 'Yes', 'YES',
                                          'true', 'True', 'TRUE',
                                          'on', 'On', 'ON'):
                    kwargs['realtime'] = True
                elif kwargs['realtime'] in ('n', 'N', 'no', 'No', 'NO',
                                            'false', 'False', 'FALSE',
                                            'off', 'Off', 'OFF'):
                    kwargs['realtime'] = False
                else:
                    raise APIError('realtime is not a boolean', 422)

            if action:
                response['request']['action'] = action
                if (entity, action) in self._entity_actions:
                    func, entity = self._entity_actions[(entity, action)]
                    result = func(**kwargs)
                else:
                    raise EndpointNotFoundError(entity, action)
            else:
                if 'provider.id' in kwargs:
                    provider_id = kwargs.pop('provider.id')
                    if provider_id in self._providers:
                        provider = self._providers[provider_id]
                        entity_func = getattr(provider, entity, None)
                    else:
                        entity_func = Queryable(())
                else:
                    entity_func = getattr(self, entity, None)
                if entity_func is not None:
                    result = entity_func.where(**kwargs)
                else:
                    raise EndpointNotFoundError(entity)

            if limit:
                result = itertools.islice(result, limit)

            response[entity] = unexpand_init(result, to_expand)
        except APIError as exc:
            response['request']['status'] = 'error'
            response['error'] = exc.msg
            cherrypy.response.status = exc.error_code

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
        expected = ('latitude', 'longitude', 'distance')
        if all(x in kwargs for x in expected):
            for x in expected:
                kwargs[x] = float(kwargs[x])
            latlon = (kwargs['latitude'], kwargs['longitude'])
            return super(Engine, self).stops.where(
                lambda s: s.distance_to(latlon) <= kwargs['distance'])
        else:
            raise APIError('missing attributes: ' + ','.join(
                x for x in expected if x not in kwargs), 422)

    def routes_directions(self, **kwargs):
        expected = ('route.id', 'provider.id')
        missing = [x for x in expected if x not in kwargs]
        if missing:
            raise APIError('missing attributes: ' + ','.join(missing), 422)
        provider = self._providers[kwargs['provider.id']]
        route = provider.get(busbus.Route, kwargs['route.id'])
        return route.directions
