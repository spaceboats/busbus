from busbus.util import Config

import os
import pytest


def test_config_defaults():
    config = Config()
    assert config['url_cache_dir'].endswith('/.busbus/cache')


def test_config_without_home():
    old_home = os.environ['HOME']
    del os.environ['HOME']
    config = Config()
    assert (os.path.abspath(config['url_cache_dir']) ==
            os.path.abspath('.busbus/cache'))
    os.environ['HOME'] = old_home


def test_config_busbus_dir():
    config = Config({'busbus_dir': '/path/to/.busbus'})
    assert config['url_cache_dir'] == '/path/to/.busbus/cache'


def test_config_keyerror():
    config = Config()
    with pytest.raises(KeyError) as exc:
        config['The weather in London']
    assert exc.value.args[0] == 'The weather in London'
