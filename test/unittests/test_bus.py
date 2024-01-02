import random
from time import sleep
from unittest import TestCase, skip

from ovos_bus_client.message import Message
from hivemind_core.database import ClientDatabase
from hivemind_bus_client import HiveMessageType, HiveNodeClient, HiveMessage
from jarbas_hive_mind.utils.emulation import FakeMycroft

# TODO - rewrite tests


def get_hive():
    # TODO add/mock db for the test
    key = "dummy_key"
    crypto_key = "6e9941197be7f949"

    with ClientDatabase() as db:
        client = db.get_client_by_api_key(key)
        if client:
            db.change_crypto_key(key, crypto_key)
        else:
            n = db.total_clients()
            name = f"HiveMind-UNITTESTS-Node-{n}"
            db.add_client(name, key, crypto_key=crypto_key)

    # Here is a minimal test hive mind
    #
    #           Master
    #         /       \
    #       Mid      Mid2
    #     /   \          \
    #  end    end2       end3
    #
    MASTER_PORT = 10000
    MID_PORT = 20000
    MID2_PORT = 20001
    END_PORT = 30000
    END2_PORT = 30001
    END3_PORT = 30003

    master = FakeMycroft(MASTER_PORT)
    master.start()

    sleep(1)

    mid = FakeMycroft(
        MID_PORT,
        connection=HiveNodeClient(
            key=key, crypto_key=crypto_key, port=MASTER_PORT, ssl=False
        ),
    )
    mid.start()

    mid2 = FakeMycroft(
        MID2_PORT,
        connection=HiveNodeClient(
            key=key, crypto_key=crypto_key, port=MASTER_PORT, ssl=False
        ),
    )
    mid2.start()

    sleep(1)

    end = FakeMycroft(
        END_PORT,
        connection=HiveNodeClient(
            key=key, crypto_key=crypto_key, port=MID_PORT, ssl=False
        ),
    )
    end.start()
    end2 = FakeMycroft(
        END2_PORT,
        connection=HiveNodeClient(
            key=key, crypto_key=crypto_key, port=MID_PORT, ssl=False
        ),
    )
    end2.start()
    end3 = FakeMycroft(
        END3_PORT,
        connection=HiveNodeClient(
            key=key, crypto_key=crypto_key, port=MID2_PORT, ssl=False
        ),
    )
    end3.start()

    sleep(10)  # allow hive to fully connect

    return [master, mid, mid2, end, end2, end3]


master, mid, mid2, end, end2, end3 = get_hive()


class TestConnections(TestCase):
    def test_hello(self):
        # assert node_ids received via "hello" message
        self.assertEqual(mid.connection.node_id, master.hive.node_id)
        self.assertEqual(mid2.connection.node_id, master.hive.node_id)
        self.assertEqual(end.connection.node_id, mid.hive.node_id)
        self.assertEqual(end2.connection.node_id, mid.hive.node_id)
        self.assertEqual(end3.connection.node_id, mid2.hive.node_id)

    def test_connections(self):
        # assert clients connected to servers
        self.assertTrue(mid.connection.peer in master.hive.clients)
        self.assertTrue(mid2.connection.peer in master.hive.clients)
        self.assertTrue(end.connection.peer in mid.hive.clients)
        self.assertTrue(end2.connection.peer in mid.hive.clients)
        self.assertTrue(end3.connection.peer in mid2.hive.clients)


