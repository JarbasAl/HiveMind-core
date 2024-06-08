from functools import wraps
from typing import List, Dict, Union, Any, Optional, Iterable


def cast_to_client_obj():
    valid_kwargs: Iterable[str] = (
        "client_id",
        "api_key",
        "name",
        "description",
        "is_admin",
        "last_seen",
        "blacklist",
        "allowed_types",
        "crypto_key",
        "password",
        "can_broadcast",
        "can_escalate",
        "can_propagate",
    )

    def _handler(func):
        def _cast(ret):
            if ret is None or isinstance(ret, Client):
                return ret
            if isinstance(ret, list):
                return [_cast(r) for r in ret]
            if isinstance(ret, dict):
                if not all((k in valid_kwargs for k in ret.keys())):
                    raise RuntimeError(f"{func} returned a dict with unknown keys")
                return Client(**ret)

            raise TypeError(
                "cast_to_client_obj decorator can only be used in functions that return None, dict, Client or a list of those types"
            )

        @wraps(func)
        def call_function(*args, **kwargs):
            ret = func(*args, **kwargs)
            return _cast(ret)

        return call_function

    return _handler


class Client:
    def __init__(
        self,
        client_id: int,
        api_key: str,
        name: str = "",
        description: str = "",
        is_admin: bool = False,
        last_seen: float = -1,
        blacklist: Optional[Dict[str, List[str]]] = None,
        allowed_types: Optional[List[str]] = None,
        crypto_key: Optional[str] = None,
        password: Optional[str] = None,
        can_broadcast: bool = True,
        can_escalate: bool = True,
        can_propagate: bool = True,
    ):
        self.client_id = client_id
        self.description = description
        self.api_key = api_key
        self.name = name
        self.last_seen = last_seen
        self.is_admin = is_admin
        self.crypto_key = crypto_key
        self.password = password
        self.blacklist = blacklist or {"messages": [], "skills": [], "intents": []}
        self.allowed_types = allowed_types or [
            "recognizer_loop:utterance",
            "recognizer_loop:record_begin",
            "recognizer_loop:record_end",
            "recognizer_loop:audio_output_start",
            "recognizer_loop:audio_output_end",
        ]
        if "recognizer_loop:utterance" not in self.allowed_types:
            self.allowed_types.append("recognizer_loop:utterance")
        self.can_broadcast = can_broadcast
        self.can_escalate = can_escalate
        self.can_propagate = can_propagate

    def __getitem__(self, item: str) -> Any:
        return self.__dict__.get(item)

    def __setitem__(self, key: str, value: Any):
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            raise ValueError("unknown property")

    def __eq__(self, other: Union[object, dict]) -> bool:
        if not isinstance(other, dict):
            other = other.__dict__
        if self.__dict__ == other:
            return True
        return False

    def __repr__(self) -> str:
        return str(self.__dict__)
