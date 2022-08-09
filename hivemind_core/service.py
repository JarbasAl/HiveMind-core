import base64
from threading import Thread

from ovos_bus_client.message import Message
from ovos_config import Configuration
from ovos_utils import create_daemon, wait_for_exit_signal
from ovos_utils.log import LOG
from ovos_utils.process_utils import ProcessStatus, StatusCallbackMap
from poorman_handshake import HandShake
from pyee import EventEmitter
from tornado import web, ioloop
from tornado.websocket import WebSocketHandler

from hivemind_core.database import ClientDatabase
from hivemind_core.identity import NodeIdentity
from hivemind_core.protocol import HiveMindListenerProtocol, HiveMindClientConnection, HiveMindNodeType
from hivemind_presence import LocalPresence


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
    protocol = None

    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)
        self.emitter = EventEmitter()

    @staticmethod
    def decode_auth(auth):
        userpass_encoded = bytes(auth, encoding="utf-8")
        userpass_decoded = base64.b64decode(userpass_encoded).decode("utf-8")
        name, key = userpass_decoded.split(":")
        return name, key

    def on(self, event_name, handler):
        self.emitter.on(event_name, handler)

    def on_message(self, message):
        if isinstance(message, bytes):
            LOG.info(f"received binary data: {len(message)}")
            self.protocol.handle_binary_message(message, self.client)
        else:
            message = self.client.decode(message)
            self.protocol.handle_message(message, self.client)

    def open(self):
        auth = self.request.uri.split("/?authorization=")[-1]
        name, key = self.decode_auth(auth)

        self.client = HiveMindClientConnection(key=key, name=name,
                                               ip=self.request.remote_ip, socket=self,
                                               handshake=HandShake(HiveMindService.identity.identity_file))

        with ClientDatabase() as users:
            user = users.get_client_by_api_key(key)
            if not user:
                LOG.error("Client provided an invalid api key")
                self.protocol.handle_invalid_key_connected(self.client)
                self.close()
                return

            if not self.client.crypto_key and \
                    not self.protocol.handshake_enabled \
                    and self.protocol.require_crypto:
                # TODO - protocol version error handler
                LOG.error("No crypto key registered for client, "
                          "but configured to require crypto!")
                self.protocol.handle_invalid_key_connected(self.client)
                self.close()

            self.client.crypto_key = users.get_crypto_key(key)
            self.client.node_type = HiveMindNodeType.NODE

        self.protocol.handle_new_client(self.client)
        self.write_message(Message("connected").serialize())

    def on_close(self):
        self.protocol.handle_client_disconnected(self.client)

    def check_origin(self, origin):
        return True


class HiveMindService(Thread):
    identity = NodeIdentity()

    def __init__(self, alive_hook=on_alive, started_hook=on_started, ready_hook=on_ready,
                 error_hook=on_error, stopping_hook=on_stopping):
        super().__init__()
        try:
            websocket_configs = Configuration()['websocket']
        except KeyError as ke:
            LOG.error('No websocket configs found ({})'.format(repr(ke)))
            raise

        callbacks = StatusCallbackMap(on_started=started_hook,
                                      on_alive=alive_hook,
                                      on_ready=ready_hook,
                                      on_error=error_hook,
                                      on_stopping=stopping_hook)
        self.status = ProcessStatus('gui_service', callback_map=callbacks)
        self.host = websocket_configs.get('host')
        self.port = websocket_configs.get('port')

        self.presence = LocalPresence(name=self.identity.name,
                                      service_type=HiveMindNodeType.MIND,
                                      upnp=websocket_configs.get('upnp', False),
                                      port=self.port,
                                      zeroconf=websocket_configs.get('zeroconf', False))

    def run(self):
        self.status.set_alive()
        self.protocol = HiveMindListenerProtocol()
        self.protocol.bind(MessageBusEventHandler)
        self.status.bind(self.protocol.internal_protocol.bus)
        self.status.set_started()

        routes = [("/", MessageBusEventHandler)]
        application = web.Application(routes)
        application.listen(self.port, self.host)

        self.presence.start()

        create_daemon(ioloop.IOLoop.instance().start)
        self.status.set_ready()
        wait_for_exit_signal()
        self.status.set_stopping()
        self.presence.stop()
