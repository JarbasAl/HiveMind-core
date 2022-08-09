from jarbas_hive_mind.nodes.master import HiveMind, HiveMindProtocol
from jarbas_hive_mind.configuration import CONFIGURATION
from jarbas_hive_mind.settings import DEFAULT_PORT
from jarbas_hive_mind.utils import create_self_signed_cert
from jarbas_hive_mind.exceptions import SecureConnectionFailed, HiveMindConnectionError
from jarbas_hive_mind.server import HiveMindWebsocketServer


def get_listener(port=DEFAULT_PORT, max_connections=-1, bus=None):
    return HiveMindWebsocketServer(port, max_connections, bus)
