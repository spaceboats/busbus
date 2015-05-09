from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand

import collections
import errno
import os
import sys
import zipfile

SETUP_DIR = os.path.abspath(os.path.dirname(__file__))
VERSION = '0.1.0'


class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = ['--pep8']

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        fetch_test_data()

        import pytest
        errno = pytest.main(self.pytest_args)
        sys.exit(errno)


class ExtraRequires(collections.Mapping):
    suffix = '-requirements.txt'

    def __getitem__(self, key):
        return get_requires(key + self.suffix)

    def __iter__(self):
        for filename in os.listdir(SETUP_DIR):
            if (os.path.isfile(filename) and filename.endswith(self.suffix)):
                yield filename[:-len(self.suffix)]

    def __len__(self):
        return sum(1 for _ in self)


def get_requires(filename='requirements.txt'):
    with open(os.path.join(SETUP_DIR, filename), 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#') or not line:
                continue
            elif '#' in line:
                yield line.split('#', 1)[0]
            else:
                yield line


def fetch_test_data():
    """
    Fetches test data if it's missing.
    """

    data_dir = os.path.join(SETUP_DIR, 'tests', 'data')

    # if tests/data exists, is empty, and .gitmodules exists, run the
    # appropriate git-submodule(1) command
    if (os.path.isdir(data_dir) and not os.listdir(data_dir) and
            os.path.isfile(os.path.join(SETUP_DIR, '.gitmodules'))):
        import subprocess
        subprocess.call(['git', 'submodule', 'update',
                         '--init', '--recursive'])
    # if tests/data either doesn't exist or is empty, download the
    # busbus-test-data zip from GitHub and unpack it
    else:
        try:
            os.mkdir(data_dir)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise

        if not os.listdir(data_dir):
            # at this point requests and six are already installed
            import requests
            import six

            resp = requests.get('https://github.com/spaceboats/busbus-test-'
                                'data/archive/v{0}.zip'.format(VERSION))
            with zipfile.ZipFile(six.BytesIO(resp.content)) as z:
                prefix = 'busbus-test-data-{0}/'.format(VERSION)
                for filename in z.namelist():
                    if filename == prefix or not filename.startswith(prefix):
                        continue
                    filename = filename[len(prefix):]
                    if filename.endswith('/'):
                        os.mkdir(os.path.join(data_dir, filename))
                    else:
                        with open(os.path.join(data_dir, filename), 'wb') as f:
                            f.write(z.read(prefix + filename))


setup(
    name='busbus',
    version=VERSION,
    license='MIT',
    url='https://github.com/spaceboats/busbus',
    packages=find_packages(),
    package_data={
        'busbus.provider': ['*.sql'],
    },
    install_requires=list(get_requires()),
    tests_require=list(get_requires('dev-requirements.txt')),
    extras_require=ExtraRequires(),
    cmdclass={
        'test': PyTest,
    },
)
