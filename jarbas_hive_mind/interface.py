from hivemind_bus_client.util import serialize_message, payload2dict, get_hivemsg
from jarbas_hive_mind.message import HiveMessage, HiveMessageType
from ovos_utils.messagebus import Message


from functools import wraps


def cast_to_hivemessage():
    # TODO improve this and make more generic
    #  currently tied to HiveMindMasterInterface class

    def _handler(func):

        @wraps(func)
        def call_function(*args, **kwargs):
            if "message" in kwargs:
                kwargs["message"] = get_hivemsg(kwargs["message"])
            elif len(args) == 1:
                args = (get_hivemsg(args[0]))
            return func(*args, **kwargs)

        return call_function

    return _handler


class HiveMindMasterInterface:
    def __init__(self, listener):
        self.listener = listener

    @property
    def peer(self):
        return self.listener.peer

    @property
    def clients(self):
        return [c["instance"] for c in
                self.listener.clients.values()]

    @property
    def node_id(self):
        return self.listener.node_id

    @property
    def bus(self):
        return self.listener.bus

    def send(self, payload, client):
        payload = serialize_message(payload)
        if isinstance(client, str):
            client = self.listener.clients[client]["instance"]
        if not isinstance(payload, bytes):
            payload = bytes(payload, encoding="utf-8")

        client.sendMessage(payload)

    def send_to_many(self, payload, no_send=None):
        no_send = no_send or []
        payload["route"] = payload["route"] or []
        route_data = {"source": self.peer,
                      "targets": [c.peer for c in self.clients]}
        # No resend
        if route_data in payload["route"]:
            return

        payload["route"].append(route_data)

        for client in self.clients:
            if client.peer not in no_send:
                self.send(payload, client)

    @cast_to_hivemessage()
    def broadcast(self, message):
        payload = {"msg_type": HiveMessageType.BROADCAST,
                   "payload": message,
                   "route": message.route,
                   "source_peer": self.peer,
                   "node": self.node_id
                   }
        self.send_to_many(payload)

    @cast_to_hivemessage()
    def propagate(self, message):
        payload = {"msg_type": HiveMessageType.PROPAGATE,
                   "payload": message,
                   "route": message.route,
                   "source_peer": self.peer,
                   "node": self.node_id
                   }

        # send downstream to any nodes who didn't get the message yet
        no_send = [n["source"] for n in message.route]
        self.send_to_many(payload, no_send)

        # tell slaves connected to bus to propagate upstream
        if self.bus and message.source_peer != self.peer:
            payload = payload2dict(payload)
            message = Message("hive.send.upstream", payload,
                              {"destination": "hive",
                               "node": self.node_id,
                               "source": self.peer})
            self.bus.emit(message)

    @cast_to_hivemessage()
    def escalate(self, message):
        payload = {"msg_type": HiveMessageType.ESCALATE,
                   "payload": message,
                   "route": message.route,
                   "source_peer": self.peer,
                   "node": self.node_id
                   }
        # tell slaves connected to bus to escalate upstream
        if self.bus and message.source_peer != self.peer:
            payload = payload2dict(payload)
            message = Message("hive.send.upstream", payload,
                              {"destination": "hive",
                               "source": self.peer})
            self.bus.emit(message)

    def query(self, payload, msg_data=None):
        raise NotImplementedError

    def cascade(self, payload, msg_data=None):
        raise NotImplementedError

