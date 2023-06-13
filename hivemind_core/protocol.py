import json
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Optional, Dict, List

from ovos_bus_client import MessageBusClient
from ovos_bus_client.message import Message
from ovos_utils.log import LOG
from poorman_handshake import HandShake, PasswordHandShake
from tornado.websocket import WebSocketHandler

from hivemind_bus_client.message import HiveMessage, HiveMessageType
from hivemind_bus_client.util import decrypt_from_json, encrypt_as_json


class ProtocolVersion(IntEnum):
    ZERO = 0  # json only, no handshake, no binary
    ONE = 1  # handshake https://github.com/JarbasHiveMind/HiveMind-core/pull/29
    TWO = 2  # binary https://github.com/JarbasHiveMind/hivemind_websocket_client/pull/4


class HiveMindNodeType(str, Enum):
    CANDIDATE_NODE = "candidate"  # potential node, if it manages to connect...
    NODE = "node"  # anything connected to the hivemind is a "node"
    MIND = "mind"  # listening for connections and providing mycroft-core
    # (mycroft itself may be running in a different "mind")
    FAKECROFT = "fakecroft"  # a mind, that pretends to be running mycroft
    # but is actually using a different stack
    # (mycroft itself may be running in a different "mind")
    SLAVE = "slave"  # node that can be partially controlled by a "mind"
    TERMINAL = "terminal"  # user facing endpoint that connects to some Mind
    # and does not itself accept connections
    BRIDGE = "bridge"  # connects some external service to the hive

    # RESERVED
    HIVE = "hive"  # a collection of nodes
    MASTER_MIND = "master"  # the top level node, not connected to anything
    # but receiving connections


@dataclass
class HiveMindClientConnection:
    """ represents a connection to the hivemind listener """
    key: str
    ip: str
    name: str = "AnonClient"
    node_type: HiveMindNodeType = HiveMindNodeType.CANDIDATE_NODE
    handshake: Optional[HandShake] = None
    pswd_handshake: Optional[PasswordHandShake] = None
    socket: Optional[WebSocketHandler] = None
    crypto_key: Optional[str] = None
    blacklist: List[str] =  field(default_factory=list) # list of ovos message_type to never be sent to this client

    @property
    def peer(self):
        # friendly id that ovos components can use to refer to this connection
        # this is how ovos refers to connected nodes in message.context
        return f"{self.name}:{self.ip}"

    def send(self, message: HiveMessage):
        LOG.info(f"sending to {self.peer}: {message}")
        payload = message.serialize()  # json string
        if self.crypto_key and message.msg_type not in [HiveMessageType.HANDSHAKE,
                                                    HiveMessageType.HELLO]:
            payload = encrypt_as_json(self.crypto_key, payload)  # still a json string
            LOG.info(f"encrypted payload: {len(payload)}")
        else:
            LOG.warning(f"sent unencrypted!")
        self.socket.write_message(payload)

    def decode(self, payload: str):
        if self.crypto_key:
            if "ciphertext" in payload:
                payload = decrypt_from_json(self.crypto_key, payload)
            else:
                LOG.warning("Message was unencrypted")
                # TODO - some error if crypto is required
        else:
            pass  # TODO - reject anything except HELLO and HANDSHAKE
        if isinstance(payload, str):
            payload = json.loads(payload)
        return HiveMessage(**payload)

    def authorize(self, message: Message):
        """ parse the message being injected into ovos-core bus
        if this client is not authorized to inject it return False"""
        if message.msg_type in self.blacklist:
            return False

        # TODO check intent / skill that will trigger
        # we want for example to be able to block shutdown/reboot intents to random chat users
        return True


