import asyncio
import ssl
from os.path import join, exists, isfile

from ovos_utils.log import LOG
from ovos_utils.messagebus import get_mycroft_bus

from jarbas_hive_mind.configuration import CONFIGURATION
from jarbas_hive_mind.nodes.master import HiveMind, HiveMindProtocol
from jarbas_hive_mind.settings import DEFAULT_PORT
from jarbas_hive_mind.utils import create_self_signed_cert


class HiveMindWebsocketServer:
    _autorun = True
    default_factory = HiveMind
    default_protocol = HiveMindProtocol

    def __init__(self, port=DEFAULT_PORT, max_cons=-1, bus=None,
                 host="0.0.0.0", accept_self_signed=True):
        self.loop = None
        self.host = host
        self.port = port
        self.max_cons = max_cons
        self._use_ssl = CONFIGURATION["ssl"].get("use_ssl", False)
        self.certificate_path = CONFIGURATION["ssl"]["certificates"]
        self._key_file = CONFIGURATION["ssl"].get("ssl_keyfile",
                                                  "HiveMind.key")
        self._cert_file = CONFIGURATION["ssl"].get("ssl_certfile",
                                                   "HiveMind.crt")
        self.bus = bus
        self.accept_self_signed = accept_self_signed

    def _set_event_loop(self, loop=None):
        self.loop = loop or asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        return self.loop

    def bind(self, bus=None):
        # TODO read config for bus options
        self.bus = bus or get_mycroft_bus()

    @property
    def ssl_key(self):
        if isfile(self._key_file):
            return self._key_file
        return join(self.certificate_path, self._key_file)

    @property
    def ssl_cert(self):
        if isfile(self._cert_file):
            return self._cert_file
        return join(self.certificate_path, self._cert_file)

    def load_config(self, config=CONFIGURATION):
        # read configuration
        self.port = config["port"]
        self.max_cons = config.get("max_connections", -1)

        ssl_config = config.get("ssl", {})
        self.certificate_path = ssl_config.get("certificates",
                                               self.certificate_path)
        self._key_file = ssl_config.get("ssl_keyfile", self._key_file)
        self._cert_file = ssl_config.get("ssl_certfile", self._cert_file)
        self._use_ssl = ssl_config.get("use_ssl", True)

        # generate self signed keys
        if not exists(self.ssl_key) and self.accept_self_signed and \
                self.is_secure:
            LOG.warning("ssl keys dont exist, creating self signed certificates")
            self.generate_keys(self.certificate_path)

    @property
    def is_secure(self):
        return self._use_ssl

    @property
    def address(self):
        if self.is_secure:
            return "wss://" + self.host + ":" + str(self.port)
        return "ws://" + self.host + ":" + str(self.port)

    @property
    def peer(self):
        return "tcp4:" + self.host + ":" + str(self.port)

    @staticmethod
    def generate_keys(path=CONFIGURATION["ssl"]["certificates"],
                      key_name="HiveMind"):
        LOG.info("creating self signed SSL keys")
        name = key_name.split("/")[-1].replace(".key", "")
        create_self_signed_cert(path, name)
        cert = path + "/" + name + ".crt"
        key = path + "/" + name + ".key"
        LOG.info("key created at: " + key)
        LOG.info("crt created at: " + cert)

    def secure_listen(self, key=None, cert=None, factory=None, protocol=None):
        self._use_ssl = True
        self._ssl_key = key or self.ssl_key
        self._ssl_cert = cert or self.ssl_cert

        self.factory = factory or self.default_factory(bus=self.bus)
        self.factory.protocol = protocol or self.default_protocol
        if self.max_cons >= 0:
            self.factory.setProtocolOptions(maxConnections=self.max_cons)
        self.factory.bind(self)

        if self._autorun:
            self.run()
        return self.factory

    def unsafe_listen(self, factory=None, protocol=None):
        self._use_ssl = False
        self.factory = factory or self.default_factory(bus=self.bus)
        self.factory.protocol = protocol or self.default_protocol
        if self.max_cons >= 0:
            self.factory.setProtocolOptions(maxConnections=self.max_cons)
        self.factory.bind(self)

        if self._autorun:
            self.run()
        return self.factory

    def run(self):
        if not self.loop:
            self._set_event_loop()

        if self.is_secure:
            ssl_context = ssl.create_default_context()
            if self.accept_self_signed:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            ssl_context.load_cert_chain(self.ssl_cert, self.ssl_key)

            coro = self.loop.create_server(self.factory, self.host,
                                           self.port, ssl=ssl_context)
            LOG.info("HiveMind Listening: " + self.address)
        else:
            coro = self.loop.create_server(self.factory, self.host, self.port)
            LOG.info("HiveMind Listening (UNSECURED): " + self.address)

        self.server = self.loop.run_until_complete(coro)
        if not self.loop.is_running():
            self.loop.run_forever()

    def listen(self, factory=None, protocol=None):
        if self.is_secure:
            return self.secure_listen(factory=factory, protocol=protocol)
        else:
            return self.unsafe_listen(factory=factory, protocol=protocol)

    def stop(self):
        if self.server:
            self.server.close()
        if self.loop:
            self.loop.close()
