from busbus.queryable import Queryable

from six.moves import range


def test_queryable():
    q = Queryable(range(10)).where(lambda x: x % 5 == 0)
    assert next(q) == 0
    assert next(q) == 5
