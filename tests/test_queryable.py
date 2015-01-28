from busbus.queryable import Queryable


def test_queryable():
    q = Queryable(xrange(10)).where(lambda x: x % 5 == 0)
    assert next(q) == 0
    assert next(q) == 5
