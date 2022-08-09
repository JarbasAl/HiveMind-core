from ovos_utils.messagebus import FakeBus

from hivemind_bus_client import HiveNodeClient
from jarbas_hive_mind.nodes.slave import HiveMindSlave


def connect_to_hivemind(key, host="ws://0.0.0.0", port=5678,
                        name="JarbasDroneV0.3", crypto_key=None, bus=None):
    hive = HiveNodeClient(key, bus, crypto_key=crypto_key, useragent=name,
                          port=port, host=host,  self_signed=False)

    slave = HiveMindSlave(connection=hive)
    slave.start()


if __name__ == '__main__':
    # TODO arg parse
    key = "RESISTENCEisFUTILE"
    crypto_key = "resistanceISfutile"
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
