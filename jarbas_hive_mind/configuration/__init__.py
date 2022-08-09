from json_database import JsonStorageXDG
from os.path import join, exists, isdir
from os import makedirs
from jarbas_hive_mind.settings import DEFAULT_PORT, DATA_PATH, \
    MYCROFT_WEBSOCKET_CONFIG
from ovos_utils.xdg_utils import xdg_config_home


def default_config():
    return {'data_path': DATA_PATH,
            'database': join(DATA_PATH, "database", "clients.db"),
            'log_blacklist': [],
            'max_connections': -1,
            'mycroft_bus': MYCROFT_WEBSOCKET_CONFIG,
            'port': DEFAULT_PORT,
            'ssl': {'certificates': join(DATA_PATH, "certs"),
                    'ssl_certfile': 'HiveMind.crt',
                    'ssl_keyfile': 'HiveMind.key'}
            }


# TODO use ovos_utils merge_dict
def _merge_defaults(base, default=None):
    """
        Recursively merging configuration dictionaries.

        Args:
            base:  Target for merge
            default: Dictionary to merge into base if key not present
    """
    default = default or default_config()
    for k, dv in default.items():
        bv = base.get(k)
        if isinstance(dv, dict) and isinstance(bv, dict):
            _merge_defaults(bv, dv)
        elif k not in base:
            base[k] = dv
    return base


CONFIGURATION = JsonStorageXDG("hivemind",
                               xdg_folder=xdg_config_home(),
                               subfolder="jarbasHiveMind",
                               extension="conf")

CONFIGURATION = _merge_defaults(CONFIGURATION)

# ensure directories exist
if not exists(CONFIGURATION.path):
    CONFIGURATION.store()

if not isdir(CONFIGURATION["data_path"]):
    makedirs(CONFIGURATION["data_path"])

if not isdir(CONFIGURATION["ssl"]["certificates"]):
    makedirs(CONFIGURATION["ssl"]["certificates"])