@dataclass()
class HiveMindListenerInternalProtocol:
    """ this class handles all interactions between a hivemind listener and a ovos-core messagebus"""
    bus: MessageBusClient

    def register_bus_handlers(self):
        self.bus.on("hive.send.downstream", self.handle_send)
        self.bus.on("message", self.handle_outgoing_mycroft)  # catch all

    @property
    def clients(self):
        return HiveMindListenerProtocol.clients

    # mycroft handlers  - from master -> slave
    def handle_send(self, message: Message):
        """ ovos wants to send a HiveMessage

        a device can be both a master and a slave, downstream messages are handled here

        HiveMindSlaveInternalProtocol will handle requests meant to go upstream
        """

        payload = message.data.get("payload")
        peer = message.data.get("peer")
        msg_type = message.data["msg_type"]

        hmessage = HiveMessage(msg_type,
                               payload=payload,
                               target_peers=[peer])

        if msg_type in [HiveMessageType.PROPAGATE, HiveMessageType.BROADCAST]:
            # this message is meant to be sent to all slave nodes
            for peer in self.clients:
                self.clients[peer].send(hmessage)
        elif msg_type == HiveMessageType.ESCALATE:
            # only slaves can escalate, ignore silently
            #   if this device is also a slave to something,
            #   HiveMindSlaveInternalProtocol will handle the request
            pass

        # NOT a protocol specific message, send directly to requested peer
        # ovos component is asking explicitly to send a message to a peer
        elif peer:
            if peer in self.clients:
                # send message to client
                client = self.clients[peer]
                client.send(hmessage)
            else:
                LOG.error("That client is not connected")
                self.bus.emit(message.forward(
                    "hive.client.send.error",
                    {"error": "That client is not connected", "peer": peer}))

    def handle_outgoing_mycroft(self, message: Message):
        """ forward internal messages to clients if they are the target
        here is where the client isolation happens,
        clients only get responses to their own messages"""
        if isinstance(message, str):
            # "message" is a special case in ovos-bus-client that is not deserialized
            message = Message.deserialize(message)

        # forward internal messages to clients if they are the target
        message.context = message.context or {}
        peers = message.context.get("destination") or []

        if not isinstance(peers, list):
            peers = [peers]

        for peer in peers:
            if peer and peer in self.clients:
                client = self.clients[peer]
                msg = HiveMessage(HiveMessageType.BUS,
                                  target_peers=peers,
                                  payload=message)
                client.send(msg)