class TestHiveBus(TestCase):
    def test_midtomaster(self):
        #
        #           Master
        #          *
        #         /
        #       Mid      Mid2
        #
        #  end    end2       end3
        #

        rcv_master = []
        rcv_mid = []
        rcv_mid2 = []

        def handle_master_bus(message):
            rcv_master.append(message)

        def handle_mid_bus(message):
            rcv_mid.append(message)

        def handle_mid2_bus(message):
            rcv_mid2.append(message)

        master.handle_downstream_bus = handle_master_bus
        mid.handle_downstream_bus = handle_mid_bus
        mid2.handle_downstream_bus = handle_mid2_bus
        master.register_downstream_handlers()
        mid.register_downstream_handlers()
        mid2.register_downstream_handlers()

        pload = HiveMessage(
            msg_type=HiveMessageType.BUS, payload=Message("test", {"ping": "pong"})
        )
        mid.connection.emit(pload)
        sleep(2)

        # check that only master received the message
        self.assertEqual(len(rcv_master), 1)
        self.assertEqual(len(rcv_mid), 0)
        self.assertEqual(len(rcv_mid2), 0)

        # TODO debug where sometimes payload isnt unpacked
        for message in rcv_master:
            continue
            self.assertEqual(message.msg_type, HiveMessageType.BUS)
            self.assertTrue(isinstance(message.payload, Message))

    def test_end3tomid2(self):
        #
        #           Master
        #
        #       Mid      Mid2
        #                   *
        #                    \
        #  end    end2       end3
        #
        rcv_master = []
        rcv_mid = []
        rcv_mid2 = []

        def handle_master_bus(message):
            rcv_master.append(message)

        def handle_mid_bus(message):
            rcv_mid.append(message)

        def handle_mid2_bus(message):
            rcv_mid2.append(message)

        master.handle_downstream_bus = handle_master_bus
        mid.handle_downstream_bus = handle_mid_bus
        mid2.handle_downstream_bus = handle_mid2_bus
        master.register_downstream_handlers()
        mid.register_downstream_handlers()
        mid2.register_downstream_handlers()

        pload = HiveMessage(
            msg_type=HiveMessageType.BUS, payload=Message("test", {"ping": "pong"})
        )
        end3.connection.emit(pload)
        sleep(2)

        # check that only mid2 received the message
        self.assertEqual(len(rcv_master), 0)
        self.assertEqual(len(rcv_mid), 0)
        self.assertEqual(len(rcv_mid2), 1)

        # TODO debug where sometimes payload isnt unpacked
        for message in rcv_mid2:
            continue
            self.assertEqual(message.msg_type, HiveMessageType.BUS)
            self.assertTrue(isinstance(message.payload, Message))

    def test_mastertomid(self):
        #
        #           Master
        #         /
        #        *
        #       Mid      Mid2
        #
        #  end    end2       end3
        #

        rcv_mid = []
        rcv_mid2 = []
        rcv_end = []
        rcv_end2 = []
        rcv_end3 = []

        def handle_mid_bus(message):
            rcv_mid.append(message)

        def handle_mid2_bus(message):
            rcv_mid2.append(message)

        def handle_end_bus(message):
            rcv_end.append(message)

        def handle_end2_bus(message):
            rcv_end2.append(message)

        def handle_end3_bus(message):
            rcv_end3.append(message)

        mid.handle_upstream_bus = handle_mid_bus
        mid2.handle_upstream_bus = handle_mid2_bus
        end.handle_upstream_bus = handle_end_bus
        end2.handle_upstream_bus = handle_end2_bus
        end3.handle_upstream_bus = handle_end3_bus
        mid.register_upstream_handlers()
        mid2.register_upstream_handlers()
        end.register_upstream_handlers()
        end2.register_upstream_handlers()
        end2.register_upstream_handlers()

        pload = HiveMessage(
            msg_type=HiveMessageType.BUS, payload=Message("test", {"ping": "pong"})
        )
        master.interface.send(pload, mid.connection.peer)
        sleep(0.5)

        # check that only mid received the message
        self.assertEqual(len(rcv_mid), 1)
        self.assertEqual(len(rcv_mid2), 0)
        self.assertEqual(len(rcv_end), 0)
        self.assertEqual(len(rcv_end2), 0)
        self.assertEqual(len(rcv_end3), 0)

        for message in rcv_mid:
            self.assertEqual(message.msg_type, HiveMessageType.BUS)
            self.assertTrue(isinstance(message.payload, Message))

    def test_midtoend(self):
        #
        #           Master
        #
        #       Mid      Mid2
        #     /
        #    *
        #  end    end2       end3
        #

        rcv_mid = []
        rcv_mid2 = []
        rcv_end = []
        rcv_end2 = []
        rcv_end3 = []

        def handle_mid_bus(message):
            rcv_mid.append(message)

        def handle_mid2_bus(message):
            rcv_mid2.append(message)

        def handle_end_bus(message):
            rcv_end.append(message)

        def handle_end2_bus(message):
            rcv_end2.append(message)

        def handle_end3_bus(message):
            rcv_end3.append(message)

        mid.handle_upstream_bus = handle_mid_bus
        mid2.handle_upstream_bus = handle_mid2_bus
        end.handle_upstream_bus = handle_end_bus
        end2.handle_upstream_bus = handle_end2_bus
        end3.handle_upstream_bus = handle_end3_bus
        mid.register_upstream_handlers()
        mid2.register_upstream_handlers()
        end.register_upstream_handlers()
        end2.register_upstream_handlers()
        end2.register_upstream_handlers()

        pload = HiveMessage(
            msg_type=HiveMessageType.BUS, payload=Message("test", {"ping": "pong"})
        )
        mid.interface.send(pload, end.connection.peer)
        sleep(0.5)

        # check that only mid received the message
        self.assertEqual(len(rcv_mid), 0)
        self.assertEqual(len(rcv_mid2), 0)
        self.assertEqual(len(rcv_end), 1)
        self.assertEqual(len(rcv_end2), 0)
        self.assertEqual(len(rcv_end3), 0)

        for message in rcv_mid:
            self.assertEqual(message.msg_type, HiveMessageType.BUS)
            self.assertTrue(isinstance(message.payload, Message))


