import json
from threading import Thread

from ovos_utils.log import LOG
from ovos_utils.messagebus import Message

from hivemind_bus_client import HiveMessage, \
    HiveMessageType
from hivemind_bus_client.util import get_mycroft_msg
from jarbas_hive_mind.message import HiveMessage, HiveMessageType
from jarbas_hive_mind.nodes import HiveMindNodeType


class HiveMindTerminal(Thread):
    platform = "HiveMindTerminalV0.3"
    node_type = HiveMindNodeType.TERMINAL

    def __init__(self, connection=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hive = connection
        if connection:
            self._register_hivemind_handlers()
        self.upnp_server = None
        self.ssdp = None

    def bind(self, hive):
        self.hive = hive
        self._register_hivemind_handlers()

    def _register_hivemind_handlers(self):
        self.hive.on(HiveMessageType.BUS, self.handle_bus_message)
        self.hive.on(HiveMessageType.ESCALATE, self.handle_escalate_message)
        self.hive.on(HiveMessageType.PROPAGATE, self.handle_propagate_message)
        self.hive.on(HiveMessageType.BROADCAST, self.handle_broadcast_message)

    @property
    def node_id(self):
        """ semi-unique session id, only meaningful for the master the node is
        connected to, other hive nodes do not know what node this is,
        only the master recognizes this uid """
        if not self.hive:
            # not yet connected
            return f"{self.__class__.__name__}" \
                   f".{HiveMindNodeType.CANDIDATE_NODE}:{self.node_type}"
        return f"{self.hive.useragent}:{self.node_type}"

    def run(self) -> None:
        if not self.hive.started_running:
            self.hive.run_forever()

    # parsed protocol messages
    def handle_incoming_mycroft(self, message):
        assert isinstance(message, Message)
        LOG.debug("[Mycroft Message] " + message.serialize())

    # HiveMind protocol messages - from UPstream
    def handle_bus_message(self, hmessage):
        # Generate mycroft Message object
        message = get_mycroft_msg(hmessage)
        assert isinstance(message, Message)
        message.context["source"] = self.node_id
        message.context["destination"] = "skills"
        if "platform" not in message.context:
            message.context["platform"] = self.platform
        self.handle_incoming_mycroft(message)

    def handle_propagate_message(self, hmessage):
        LOG.info("Received propagate message at: " + self.node_id)
        LOG.debug("ROUTE: " + str(hmessage.route))
        LOG.debug("PAYLOAD: " + str(hmessage.payload))

    def handle_broadcast_message(self, hmessage):
        LOG.info("Received broadcast message at: " + self.node_id)
        LOG.debug("ROUTE: " + str(hmessage.route))
        LOG.debug("PAYLOAD: " + str(hmessage.payload))

    def handle_escalate_message(self, hmessage):
        # only Slaves are allowed to escalate, by definition escalate
        # goes upstream only
        LOG.debug("Ignoring escalate message from upstream, illegal action")