@dataclass()
class HiveMindListenerProtocol:
    clients = {}
    internal_protocol: HiveMindListenerInternalProtocol = None
    peer: str = "master:0.0.0.0"

    require_crypto: bool = True  # throw error if crypto key not available
    handshake_enabled: bool = True  # generate a key per session if not pre-shared

    # below are optional callbacks to handle payloads
    # receives the payload + HiveMindClient that sent it
    escalate_callback = None  # slave asked to escalate payload
    illegal_callback = None  # slave asked to broadcast payload (illegal action)
    propagate_callback = None  # slave asked to propagate payload
    mycroft_bus_callback = None  # slave asked to inject payload into mycroft bus
    shared_bus_callback = None  # passive sharing of slave device bus (info)

    def bind(self, websocket, bus=None):
        websocket.protocol = self
        if bus is None:
            bus = MessageBusClient()
            bus.run_in_thread()
            bus.connected_event.wait()
        self.internal_protocol = HiveMindListenerInternalProtocol(bus)
        self.internal_protocol.register_bus_handlers()

    def handle_new_client(self, client: HiveMindClientConnection):
        LOG.info(f"new client: {client.peer}")
        self.clients[client.peer] = client
        message = Message("hive.client.connect",
                          {"ip": client.ip},
                          {"source": client.peer})
        self.internal_protocol.bus.emit(message)

        min_version = ProtocolVersion.ONE if client.crypto_key is None and self.require_crypto \
            else ProtocolVersion.ZERO
        max_version = ProtocolVersion.ONE

        msg = HiveMessage(HiveMessageType.HELLO,
                          payload={"pubkey": client.handshake.pubkey, # allows any node to verify messages are signed with this
                                   "peer": client.peer,  # this identifies the connected client in ovos message.context
                                   "node_id": self.peer})
        LOG.info(f"saying HELLO to: {client.peer}")
        client.send(msg)

        needs_handshake = not client.crypto_key and self.handshake_enabled

        # request client to start handshake (by sending client pubkey)
        payload = {
            "handshake": needs_handshake,  # tell the client it must do a handshake or connection will be dropped
            "min_protocol_version": min_version,
            "max_protocol_version": max_version,
            "preshared_key": client.crypto_key is not None,  # do we have a pre-shared key (V0 proto)
            "password": client.pswd_handshake is not None,  # is password available (V1 proto, replaces pre-shared key)
            "crypto_required": self.require_crypto  # do we allow unencrypted payloads
        }
        msg = HiveMessage(HiveMessageType.HANDSHAKE, payload)
        LOG.info(f"starting {client.peer} HANDSHAKE: {payload}")
        client.send(msg)
        # if client is in protocol V1 -> self.handle_handshake_message
        # clients can rotate their pubkey or session_key by sending a new handshake

    def handle_client_disconnected(self, client: HiveMindClientConnection):
        if client.peer in self.clients:
            self.clients.pop(client.peer)
        client.socket.close()
        message = Message("hive.client.disconnect",
                          {"ip": client.ip},
                          {"source": client.peer})
        self.internal_protocol.bus.emit(message)

    def handle_invalid_key_connected(self, client: HiveMindClientConnection):
        LOG.error("Client provided an invalid api key")
        message = Message("hive.client.connection.error",
                          {"error": "invalid api key", "peer": client.peer},
                          {"source": client.peer})
        self.internal_protocol.bus.emit(message)

    def handle_invalid_protocol_version(self, client: HiveMindClientConnection):
        LOG.error("Client does not satisfy protocol requirements")
        message = Message("hive.client.connection.error",
                          {"error": "protocol error", "peer": client.peer},
                          {"source": client.peer})
        self.internal_protocol.bus.emit(message)

    def handle_message(self, message: HiveMessage, client: HiveMindClientConnection):
        """
        message (HiveMessage): HiveMind message object

        Process message from client, decide what to do internally here
        """
        LOG.info(f"message: {message}")
        # update internal peer ID
        message.update_source_peer(client.peer)

        message.update_hop_data()

        if message.msg_type == HiveMessageType.HANDSHAKE:
            self.handle_handshake_message(message, client)

        # mycroft Message handlers
        elif message.msg_type == HiveMessageType.BUS:
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
            self.handle_unknown_message(message, client)

    # HiveMind protocol messages -  from slave -> master
    def handle_unknown_message(self, message: HiveMessage, client: HiveMindClientConnection):
        """ message handler for non default message types, subclasses can
        handle their own types here

        message (HiveMessage): HiveMind message object
        """

    def handle_handshake_message(self, message: HiveMessage,
                                 client: HiveMindClientConnection):
        LOG.info("handshake received, generating session key")
        payload = message.payload
        if "pubkey" in payload and client.handshake is not None:
            pub = payload.pop("pubkey")
            payload["envelope"] = client.handshake.generate_handshake(pub)
            client.crypto_key = client.handshake.secret  # start using new key

            # client side
            # LOG.info("Received encryption key")
            # pub = "pubkey from HELLO message"
            # if pub:  # validate server from known trusted public key
            #   self.handshake.receive_and_verify(payload["envelope"], pub)
            # else:  # implicitly trust server
            #   self.handshake.receive_handshake(payload["envelope"], pub)

            # self.crypto_key = self.handshake.secret
        elif client.pswd_handshake is not None and "envelope" in payload:
            # while the access key is transmitted, the password never is
            envelope = payload["envelope"]

            payload["envelope"] = client.pswd_handshake.generate_handshake()

            client.pswd_handshake.receive_handshake(envelope)
           # if not client.pswd_handshake.receive_and_verify(envelope):
           #     # TODO - different handles for invalid access key / invalid password
           #     self.handle_invalid_key_connected(client)
           #     client.socket.close()
        #    return


            # key is derived safely from password in both sides
            # the handshake is validating both ends have the same password
            # the key is never actually transmitted
            client.crypto_key = client.pswd_handshake.secret

            # client side
            # LOG.info("Received password envelope")
            # self.pswd_handshake.receive_and_verify(payload["envelope"])
            # self.crypto_key = self.pswd_handshake.secret
        else:
            # TODO - invalid handshake handler
            client.socket.close()
            return

        msg = HiveMessage(HiveMessageType.HANDSHAKE, payload)
        client.send(msg)  # client can recreate crypto_key on his side now

    def handle_binary_message(self, message: bytes, client: HiveMindClientConnection):
        pass  # TODO -  binary https://github.com/JarbasHiveMind/hivemind_websocket_client/pull/4

    def handle_bus_message(self, message: HiveMessage,
                           client: HiveMindClientConnection):
        if self.mycroft_bus_callback:
            self.mycroft_bus_callback(message.payload)

        self.handle_incoming_mycroft(message.payload, client)

    def handle_broadcast_message(self, message: HiveMessage, client: HiveMindClientConnection):
        """
        message (HiveMessage): HiveMind message object
        """
        # Slaves are not allowed to broadcast, by definition broadcast goes
        # downstream only, use propagate instead
        LOG.warning("Received broadcast message from downstream, illegal action")
        if self.illegal_callback:
            self.illegal_callback(message.payload)
        # TODO kick client for misbehaviour so it stops doing that?

    def _unpack_message(self, message: HiveMessage, client: HiveMindClientConnection):
        # propagate message to other peers
        pload = message.payload
        # keep info about which nodes this message has been to
        pload.replace_route(message.route)
        pload.update_source_peer(self.peer)
        pload.remove_target_peer(client.peer)
        return pload

    def handle_propagate_message(self, message: HiveMessage,
                                 client: HiveMindClientConnection):
        """
        message (HiveMessage): HiveMind message object
        """
        LOG.debug("ROUTE: " + str(message.route))
        LOG.debug("PAYLOAD_TYPE: " + message.payload.msg_type)
        LOG.debug("PAYLOAD: " + str(message.payload.payload))

        payload = self._unpack_message(message, client)

        if self.propagate_callback:
            self.propagate_callback(payload)

        # propagate message to other peers
        for peer in payload.target_peers:
            if peer in self.clients:
                self.clients[peer].send(payload)

        # send to other masters
        message = Message("hive.send.upstream", payload,
                          {"destination": "hive", "source": self.peer})
        self.internal_protocol.bus.emit(message)

    def handle_escalate_message(self, message: HiveMessage,
                                client: HiveMindClientConnection):
        """
        message (HiveMessage): HiveMind message object
        """
        LOG.info("Received escalate message from: " + client.peer)
        LOG.debug("ROUTE: " + str(message.route))
        LOG.debug("PAYLOAD_TYPE: " + message.payload.msg_type)
        LOG.debug("PAYLOAD: " + str(message.payload.payload))

        # unpack message
        payload = self._unpack_message(message, client)

        if self.escalate_callback:
            self.escalate_callback(payload)

        # send to other masters
        message = Message("hive.send.upstream", payload,
                          {"destination": "hive", "source": self.peer})
        self.internal_protocol.bus.emit(message)

    # HiveMind mycroft bus messages -  from slave -> master
    def handle_incoming_mycroft(self, message: Message, client: HiveMindClientConnection):
        """
        message (Message): mycroft bus message object
        """
        # A Slave wants to inject a message in internal mycroft bus
        # You are a Master, authorize bus message

        # messages/skills/intents per user
        if not client.authorize(message):
            LOG.warning(client.peer + " sent an unauthorized bus message")
            return

        # send client message to internal mycroft bus
        LOG.info(f"Forwarding message to mycroft bus from client: {client.peer}")
        message.context["peer"] = message.context["source"] = client.peer
        message.context["source"] = client.peer
        message = Message(message.msg_type, message.data, message.context)
        self.internal_protocol.bus.emit(message)

        if self.mycroft_bus_callback:
            self.mycroft_bus_callback(message)

    def handle_client_bus(self, message: Message, client: HiveMindClientConnection):
        # this message is going inside the client bus
        # take any metrics you need
        LOG.info("Monitoring bus from client: " + client.peer)
        if self.shared_bus_callback:
            self.shared_bus_callback(message)
