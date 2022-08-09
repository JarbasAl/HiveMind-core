from hivemind_bus_client.client import HiveNodeClient
from jarbas_hive_mind.nodes import HiveMindNodeType
from jarbas_hive_mind.nodes.terminal import HiveMindTerminal


class HiveMindSlave(HiveMindTerminal):
    node_type = HiveMindNodeType.SLAVE

    def __init__(self, connection, *args, **kwargs):
        # TODO log error and solution
        assert isinstance(connection, HiveNodeClient)
        assert connection.bus is not None
        super().__init__(connection, *args, **kwargs)

    @property
    def share_bus(self):
        return self.hive.share_bus

    @share_bus.setter
    def share_bus(self, val):
        self.hive.share_bus = bool(val)

    @property
    def bus(self):
        return self.hive.bus
