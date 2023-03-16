from typing import Optional
import configparser

CONFIG_PATH = 'config.ini'


# This is a stub for future gettext() i18n support
def _(txt):
    return txt


def get_config(fpath: Optional[str] =CONFIG_PATH):
    config = configparser.ConfigParser()
    config.read(fpath)
    return config
