from busbus.queryable import Queryable

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
    q = provider.agencies.where(id='The weather in London')
    with pytest.raises(StopIteration):
        next(q)


def test_queryable_where_none():
    q = Queryable(range(10))
    q_prime = q.where()
    assert q is q_prime


def test_queryable_dict_obj_kwargs():
    q = Queryable({'id': x, 'odd': bool(x % 2)} for x in range(10))
    assert next(q.where(odd=True))['id'] == 1


def test_queryable_unknown_obj_kwargs():
    q = Queryable(range(10)).where(qwerty='uiop')
    with pytest.raises(StopIteration):
        next(q)


@pytest.fixture(scope='function')
def qchain():
    q1 = Queryable(range(10)).where(lambda x: x % 3 == 0)
    q2 = Queryable(range(10)).where(lambda x: x % 2 == 0)
    return Queryable.chain(q1, q2)


def test_chained_len(qchain):
    assert len(list(qchain)) == 9


def test_chained_set(qchain):
    assert set(qchain) == set([0, 2, 3, 4, 6, 8, 9])


def test_chained_where_len(qchain):
    assert len(list(qchain.where(lambda x: x % 6 == 0))) == 4


def test_chained_where_set(qchain):
    assert set(qchain.where(lambda x: x % 6 == 0)) == set([0, 6])
