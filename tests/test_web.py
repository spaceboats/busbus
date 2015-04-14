# coding=utf-8

import busbus.web
from .conftest import SampleGTFSProvider

import cherrypy
import pytest
import requests
from wsgi_intercept import requests_intercept, add_wsgi_intercept


@pytest.fixture(scope='module')
def url_prefix(request):
    engine = busbus.web.Engine()
    SampleGTFSProvider(engine)

    # https://cherrypy.readthedocs.org/en/latest/deploy.html
    # § Embedding into another WSGI framework
    cherrypy.config.update({'environment': 'embedded'})
    cherrypy.server.unsubscribe()  # disables built-in HTTP server
    cherrypy.engine.start()

    # intercept requests
    host = 'busbus.invalid'
    port = 8080
    requests_intercept.install()
    add_wsgi_intercept(host, port, lambda: cherrypy.tree.mount(engine))

    @request.addfinalizer
    def fin():
        requests_intercept.uninstall()
        cherrypy.engine.exit()

    return 'http://{0}:{1}/'.format(host, port)
