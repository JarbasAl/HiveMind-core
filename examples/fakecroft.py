from hivemind_bus_client.message import HiveMessage, HiveMessageType
from ovos_bus_client.message import Message
from ovos_utils.log import LOG
from ovos_utils.messagebus import FakeBus
from hivemind_listener.service import MessageBusEventHandler
from hivemind_listener.protocol import (
    HiveMindListenerProtocol,
    HiveMindListenerInternalProtocol,
    HiveMindClientConnection,
)


class HiveMindFakeCroftProtocol(HiveMindListenerProtocol):
    """Fake ovos-core instance, not actually connected to a messagebus"""

    peer: str = "fakecroft:0.0.0.0"

    def bind(self, websocket, bus=None):
        websocket.protocol = self
        if bus is None:
            bus = FakeBus()
        self.internal_protocol = HiveMindListenerInternalProtocol(bus)

    def handle_incoming_mycroft(
        self, message: Message, client: HiveMindClientConnection
    ):
        """
        message (Message): mycroft bus message object
        """
        super().handle_inject_mycroft_msg(message, client)
        answer = "mycroft is dead! long live mycroft!"

        payload = HiveMessage(
            HiveMessageType.BUS, message.reply("speak", {"utterance": answer})
        )
        client.send(payload)


def on_ready():
    LOG.info("FakeCroft started!")


def on_error(e="Unknown"):
    LOG.info("FakeCroft failed to start ({})".format(repr(e)))


def on_stopping():
    LOG.info("FakeCroft is shutting down...")


def main(ready_hook=on_ready, error_hook=on_error, stopping_hook=on_stopping):
    from ovos_utils import create_daemon, wait_for_exit_signal
    from tornado import web, ioloop
    from ovos_config import Configuration

    LOG.info("Starting FakeCroft...")

    try:
        websocket_configs = Configuration()["websocket"]
    except KeyError as ke:
        LOG.error("No websocket configs found ({})".format(repr(ke)))
        raise

    host = websocket_configs.get("host")
    port = websocket_configs.get("port")
    route = websocket_configs.get("route")
    port = 5678
    route = "/"

    # TODO - protocol from config / argparse
    protocol = HiveMindFakeCroftProtocol()
    protocol.bind(MessageBusEventHandler)

    routes = [(route, MessageBusEventHandler)]
    application = web.Application(routes)
    application.listen(port, host)
    create_daemon(ioloop.IOLoop.instance().start)
    ready_hook()
    wait_for_exit_signal()
    stopping_hook()


if __name__ == "__main__":
    main()
