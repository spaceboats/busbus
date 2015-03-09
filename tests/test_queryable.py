from busbus.queryable import Queryable

from test_provider_gtfs import provider

from six.moves import range
import pytest


def test_queryable_where_func():
    q = Queryable(range(10)).where(lambda x: x % 5 == 0)
    assert next(q) == 0
    assert next(q) == 5
    with pytest.raises(StopIteration):
        next(q)


def test_queryable_where_manyfunc():
    q = Queryable(range(10)).where(lambda x: x % 2 == 0)
    q = q.where(lambda x: x % 3 == 0)
    assert next(q) == 0
    assert next(q) == 6
    with pytest.raises(StopIteration):
        next(q)


def test_queryable_where_kwargs(provider):
    q = provider.agencies.where(id='DTA')
    assert len(list(q)) == 1


def test_queryable_where_none():
    q = Queryable(range(10))
    q_prime = q.where()
    assert q is q_prime
