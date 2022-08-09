import base64
import json

from autobahn.asyncio.websocket import WebSocketServerProtocol, WebSocketServerFactory
from ovos_utils.log import LOG
from ovos_utils.messagebus import FakeBus
from ovos_utils.messagebus import Message, get_mycroft_bus

from HiveMind_presence import LocalPresence
from jarbas_hive_mind.database import ClientDatabase
from jarbas_hive_mind.exceptions import UnauthorizedKeyError
from jarbas_hive_mind.interface import HiveMindMasterInterface
from jarbas_hive_mind.message import HiveMessage, HiveMessageType
from jarbas_hive_mind.nodes import HiveMindNodeType
from jarbas_hive_mind.utils import decrypt_from_json, encrypt_as_json


# protocol
class HiveMindProtocol(WebSocketServerProtocol):
    platform = "HiveMindV0.7"

    @staticmethod
    def decode_auth(request):
        # see if params were passed in url
        auth = request.params.get("authorization")
        if auth:
            auth = auth[0]
            userpass_encoded = bytes(auth, encoding="utf-8")
        else:
            # regular websocket auth wss://user:pass@url:port
            auth = request.headers.get("authorization")
            userpass_encoded = bytes(auth, encoding="utf-8")
            if userpass_encoded.startswith(b"Basic "):
                userpass_encoded = userpass_encoded[6:-2]
            else:
                userpass_encoded = userpass_encoded[2:-1]
        userpass_decoded = base64.b64decode(userpass_encoded).decode("utf-8")
        name, key = userpass_decoded.split(":")
        return name, key

    def onConnect(self, request):
        LOG.info("Client connecting: {0}".format(request.peer))

        name, key = self.decode_auth(request)

        ip = request.peer.split(":")[1]
        context = {"source": self.peer}
        self.platform = request.headers.get("platform", "unknown")

        try:
            with ClientDatabase() as users:
                user = users.get_client_by_api_key(key)
                if not user:
                    raise UnauthorizedKeyError
                self.crypto_key = users.get_crypto_key(key)
        except UnauthorizedKeyError:
            LOG.error("Client provided an invalid api key")
            self.factory.mycroft_send("hive.client.connection.error",
                                      {"error": "invalid api key",
                                       "ip": ip,
                                       "api_key": key,
                                       "platform": self.platform},
                                      context)
            raise

        # send message to internal mycroft bus
        data = {"ip": ip, "headers": request.headers}
        with ClientDatabase() as users:
            self.blacklist = users.get_blacklist_by_api_key(key)
        self.factory.mycroft_send("hive.client.connect", data, context)
        # return a pair with WS protocol spoken (or None for any) and
        # custom headers to send in initial WS opening handshake HTTP response
        headers = {"server": self.platform}
        return (None, headers)

    def onOpen(self):
        """
       Connection from client is opened. Fires after opening
       websockets handshake has been completed and we can send
       and receive messages.

       Register client in factory, so that it is able to track it.
       """
        LOG.info("WebSocket connection open.")
        self.factory.register_client(self, self.platform)

    def onMessage(self, payload, isBinary):

        if isBinary:
            LOG.debug(
                "Binary message received: {0} bytes".format(len(payload)))
        else:
            payload = self.decode(payload)

        self.factory.on_message(self, payload, isBinary)

    def onClose(self, wasClean, code, reason):
        self.factory.unregister_client(self, reason="connection closed")
        LOG.info("WebSocket connection closed: {0}".format(reason))
        ip = self.peer.split(":")[1]
        data = {"ip": ip, "code": code, "reason": "connection closed",
                "wasClean": wasClean}
        context = {"source": self.peer}
        self.factory.mycroft_send("hive.client.disconnect", data, context)

    def connectionLost(self, reason):
        """
       Client lost connection, either disconnected or some error.
       Remove client from list of tracked connections.
       """
        self.factory.unregister_client(self, reason="connection lost")
        LOG.info("WebSocket connection lost: {0}".format(reason))
        ip = self.peer.split(":")[1]
        data = {"ip": ip, "reason": "connection lost"}
        context = {"source": self.peer}
        self.factory.mycroft_send("hive.client.disconnect", data, context)

    def decode(self, payload):
        payload = payload.decode("utf-8")
        if self.crypto_key:
            if "ciphertext" in payload:
                payload = decrypt_from_json(self.crypto_key, payload)
            else:
                LOG.warning("Message was unencrypted")
        if isinstance(payload, str):
            payload = json.loads(payload)
        return HiveMessage(**payload)

    def sendMessage(self,
                    payload,
                    isBinary=False,
                    fragmentSize=None,
                    sync=False,
                    doNotCompress=False):
        if isinstance(payload, dict):
            payload = json.dumps(payload)
        if self.crypto_key and not isBinary:
            payload = encrypt_as_json(self.crypto_key, payload)
        if isinstance(payload, str):
            payload = bytes(payload, encoding="utf-8")
        super().sendMessage(payload, isBinary,
                            fragmentSize=fragmentSize,
                            sync=sync,
                            doNotCompress=doNotCompress)


