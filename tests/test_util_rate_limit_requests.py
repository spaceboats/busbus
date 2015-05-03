from busbus.util import RateLimitRequests

from datetime import datetime, timedelta
import httpbin
import pytest
import requests
import time
from wsgi_intercept import requests_intercept, add_wsgi_intercept


@pytest.fixture(scope='module')
def url_prefix(request):
    host = 'httpbin.org'
    port = 80
    requests_intercept.install()
    add_wsgi_intercept(host, port, lambda: httpbin.app)

    @request.addfinalizer
    def fin():
        requests_intercept.uninstall()

    return 'http://{0}:{1}/'.format(host, port)


def test_request(url_prefix):
    resp = requests.get(url_prefix + '/get')
    assert len(resp.json()['args']) == 0


def test_repeat_get_no_rate_limit(url_prefix):
    session = RateLimitRequests()
    resp1 = session.get(url_prefix + '/cookies')
    session.get(url_prefix + '/cookies/set?a=b')
    resp2 = session.get(url_prefix + '/cookies')
    assert resp1.json()['cookies'] != resp2.json()['cookies']


def test_get_interval(url_prefix):
    session = RateLimitRequests(interval=0.2)
    resp1 = session.get(url_prefix + '/get')
    t = datetime.now()
    resp2 = session.get(url_prefix + '/ip')
    assert datetime.now() - t > timedelta(seconds=0.1)


def test_repeat_get_url_interval(url_prefix):
    session = RateLimitRequests(url_interval=1)
    t = datetime.now()
    resp1 = session.get(url_prefix + '/cookies')
    session.get(url_prefix + '/cookies/set?a=b')
    resp2 = session.get(url_prefix + '/cookies')
    assert datetime.now() - t < timedelta(seconds=1)
    assert resp1 == resp2
    assert resp1.json()['cookies'] == resp2.json()['cookies']
    time.sleep(1)
    resp3 = session.get(url_prefix + '/cookies')
    assert resp1 != resp3
    assert resp1.json()['cookies'] != resp3.json()['cookies']


def test_post(url_prefix):
    session = RateLimitRequests()
    assert not session.post(url_prefix + '/post').json()['form']
