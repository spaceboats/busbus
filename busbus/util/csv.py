from __future__ import absolute_import

from busbus import util

import csv
import io
import six


class CSVReader(util.Iterable):
    """
    Ordinarily one would use csv.reader for their day-to-day CSV file reading.
    However, the csv module expects a str object in both Python 2 and 3; of
    course, this means that it wants bytes in Python 2 and unicode in Python 3.
    Likewise, the data it spits out is a str in both languages, but we want the
    equivalent of unicode in both languages (unicode and str, respectively).
    """

    def __init__(self, csvfile):
        if six.PY3:
            csvfile = io.TextIOWrapper(csvfile, encoding='utf-8')
        self.reader = csv.reader(csvfile)
        self.header = next(self.reader)
        if six.PY2:
            self.header = [x.decode('utf-8') for x in self.header]

    def __next__(self):
        row = next(self.reader)
        if six.PY2:
            row = (x.decode('utf-8') for x in row)
        return six.moves.zip(self.header, row)