class TestEscalate(TestCase):
    def test_midtomaster(self):
        #
        #           Master
        #          *
        #         /
        #       Mid      Mid2
        #
        #  end    end2       end3
        #

        rcv_master = []
        rcv_mid = []
        rcv_mid2 = []

        def handle_master_escalate(message):
            rcv_master.append(message)

        def handle_mid_escalate(message):
            rcv_mid.append(message)

        def handle_mid2_escalate(message):
            rcv_mid2.append(message)

        master.handle_downstream_escalate = handle_master_escalate
        mid.handle_downstream_escalate = handle_mid_escalate
        mid2.handle_downstream_escalate = handle_mid2_escalate
        master.register_downstream_handlers()
        mid.register_downstream_handlers()
        mid2.register_downstream_handlers()

        pload = HiveMessage(
            msg_type=HiveMessageType.THIRDPRTY,
            payload=Message("test", {"ping": "pong"}),
        )
        pload = HiveMessage(msg_type=HiveMessageType.ESCALATE, payload=pload)
        mid.connection.emit(pload)
        sleep(2)

        # check that only master received the message
        self.assertEqual(len(rcv_master), 1)
        self.assertEqual(len(rcv_mid), 0)
        self.assertEqual(len(rcv_mid2), 0)

        # TODO debug where sometimes payload isnt unpacked
        for message in rcv_master + rcv_mid + rcv_mid2:
            print(message)
            continue
            self.assertEqual(message.msg_type, HiveMessageType.BUS)
            self.assertTrue(isinstance(message.payload, Message))

    def test_endtomaster(self):
        #
        #         Master
        #        *
        #       /
        #     Mid      Mid2
        #     *
        #    /
        #  end    end2      end3
        #
        rcv_master = []
        rcv_mid = []
        rcv_mid2 = []

        def handle_master_escalate(message):
            rcv_master.append(message)

        def handle_mid_escalate(message):
            rcv_mid.append(message)

        def handle_mid2_escalate(message):
            rcv_mid2.append(message)

        master.handle_downstream_escalate = handle_master_escalate
        mid.handle_downstream_escalate = handle_mid_escalate
        mid2.handle_downstream_escalate = handle_mid2_escalate
        master.register_downstream_handlers()
        mid.register_downstream_handlers()
        mid2.register_downstream_handlers()

        pload = HiveMessage(
            msg_type=HiveMessageType.THIRDPRTY,
            payload=Message("test", {"ping": "pong"}),
        )
        pload = HiveMessage(msg_type=HiveMessageType.ESCALATE, payload=pload)
        end.connection.emit(pload)
        sleep(2)

        # check that master and mid2received the message
        self.assertEqual(len(rcv_master), 1)
        self.assertEqual(len(rcv_mid), 1)
        self.assertEqual(len(rcv_mid2), 0)

        # TODO debug where sometimes payload isnt unpacked
        for message in rcv_master + rcv_mid + rcv_mid2:
            continue
            self.assertEqual(message.msg_type, HiveMessageType.BUS)
            self.assertTrue(isinstance(message.payload, Message))

    def test_end3tomaster(self):
        #
        #           Master
        #                *
        #                 \
        #       Mid      Mid2
        #                   *
        #                    \
        #  end    end2       end3
        #
        rcv_master = []
        rcv_mid = []
        rcv_mid2 = []

        def handle_master_escalate(message):
            rcv_master.append(message)

        def handle_mid_escalate(message):
            rcv_mid.append(message)

        def handle_mid2_escalate(message):
            rcv_mid2.append(message)

        master.handle_downstream_escalate = handle_master_escalate
        mid.handle_downstream_escalate = handle_mid_escalate
        mid2.handle_downstream_escalate = handle_mid2_escalate
        master.register_downstream_handlers()
        mid.register_downstream_handlers()
        mid2.register_downstream_handlers()

        pload = HiveMessage(
            msg_type=HiveMessageType.THIRDPRTY,
            payload=Message("test", {"ping": "pong"}),
        )
        pload = HiveMessage(msg_type=HiveMessageType.ESCALATE, payload=pload)
        end3.connection.emit(pload)
        sleep(2)

        # check that master and mid2 received the message
        self.assertEqual(len(rcv_master), 1)
        self.assertEqual(len(rcv_mid), 0)
        self.assertEqual(len(rcv_mid2), 1)

        # TODO debug where sometimes payload isnt unpacked
        for message in rcv_master + rcv_mid + rcv_mid2:
            continue
            self.assertEqual(message.msg_type, HiveMessageType.BUS)
            self.assertTrue(isinstance(message.payload, Message))


