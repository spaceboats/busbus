from setuptools import setup, find_packages
import os

SETUP_DIR = os.path.dirname(__file__)


def get_requires():
    with open(os.path.join(SETUP_DIR, 'requirements.txt'), 'r') as f:
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
    version='0.0.1',
    license='MIT',
    url='https://github.com/spaceboats/busbus',
    packages=find_packages(),
    install_requires=list(get_requires()),
)
