from setuptools import setup, find_packages
import collections
import os

SETUP_DIR = os.path.abspath(os.path.dirname(__file__))


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


setup(
    name='busbus',
    version='0.1.0',
    license='MIT',
    url='https://github.com/spaceboats/busbus',
    packages=find_packages(),
    package_data={
        'busbus.provider': ['*.sql'],
    },
    install_requires=list(get_requires()),
    extras_require=ExtraRequires(),
)
