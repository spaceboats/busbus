# coding=utf-8

import busbus.web
from .conftest import SampleGTFSProvider

import cherrypy
import pytest
import requests
from wsgi_intercept import requests_intercept, add_wsgi_intercept


@pytest.fixture(scope='module')
def url_prefix(request, engine_config):
    engine = busbus.web.Engine(engine_config)
    SampleGTFSProvider(engine)

    # https://cherrypy.readthedocs.org/en/latest/deploy.html
    # § Embedding into another WSGI framework
    cherrypy.config.update({'environment': 'embedded',
                            'global': {'request.throw_errors': True}})
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


@pytest.fixture(scope='module')
def provider_id(url_prefix):
    data, resp = get(url_prefix + 'providers')
    return data['providers'][0]['id']


def get(url, code=200):
    resp = requests.get(url)
    assert resp.status_code == code
    assert resp.headers['content-type'] == 'application/json'
    data = resp.json()
    assert 'request' in data
    assert 'status' in data['request']
    assert data['request']['status'] in (('error',) if code // 100 == 4
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


def test_nested(url_prefix, provider_id):
    data, resp = get(url_prefix + 'routes?provider.id={0}'.format(provider_id))
    assert data['routes']


def test_query(url_prefix):
    data, resp = get(url_prefix + 'stops')
    assert 'stops' in data
    assert len(data['stops']) == 9


def test_unexpand_none(url_prefix):
    data, resp = get(url_prefix + 'routes')
    assert set(data['routes'][0]['agency'].keys()) == set(['id'])


def test_unexpand_agencies(url_prefix):
    data, resp = get(url_prefix + 'routes?_expand=agencies')
    assert 'timezone' in data['routes'][0]['agency']


def test_limit(url_prefix):
    data, resp = get(url_prefix + 'routes?_limit=1')
    assert len(data['routes']) == 1


def test_invalid_limit(url_prefix):
    get(url_prefix + 'routes?_limit=-422', 422)


def test_limit_on_action(url_prefix):
    data, resp = get(url_prefix + ('stops/find?latitude=36.914778&'
                                   'longitude=-116.767900&distance=10000&'
                                   '_limit=1'))
    assert len(data['stops']) == 1


def test_stops_find(url_prefix):
    data, resp = get(url_prefix + ('stops/find?latitude=36.914778&'
                                   'longitude=-116.767900&distance=100'))
    assert len(data['stops']) == 1
    assert data['stops'][0]['id'] == 'NADAV'


def test_stops_find_missing_attrs(url_prefix):
    data, resp = get(url_prefix + 'stops/find', 422)
    assert data['error'].startswith('missing attributes')


def test_routes_directions(url_prefix, provider_id):
    data, resp = get(url_prefix + ('routes/directions?route.id=AB&'
                                   'provider.id={0}'.format(provider_id)))
    assert len(data['directions']) == 2


def test_routes_directions_missing_attrs(url_prefix):
    data, resp = get(url_prefix + 'routes/directions', 422)
    assert data['error'].startswith('missing attributes')
