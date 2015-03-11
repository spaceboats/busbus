import busbus
from busbus.entity import BaseEntityJSONEncoder

import cherrypy
import math


def json_handler(*args, **kwargs):
    value = cherrypy.serving.request._json_inner_handler(*args, **kwargs)
    return BaseEntityJSONEncoder().encode(value).encode('utf-8')
cherrypy.config['tools.json_out.handler'] = json_handler


class APIError(Exception):

    def __init__(self, msg):
        self.msg = msg


class Engine(busbus.Engine):

    def __init__(self, *args, **kwargs):
        # perhaps fix this to use a decorator somehow?
        self._entity_actions = {
            ('stops', 'find'): self.stops_find
        }
        super(Engine, self).__init__(*args, **kwargs)

    @cherrypy.popargs('entity', 'action')
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def default(self, entity, action=None, **kwargs):
        response = {
            'request': {
                'entity': entity,
                'params': kwargs,
            }
        }
        if action:
            response['request']['action'] = action
            try:
                func = self._entity_actions[(entity, action)]
                response[entity] = func(**kwargs)
            except APIError as exc:
                response['error'] = exc.msg
        else:
            response[entity] = (getattr(super(Engine, self), entity)
                                .where(**kwargs))
        return response

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
