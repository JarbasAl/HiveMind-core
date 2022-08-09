from threading import Thread
import asyncio
from hivemind_bus_client import HiveMessageBusClient, HiveMessage, \
    HiveMessageType, HiveNodeClient
from ovos_utils.messagebus import FakeBus

from jarbas_hive_mind.configuration import CONFIGURATION
from jarbas_hive_mind.server import HiveMindWebsocketServer


class FakeMycroft(Thread):

    def __init__(self, port, connection=None, bus=None, config=None):
        daemon = True
        super().__init__(daemon=daemon)
        self.loop = None
        self.bus = bus or FakeBus()
        self.config = config or CONFIGURATION
        self.port = port
        self.user_agent = f"fakeCroft:{self.port}"
        # hive mind objects
        self.connection = None
        self._master_thread = None
        self.hive = None
        self.server = None
        if connection:
            self.bind_master(connection)

    def bind_master(self, connection):
        self.connection = connection
        if isinstance(self.connection, HiveNodeClient):
            self.connection.bind(self.bus)
        self.register_upstream_handlers()

    def register_upstream_handlers(self):
        self.connection.on(HiveMessageType.BUS,
                           self.handle_upstream_bus)
        self.connection.on(HiveMessageType.ESCALATE,
                           self.handle_upstream_escalate)
        self.connection.on(HiveMessageType.PROPAGATE,
                           self.handle_upstream_propagate)
        self.connection.on(HiveMessageType.BROADCAST,
                           self.handle_upstream_broadcast)

    def register_downstream_handlers(self):
        self.hive.on_escalate = self.handle_downstream_escalate
        self.hive.on_propagate = self.handle_downstream_propagate
        self.hive.on_broadcast = self.handle_downstream_broadcast
        self.hive.on_bus = self.handle_downstream_bus
        
    def handle_upstream_escalate(self, msg):
        pass  # should not happen !

    def handle_upstream_propagate(self, msg):
        pass

    def handle_upstream_broadcast(self, msg):
        pass

    def handle_upstream_bus(self, msg):
        pass

    def handle_downstream_escalate(self, msg):
        pass

    def handle_downstream_propagate(self, msg):
        pass

    def handle_downstream_broadcast(self, msg):
        pass  # should not happen !

    def handle_downstream_bus(self, msg):
        pass

    def _set_event_loop(self, loop=None):
        self.loop = loop or asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        return self.loop

    @property
    def interface(self):
        if self.hive:
            return self.hive.interface

    def start_listener(self):
        # listen
        self.server = HiveMindWebsocketServer(self.port, bus=self.bus)
        # this flag is not meant for the end user
        # used here so the event loop can be started manually
        self.server._autorun = False

        # share the event loop so we can run in a thread
        if self.loop is None:
            self._set_event_loop()
        self.server._set_event_loop(self.loop)

        # returns a HiveMind object
        self.hive = self.server.listen()
        self.register_downstream_handlers()

    def run(self):
        if self.loop is None:
            self._set_event_loop()
        if self.connection:
            if not self.connection.started_running:
                self._master_thread = self.connection.run_in_thread()
        if not self.server:
            self.start_listener()
            self.server.run()

    def stop(self):
        if self.server:
            self.server.stop()
        if self._master_thread:
            if self.connection:
                self.connection.close()
            self._master_thread.join()

