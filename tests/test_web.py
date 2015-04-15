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


def get(url, status_code=200):
    resp = requests.get(url)
    assert resp.status_code == status_code
    assert resp.headers['content-type'] == 'application/json'
    data = resp.json()
    assert 'request' in data
    assert 'status' in data['request']
    assert data['request']['status'] in (('error',) if status_code == 404
                                         else ('ok', 'help'))
    return (data, resp)


def test_index(url_prefix):
    data, resp = get(url_prefix)
    assert data['request']['status'] == 'help'
    for attr in ('_entities', '_actions'):
        assert isinstance(data.get(attr, None), list)


def test_invalid_entity(url_prefix):
    get(url_prefix + 'invalid_entity', 404)


def test_invalid_action(url_prefix):
    get(url_prefix + 'providers/invalid_action', 404)
