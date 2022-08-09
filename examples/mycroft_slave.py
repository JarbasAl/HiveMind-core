from ovos_utils.messagebus import FakeBus

from hivemind_bus_client import HiveMessageBusClient
from jarbas_hive_mind.nodes.slave import HiveMindSlave


def connect_to_hivemind(key, host="ws://0.0.0.0", port=10000,
                        name="JarbasDroneV0.3", crypto_key=None, bus=None):
    if host.startswith("wss://"):
        ssl = True
        host = host.split("ws://")[-1]
    else:
        ssl = False
        host = host.split("wss://")[-1]

    hive = HiveMessageBusClient(key, crypto_key=crypto_key, ssl=ssl,
                                port=port, host=host, useragent=name)

    slave = HiveMindSlave(bus=bus, connection=hive)
    slave.start()


if __name__ == '__main__':
    # TODO arg parse
    key = "dummy_key"
    crypto_key = "6e9941197be7f949"
    bus = FakeBus()

    connect_to_hivemind(key=key, crypto_key=crypto_key, bus=bus)

    # That's it, now the hive mind can send messages to the mycroft bus

    # you can react to hive mind events
    # NOTE the payload from hive mind is also sent directly to the messagebus
    # "hive.mind.connected"
    # "hive.mind.websocket.open"
    # "hive.mind.connection.closed"
    # "hive.mind.message.received"
    # "hive.mind.message.sent"

    # you can send messages to the mycroft bus to send to the HiveMind
    # for example to interact with a skill
    # 'Message("hive.mind.message.send",
    #           {"payload":
    #               {"msg_type": "sensor.data",
    #               "data": {"status": "off"}
    #           })
