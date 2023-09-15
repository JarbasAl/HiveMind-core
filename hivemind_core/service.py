import asyncio
import base64
import os
import os.path
import random
from os import makedirs
from os.path import exists, join
from socket import gethostname
from threading import Thread
from typing import Callable, Dict, Any, Optional, Tuple

from OpenSSL import crypto
from ovos_config import Configuration
from ovos_utils.log import LOG
from ovos_utils.process_utils import ProcessStatus, StatusCallbackMap
from ovos_bus_client.session import Session
from ovos_utils.xdg_utils import xdg_data_home
from poorman_handshake import HandShake, PasswordHandShake
from pyee import EventEmitter
from tornado import web, ioloop
from tornado.platform.asyncio import AnyThreadEventLoopPolicy
from tornado.websocket import WebSocketHandler

from hivemind_bus_client.identity import NodeIdentity
from hivemind_core.database import ClientDatabase
from hivemind_core.protocol import HiveMindListenerProtocol, HiveMindClientConnection, HiveMindNodeType
from hivemind_presence import LocalPresence
from hivemind_ggwave import GGWaveMaster
from ovos_bus_client import MessageBusClient


def create_self_signed_cert(cert_dir=f"{xdg_data_home()}/hivemind",
                            name="hivemind") -> Tuple[str, str]:
    """
    If name.crt and name.key don't exist in cert_dir, create a new
    self-signed cert and key pair and write them into that directory.
    """
    CERT_FILE = name + ".crt"
    KEY_FILE = name + ".key"
    cert_path = join(cert_dir, CERT_FILE)
    key_path = join(cert_dir, KEY_FILE)
    makedirs(cert_dir, exist_ok=True)

    if not exists(join(cert_dir, CERT_FILE)) \
            or not exists(join(cert_dir, KEY_FILE)):
        # create a key pair
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, 2048)

        # create a self-signed cert
        cert = crypto.X509()
        cert.get_subject().C = "PT"
        cert.get_subject().ST = "Europe"
        cert.get_subject().L = "Mountains"
        cert.get_subject().O = "Jarbas AI"
        cert.get_subject().OU = "Powered by HiveMind"
        cert.get_subject().CN = gethostname()
        cert.set_serial_number(random.randint(0, 2000))
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(k)
        # TODO don't use sha1
        cert.sign(k, 'sha1')

        if not exists(cert_dir):
            makedirs(cert_dir)
        open(cert_path, "wb").write(
            crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        open(join(cert_dir, KEY_FILE), "wb").write(
            crypto.dump_privatekey(crypto.FILETYPE_PEM, k))

    return cert_path, key_path


def on_ready():
    LOG.info('HiveMind bus service ready!')


def on_alive():
    LOG.info('HiveMind bus service alive')


def on_started():
    LOG.info('HiveMind bus service started!')


def on_error(e='Unknown'):
    LOG.info('HiveMind bus failed to start ({})'.format(repr(e)))


def on_stopping():
    LOG.info('HiveMind bus is shutting down...')


class MessageBusEventHandler(WebSocketHandler):
    protocol: Optional[HiveMindListenerProtocol] = None

    @staticmethod
    def decode_auth(auth) -> Tuple[str, str]:
        userpass_encoded = bytes(auth, encoding="utf-8")
        userpass_decoded = base64.b64decode(userpass_encoded).decode("utf-8")
        name, key = userpass_decoded.split(":")
        return name, key

    def on_message(self, message):
        message = self.client.decode(message)
        LOG.info(f"received {self.client.peer} message: {message}")
        self.protocol.handle_message(message, self.client)

    def open(self):
        auth = self.request.uri.split("/?authorization=")[-1]
        name, key = self.decode_auth(auth)
        LOG.info(f"authorizing client: {name}")

        # in regular handshake an asymmetric key pair is used
        handshake = HandShake(HiveMindService.identity.private_key)
        self.client = HiveMindClientConnection(key=key, name=name,
                                               ip=self.request.remote_ip, socket=self, sess=Session(),
                                               handshake=handshake, loop=self.protocol.loop)

        with ClientDatabase() as users:
            user = users.get_client_by_api_key(key)
            if not user:
                LOG.error("Client provided an invalid api key")
                self.protocol.handle_invalid_key_connected(self.client)
                self.close()
                return

            self.client.crypto_key = user.crypto_key
            self.client.blacklist = user.blacklist.get("messages", [])
            self.client.allowed_types = user.allowed_types
            if user.password:
                # pre-shared password to derive aes_key
                self.client.pswd_handshake = PasswordHandShake(user.password)

            self.client.node_type = HiveMindNodeType.NODE  # TODO . placeholder

            if not self.client.crypto_key and \
                    not self.protocol.handshake_enabled \
                    and self.protocol.require_crypto:
                LOG.error("No pre-shared crypto key for client and handshake disabled, "
                          "but configured to require crypto!")
                # clients requiring handshake support might fail here
                self.protocol.handle_invalid_protocol_version(self.client)
                self.close()
                return

        self.protocol.handle_new_client(self.client)
        # self.write_message(Message("connected").serialize())

    def on_close(self):
        LOG.info(f"disconnecting client: {self.client.peer}")
        self.protocol.handle_client_disconnected(self.client)

    def check_origin(self, origin) -> bool:
        return True


class HiveMindService:
    identity = NodeIdentity()

    def __init__(self, 
                 alive_hook: Callable = on_alive,
                 started_hook: Callable = on_started,
                 ready_hook: Callable = on_ready,
                 error_hook: Callable = on_error,
                 stopping_hook: Callable = on_stopping,
                 websocket_config: Optional[Dict[str, Any]] = None):

        websocket_config = websocket_config or \
                Configuration().get('hivemind_websocket', {})
        callbacks = StatusCallbackMap(on_started=started_hook,
                                      on_alive=alive_hook,
                                      on_ready=ready_hook,
                                      on_error=error_hook,
                                      on_stopping=stopping_hook)

        self.bus = MessageBusClient(emitter=EventEmitter())
        self.bus.run_in_thread()
        self.bus.connected_event.wait()

        self.status = ProcessStatus('HiveMind', callback_map=callbacks)
        self.host = websocket_config.get('host') or "0.0.0.0"
        self.port = websocket_config.get('port') or 5678
        self.ssl = websocket_config.get('ssl', False)
        self.cert_dir = websocket_config.get('cert_dir') or f"{xdg_data_home()}/hivemind"
        self.cert_name = websocket_config.get('cert_name') or "hivemind"  # name + ".crt"/".key"

        self.presence = LocalPresence(name=self.identity.name,
                                      service_type=HiveMindNodeType.MIND,
                                      upnp=websocket_config.get('upnp', False),
                                      port=self.port,
                                      zeroconf=websocket_config.get('zeroconf', False))
        try:
            # TODO - silent_mode should be controlled via external events
            # to start enrolling new devices on demand
            self.ggwave = GGWaveMaster(bus=self.bus, silent_mode=True)
        except Exception as e:
            LOG.error(f"ggwave failed to start: {e}")
            self.ggwave = None

    def run(self):
        self.status.set_alive()
        asyncio.set_event_loop_policy(AnyThreadEventLoopPolicy())
        loop = ioloop.IOLoop.current()

        self.protocol = HiveMindListenerProtocol(loop=loop)
        self.protocol.bind(MessageBusEventHandler, self.bus)
        self.status.bind(self.bus)
        self.status.set_started()

        routes: list = [("/", MessageBusEventHandler)]
        application = web.Application(routes)

        if self.ssl:
            CERT_FILE = f"{self.cert_dir}/{self.cert_name}.crt"
            KEY_FILE = f"{self.cert_dir}/{self.cert_name}.key"
            if not os.path.isfile(KEY_FILE):
                LOG.info(f"generating self-signed SSL certificate")
                CERT_FILE, KEY_FILE = create_self_signed_cert(self.cert_dir, self.cert_name)
            LOG.debug("using ssl key at " + KEY_FILE)
            LOG.debug("using ssl certificate at " + CERT_FILE)
            ssl_options = {"certfile": CERT_FILE, "keyfile": KEY_FILE}

            LOG.info("wss connection started")
            application.listen(self.port, self.host, ssl_options=ssl_options)
        else:
            LOG.info("ws connection started")
            application.listen(self.port, self.host)

        self.presence.start()
        if self.ggwave is not None:
            self.ggwave.start()
            LOG.info("listening for ggwave audio handshakes")

        self.status.set_ready()

        loop.start()

        self.status.set_stopping()
        self.presence.stop()
        if self.ggwave is not None:
            self.ggwave.stop()