class HiveMind(WebSocketServerFactory):
    node_type = HiveMindNodeType.MIND

    def __init__(self, bus=None, announce=True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # list of clients
        self.listener = None
        self.clients = {}
        # ip block policy
        self.ip_list = []
        self.blacklist = True  # if False, ip_list is a whitelist
        # mycroft_ws
        if bus is False:
            self.bus = FakeBus()
        else:
            self.bus = bus or get_mycroft_bus()
        self.register_mycroft_messages()

        self.interface = HiveMindMasterInterface(self)
        self.announce = announce
        self.presence = None

    def start_announcing(self):
        self.presence = LocalPresence(port=self.listener.port, ssl=self.listener.is_secure)
        self.presence.start()

    def bind(self, listener):
        self.listener = listener
        if self.announce:
            self.start_announcing()

    @property
    def peer(self):
        if self.listener:
            return self.listener.peer
        return None

    @property
    def node_id(self):
        """ semi-unique id, only meaningful for the client that is
        connected, other hive nodes do not know what node this is"""
        return f"{self.peer}:{self.node_type}"

    def mycroft_send(self, msg_type, data=None, context=None):
        data = data or {}
        context = context or {}
        if isinstance(msg_type, Message):
            msg = msg_type
        else:
            msg = Message(msg_type, data, context)
        if "client_name" not in msg.context:
            msg.context["client_name"] = self.protocol.platform
        self.bus.emit(msg)

    def register_mycroft_messages(self):
        self.bus.on("message", self.handle_outgoing_mycroft)
        self.bus.on('hive.send.downstream', self.handle_send)

    def shutdown(self):
        if self.presence:
            self.presence.stop()
        self.bus.remove('message', self.handle_outgoing_mycroft)
        self.bus.remove('hive.send.downstream', self.handle_send)

    # websocket handlers
    def handle_register(self, client, platform):
        """ called before registering a client, subclasses can take
        additional actions here """

    def register_client(self, client, platform=None):
        """
       Add client to list of managed connections.
       """
        platform = platform or "unknown"
        LOG.info("registering client: " + str(client.peer))
        t, ip, sock = client.peer.split(":")
        # see if ip address is blacklisted
        if ip in self.ip_list and self.blacklist:
            LOG.warning("Blacklisted ip tried to connect: " + ip)
            self.unregister_client(client, reason="Blacklisted ip")
            return
        # see if ip address is whitelisted
        elif ip not in self.ip_list and not self.blacklist:
            LOG.warning("Unknown ip tried to connect: " + ip)
            #  if not whitelisted kick
            self.unregister_client(client, reason="Unknown ip")
            return
        self.clients[client.peer] = {"instance": client,
                                     "status": "connected",
                                     "platform": platform}
        self.handle_register(client, platform)
        msg = HiveMessage(HiveMessageType.HELLO,
                          payload={"peer": client.peer,
                                   "pubkey": None,  # TODO - hive identity
                                   "node_id": self.node_id})
        client.sendMessage(msg.serialize())

    def handle_unregister(self, client, code, reason, context):
        """ called before unregistering a client, subclasses can take
        additional actions here """

    def unregister_client(self, client, code=3078,
                          reason="unregister client request"):
        """
       Remove client from list of managed connections.
       """

        LOG.info("deregistering client: " + str(client.peer))
        if client.peer in self.clients.keys():
            client_data = self.clients[client.peer] or {}
            j, ip, sock_num = client.peer.split(":")
            context = {"user": client_data.get("names", ["unknown_user"])[0],
                       "source": client.peer}
            self.handle_unregister(client, code, reason, context)
            self.bus.emit(
                Message("hive.client.disconnect",
                        {"reason": reason, "ip": ip, "sock": sock_num},
                        context))
            client.sendClose(code, reason)
            self.clients.pop(client.peer)

    def handle_binary_message(self, client, payload):
        """ binary data handler, can be for example an audio stream """

    def handle_message(self, message, client):
        """ message handler for non default message types, subclasses can
        handle their own types here

        data contains payload, msg_type, source_peer, route

        message (HiveMessage): HiveMind message object
        """

    def on_message(self, client, message, isBinary):
        """
        message (HiveMessage): HiveMind message object

       Process message from client, decide what to do internally here
       """
        client_protocol, ip, sock_num = client.peer.split(":")

        if isBinary:
            self.handle_binary_message(client, message)
        else:
            # update internal peer ID
            message.update_source_peer(client.peer)
            message.add_target_peer(self.peer)
            message.update_hop_data()

            # mycroft Message handlers
            if message.msg_type == HiveMessageType.BUS:
                self.handle_bus_message(message, client)
            elif message.msg_type == HiveMessageType.SHARED_BUS:
                self.handle_client_bus(message.payload, client)

            # HiveMessage handlers
            elif message.msg_type == HiveMessageType.PROPAGATE:
                self.handle_propagate_message(message, client)
            elif message.msg_type == HiveMessageType.BROADCAST:
                self.handle_broadcast_message(message, client)
            elif message.msg_type == HiveMessageType.ESCALATE:
                self.handle_escalate_message(message, client)
            else:
                self.handle_message(message, client)

    # HiveMind protocol messages -  from slave -> master
    def handle_bus_message(self, message, client):
        self.on_bus(message.payload)
        self.handle_incoming_mycroft(message.payload, client)

    def on_bus(self, message):
        pass

    def handle_broadcast_message(self, message, client):
        """
        message (HiveMessage): HiveMind message object
        """
        # Slaves are not allowed to broadcast, by definition broadcast goes
        # downstream only, use propagate instead
        LOG.warning("Received broadcast message from downstream, illegal action")
        # TODO kick client for misbehaviour so it stops doing that?
        self.on_broadcast(message.payload)

    def on_broadcast(self, message):
        pass

    def handle_propagate_message(self, message, client):
        """
        message (HiveMessage): HiveMind message object
        """
        LOG.debug("ROUTE: " + str(message.route))
        LOG.debug("PAYLOAD_TYPE: " + message.payload.msg_type)
        LOG.debug("PAYLOAD: " + str(message.payload.payload))

        # unpack message
        pload = message.payload
        pload.replace_route(message.route)
        self.interface.propagate(pload)

        self.on_propagate(message.payload)

    def on_propagate(self, message):
        pass

    def handle_escalate_message(self, message, client):
        """
        message (HiveMessage): HiveMind message object
        """
        LOG.info("Received escalate message at: " + self.node_id)
        LOG.debug("ROUTE: " + str(message.route))
        LOG.debug("PAYLOAD_TYPE: " + message.payload.msg_type)
        LOG.debug("PAYLOAD: " + str(message.payload.payload))

        # unpack message
        pload = message.payload
        pload.replace_route(message.route)
        self.interface.escalate(pload)

        self.on_escalate(message.payload)

    def on_escalate(self, message):
        pass

    # HiveMind mycroft bus messages -  from slave -> master
    def handle_incoming_mycroft(self, message, client):
        """
        message (Message): mycroft bus message object
        """
        # A Slave wants to inject a message in internal mycroft bus
        # You are a Master, authorize bus message

        client_protocol, ip, sock_num = client.peer.split(":")

        # messages/skills/intents per user
        if message.msg_type in client.blacklist.get("messages", []):
            LOG.warning(client.peer + " sent a blacklisted message "
                                      "type: " + message.msg_type)
            return
        # TODO check intent / skill that will trigger

        # send client message to internal mycroft bus
        LOG.info("Forwarding message to mycroft bus from client: " +
                 str(client.peer))
        message.context["peer"] = message.context["source"] = client.peer
        self.mycroft_send(message.msg_type, message.data, message.context)

    def handle_client_bus(self, message, client):
        # this message is going inside the client bus
        # take any metrics you need
        LOG.info("Monitoring bus from client: " + client.peer)
        assert isinstance(message, Message)

    # mycroft handlers  - from master -> slave
    def handle_send(self, message):
        # mycroft wants to send a HiveMessage
        # a device can be both a master and a slave, occasionally the
        # protocol messages each process can't handle will be emitted to the
        # bus, the other process can then listen to them

        payload = message.data.get("payload")
        peer = message.data.get("peer")
        msg_type = message.data["msg_type"]

        if msg_type == HiveMessageType.PROPAGATE:
            self.interface.propagate(payload)
        elif msg_type == HiveMessageType.BROADCAST:
            self.interface.broadcast(payload)
        elif msg_type == HiveMessageType.ESCALATE:
            # only slaves can escalate, ignore silently
            # if this device is also a slave to something,
            # the slave service will also react to this message
            # and handle the escalate request
            pass

        # NOT a protocol specific message, send directly to requested peer
        elif peer:
            if peer in self.clients:
                # send message to client
                client = self.clients[peer].get("instance")
                self.interface.send(payload, client)
            else:
                LOG.error("That client is not connected")
                self.mycroft_send("hive.client.send.error",
                                  {"error": "That client is not connected",
                                   "peer": peer}, message.context)

    def handle_outgoing_mycroft(self, message=None):
        # forward internal messages to clients if they are the target
        if isinstance(message, dict):
            message = json.dumps(message)
        if isinstance(message, str):
            message = Message.deserialize(message)

        message.context = message.context or {}
        peers = message.context.get("destination") or []

        if not isinstance(peers, list):
            peers = [peers]

        for peer in peers:
            if peer and peer in self.clients:
                client = self.clients[peer].get("instance")
                msg = HiveMessage(HiveMessageType.BUS,
                                  source_peer=self.peer,
                                  payload=message)
                self.interface.send(msg, client)
