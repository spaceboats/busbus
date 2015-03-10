import busbus
from busbus.entity import BaseEntityJSONEncoder

import cherrypy


def json_handler(*args, **kwargs):
    value = cherrypy.serving.request._json_inner_handler(*args, **kwargs)
    return BaseEntityJSONEncoder().encode(value).encode('utf-8')
cherrypy.config['tools.json_out.handler'] = json_handler


class Engine(busbus.Engine):

    def _entity_response(self, entity, **kwargs):
        return {
            'request': {
                'entity': entity,
                'params': kwargs,
            },
            entity: getattr(super(Engine, self), entity).where(**kwargs),
        }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def providers(self):
        return self._providers.keys()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def agencies(self, **kwargs):
        return self._entity_response('agencies', **kwargs)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def stops(self, **kwargs):
        return self._entity_response('stops', **kwargs)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def routes(self, **kwargs):
        return self._entity_response('routes', **kwargs)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def arrivals(self, **kwargs):
        return self._entity_response('arrivals', **kwargs)