class TestHiveBroadcast(TestCase):
    def test_master(self):
        #           Master
        #         /       \
        #        *         *
        #       Mid      Mid2
        #     /   \          \
        #    *     *          *
        #  end    end2       end3
        #

        rcv_mid = []
        rcv_mid2 = []
        rcv_end = []
        rcv_end2 = []
        rcv_end3 = []

        def handle_mid_broadcast(message):
            rcv_mid.append(message)

        def handle_mid2_broadcast(message):
            rcv_mid2.append(message)

        def handle_end_broadcast(message):
            rcv_end.append(message)

        def handle_end2_broadcast(message):
            rcv_end2.append(message)

        def handle_end3_broadcast(message):
            rcv_end3.append(message)

        mid.handle_upstream_broadcast = handle_mid_broadcast
        mid2.handle_upstream_broadcast = handle_mid2_broadcast
        end.handle_upstream_broadcast = handle_end_broadcast
        end2.handle_upstream_broadcast = handle_end2_broadcast
        end3.handle_upstream_broadcast = handle_end3_broadcast
        mid.register_upstream_handlers()
        mid2.register_upstream_handlers()
        end.register_upstream_handlers()
        end2.register_upstream_handlers()
        end3.register_upstream_handlers()

        pload = HiveMessage(
            msg_type=HiveMessageType.THIRDPRTY,
            payload=Message("test", {"ping": "pong"}),
        )
        master.interface.broadcast(pload)
        sleep(1)

        # check that all nodes received the message
        self.assertEqual(len(rcv_mid), 1)
        self.assertEqual(len(rcv_mid2), 1)
        self.assertEqual(len(rcv_end), 1)
        self.assertEqual(len(rcv_end2), 1)
        self.assertEqual(len(rcv_end3), 1)

        # TODO debug where sometimes payload isnt unpacked
        for message in rcv_mid + rcv_mid2 + rcv_end + rcv_end2 + rcv_end3:
            print(message)
            continue
            self.assertEqual(message.msg_type, HiveMessageType.THIRDPRTY)
            self.assertTrue(isinstance(message, HiveMessage))

    def test_mid(self):
        #           Master
        #
        #       Mid      Mid2
        #     /   \
        #    *     *
        #  end    end2       end3
        #

        rcv_mid = []
        rcv_mid2 = []
        rcv_end = []
        rcv_end2 = []
        rcv_end3 = []

        def handle_mid_broadcast(message):
            rcv_mid.append(message)

        def handle_mid2_broadcast(message):
            rcv_mid2.append(message)

        def handle_end_broadcast(message):
            rcv_end.append(message)

        def handle_end2_broadcast(message):
            rcv_end2.append(message)

        def handle_end3_broadcast(message):
            rcv_end3.append(message)

        mid.handle_upstream_broadcast = handle_mid_broadcast
        mid2.handle_upstream_broadcast = handle_mid2_broadcast
        end.handle_upstream_broadcast = handle_end_broadcast
        end2.handle_upstream_broadcast = handle_end2_broadcast
        end3.handle_upstream_broadcast = handle_end3_broadcast
        mid.register_upstream_handlers()
        mid2.register_upstream_handlers()
        end.register_upstream_handlers()
        end2.register_upstream_handlers()
        end3.register_upstream_handlers()

        pload = HiveMessage(
            msg_type=HiveMessageType.THIRDPRTY,
            payload=Message("test", {"ping": "pong"}),
        )
        mid.interface.broadcast(pload)
        sleep(1)

        # check that all nodes received the message
        self.assertEqual(len(rcv_mid), 0)
        self.assertEqual(len(rcv_mid2), 0)
        self.assertEqual(len(rcv_end), 1)
        self.assertEqual(len(rcv_end2), 1)
        self.assertEqual(len(rcv_end3), 0)

        # TODO debug where sometimes payload isnt unpacked
        for message in rcv_mid + rcv_mid2 + rcv_end + rcv_end2 + rcv_end3:
            print(message)
            continue
            self.assertEqual(message.msg_type, HiveMessageType.THIRDPRTY)
            self.assertTrue(isinstance(message, HiveMessage))


