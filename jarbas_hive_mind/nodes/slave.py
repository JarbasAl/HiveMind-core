from jarbas_hive_mind.nodes.terminal import HiveMindTerminal
from jarbas_hive_mind.message import HiveMessageType, HiveMessage
from jarbas_hive_mind.nodes import HiveMindNodeType
from ovos_utils.log import LOG
from ovos_utils.messagebus import Message, get_mycroft_bus
import json


class HiveMindSlave(HiveMindTerminal):
    node_type = HiveMindNodeType.SLAVE

    def __init__(self, bus=None, connection=None, *args, **kwargs):
        super().__init__(connection, *args, **kwargs)
        # mycroft_ws
        self.bus = bus or get_mycroft_bus()
        self.register_mycroft_messages()

    # mycroft methods
    def register_mycroft_messages(self):
        self.bus.on("message", self.handle_outgoing_mycroft)
        self.bus.on("hive.send", self.handle_send)

    def shutdown(self):
        self.bus.remove("message", self.handle_outgoing_mycroft)
        self.bus.remove("hive.send", self.handle_send)

    def handle_send(self, message):
        msg_type = message.data["msg_type"]
        pload = message.data["payload"]
        msg = HiveMessage(msg_type, pload)
        if msg_type in [HiveMessageType.BUS,
                        HiveMessageType.PROPAGATE,
                        HiveMessageType.ESCALATE]:
            self.hive.emit(msg)
        elif msg_type == HiveMessageType.BROADCAST:
            # Ignore silently, if a Master is connected to bus it will
            # handle it
            pass
        else:
            LOG.error("Unknown HiveMind protocol msg_type")
            return
        self.bus.emit(message.forward("hive.message.sent"))

    def handle_outgoing_mycroft(self, message=None):
        # forward internal messages to connections if they are the target
        if isinstance(message, dict):
            message = json.dumps(message)
        if isinstance(message, str):
            message = Message.deserialize(message)

        message.context = message.context or {}
        peer = message.context.get("destination")
        if peer and peer == self.bus.peer:
            message.context["source"] = self.node_id
            msg = HiveMessage(HiveMessageType.BUS,
                              source_peer=self.bus.peer,
                              payload=message.serialize())
            self.hive.emit(msg)

    # parsed protocol messages
    def handle_incoming_mycroft(self, message):
        """ HiveMind is sending a mycroft bus message"""
        # you are a slave_connection, just signal it in the bus
        self.bus.emit(message.forward("hive.message.received"))
        # and then actually inject it no questions asked
        # TODO make behaviour configurable
        self.bus.emit(message)