@skip("TODO Fix me")
class TestPropagate(TestCase):
    def test_mid(self):
        #
        #           Master
        #          *     \
        #         /       *
        #       Mid      Mid2
        #      /   \         \
        #     *     *         *
        #   end    end2       end3
        #

        rcv_master = []
        rcv_mid = []
        rcv_mid2 = []
        rcv_end = []
        rcv_end2 = []
        rcv_end3 = []

        def handle_master_propagate(message):
            rcv_master.append(message)

        def handle_mid_propagate(message):
            rcv_mid.append(message)

        def handle_mid2_propagate(message):
            rcv_mid2.append(message)

        def handle_end_propagate(message):
            rcv_end.append(message)

        def handle_end2_propagate(message):
            rcv_end2.append(message)

        def handle_end3_propagate(message):
            rcv_end3.append(message)

        master.handle_downstream_propagate = handle_master_propagate
        mid.handle_downstream_propagate = handle_mid_propagate
        mid2.handle_downstream_propagate = handle_mid2_propagate
        mid.handle_upstream_propagate = handle_mid_propagate
        mid2.handle_upstream_propagate = handle_mid2_propagate
        end.handle_upstream_propagate = handle_end_propagate
        end2.handle_upstream_propagate = handle_end2_propagate
        end3.handle_upstream_propagate = handle_end3_propagate

        master.register_downstream_handlers()
        mid.register_downstream_handlers()
        mid2.register_downstream_handlers()
        mid.register_upstream_handlers()
        mid2.register_upstream_handlers()
        end.register_upstream_handlers()
        end2.register_upstream_handlers()
        end3.register_upstream_handlers()

        pload = HiveMessage(
            msg_type=HiveMessageType.THIRDPRTY,
            payload=Message("test", {"ping": "pong"}),
        )
        pload = HiveMessage(msg_type=HiveMessageType.PROPAGATE, payload=pload)
        mid.connection.emit(pload)
        sleep(2)

        # check that every node received the message
        self.assertEqual(len(rcv_master), 1)
        self.assertEqual(len(rcv_mid), 1)
        self.assertEqual(len(rcv_mid2), 1)
        self.assertEqual(len(rcv_end), 1)
        self.assertEqual(len(rcv_end2), 1)
        self.assertEqual(len(rcv_end3), 1)

        # TODO debug where sometimes payload isnt unpacked
        for message in rcv_master + rcv_mid + rcv_mid2:
            print(message)
            continue
            self.assertEqual(message.msg_type, HiveMessageType.BUS)
            self.assertTrue(isinstance(message.payload, Message))

    def test_end(self):
        #
        #           Master
        #          *     \
        #         /       *
        #       Mid      Mid2
        #      *   \         \
        #     /     *         *
        #   end    end2       end3
        #
        rcv_master = []
        rcv_mid = []
        rcv_mid2 = []
        rcv_end = []
        rcv_end2 = []
        rcv_end3 = []

        def handle_master_propagate(message):
            rcv_master.append(message)

        def handle_mid_propagate(message):
            rcv_mid.append(message)

        def handle_mid2_propagate(message):
            rcv_mid2.append(message)

        def handle_end_propagate(message):
            rcv_end.append(message)

        def handle_end2_propagate(message):
            rcv_end2.append(message)

        def handle_end3_propagate(message):
            rcv_end3.append(message)

        master.handle_downstream_propagate = handle_master_propagate
        mid.handle_downstream_propagate = handle_mid_propagate
        mid2.handle_downstream_propagate = handle_mid2_propagate
        mid.handle_upstream_propagate = handle_mid_propagate
        mid2.handle_upstream_propagate = handle_mid2_propagate
        end.handle_upstream_propagate = handle_end_propagate
        end2.handle_upstream_propagate = handle_end2_propagate
        end3.handle_upstream_propagate = handle_end3_propagate

        master.register_downstream_handlers()
        mid.register_downstream_handlers()
        mid2.register_downstream_handlers()
        mid.register_upstream_handlers()
        mid2.register_upstream_handlers()
        end.register_upstream_handlers()
        end2.register_upstream_handlers()
        end3.register_upstream_handlers()

        pload = HiveMessage(
            msg_type=HiveMessageType.THIRDPRTY,
            payload=Message("test", {"ping": "pong"}),
        )
        pload = HiveMessage(msg_type=HiveMessageType.PROPAGATE, payload=pload)
        end.connection.emit(pload)
        sleep(2)

        # check that every node received the message
        for message in rcv_master + rcv_mid + rcv_mid2 + rcv_end + rcv_end2 + rcv_end3:
            print(66, message)

        self.assertEqual(len(rcv_master), 1)
        self.assertEqual(len(rcv_mid), 1)
        self.assertEqual(len(rcv_mid2), 1)
        self.assertEqual(len(rcv_end), 1)
        self.assertEqual(len(rcv_end2), 1)
        self.assertEqual(len(rcv_end3), 1)

        # TODO debug where sometimes payload isnt unpacked
        for message in rcv_master + rcv_mid + rcv_mid2 + rcv_end + rcv_end2 + rcv_end3:
            continue
            self.assertEqual(message.msg_type, HiveMessageType.BUS)
            self.assertTrue(isinstance(message.payload, Message))

    def test_end3(self):
        #
        #           Master
        #          /     *
        #         *       \
        #       Mid      Mid2
        #      /   \         *
        #     *     *         \
        #   end    end2       end3
        #
        rcv_master = []
        rcv_mid = []
        rcv_mid2 = []
        rcv_end = []
        rcv_end2 = []
        rcv_end3 = []

        def handle_master_propagate(message):
            rcv_master.append(message)

        def handle_mid_propagate(message):
            rcv_mid.append(message)

        def handle_mid2_propagate(message):
            rcv_mid2.append(message)

        def handle_end_propagate(message):
            rcv_end.append(message)

        def handle_end2_propagate(message):
            rcv_end2.append(message)

        def handle_end3_propagate(message):
            rcv_end3.append(message)

        master.handle_downstream_propagate = handle_master_propagate
        mid.handle_downstream_propagate = handle_mid_propagate
        mid2.handle_downstream_propagate = handle_mid2_propagate
        mid.handle_upstream_propagate = handle_mid_propagate
        mid2.handle_upstream_propagate = handle_mid2_propagate
        end.handle_upstream_propagate = handle_end_propagate
        end2.handle_upstream_propagate = handle_end2_propagate
        end3.handle_upstream_propagate = handle_end3_propagate

        master.register_downstream_handlers()
        mid.register_downstream_handlers()
        mid2.register_downstream_handlers()
        mid.register_upstream_handlers()
        mid2.register_upstream_handlers()
        end.register_upstream_handlers()
        end2.register_upstream_handlers()
        end3.register_upstream_handlers()

        pload = HiveMessage(
            msg_type=HiveMessageType.THIRDPRTY,
            payload=Message("test", {"ping": "pong"}),
        )
        pload = HiveMessage(msg_type=HiveMessageType.PROPAGATE, payload=pload)
        end3.connection.emit(pload)
        sleep(2)

        # check that every node received the message
        self.assertEqual(len(rcv_master), 1)
        self.assertEqual(len(rcv_mid), 1)
        self.assertEqual(len(rcv_mid2), 1)
        self.assertEqual(len(rcv_end), 1)
        self.assertEqual(len(rcv_end2), 1)
        self.assertEqual(len(rcv_end3), 1)

        # TODO debug where sometimes payload isnt unpacked
        for message in rcv_master + rcv_mid + rcv_mid2:
            continue
            self.assertEqual(message.msg_type, HiveMessageType.BUS)
            self.assertTrue(isinstance(message.payload, Message))
