import abc
import json
import os.path
from dataclasses import dataclass, field
from typing import List, Dict, Union, Any, Optional, Iterable

from json_database import JsonStorageXDG
from ovos_utils.log import LOG
from ovos_utils.xdg_utils import xdg_data_home

try:
    import redis
except ImportError:
    redis = None

try:
    import sqlite3
except ImportError:
    sqlite3 = None

ClientDict = Dict[str, Union[str, int, float, List[str]]]
ClientTypes = Union[None, 'Client',
                    str,  # json
                    ClientDict,  # dict
                    List[Union[str, ClientDict, 'Client']]  # list of dicts/json/Client
                ]


def cast2client(ret: ClientTypes) -> Optional[Union['Client', List['Client']]]:
    """
    Convert different input types (str, dict, list) to Client instances.

    Args:
        ret: The object to be cast, can be a string, dictionary, or list.

    Returns:
        A single Client instance or a list of Clients if ret is a list.
    """
    if ret is None or isinstance(ret, Client):
        return ret
    if isinstance(ret, str) or isinstance(ret, dict):
        return Client.deserialize(ret)
    if isinstance(ret, list):
        return [cast2client(r) for r in ret]
    raise TypeError("not a client object")


@dataclass
class Client:
    client_id: int
    api_key: str
    name: str = ""
    description: str = ""
    is_admin: bool = False
    last_seen: float = -1
    intent_blacklist: List[str] = field(default_factory=list)
    skill_blacklist: List[str] = field(default_factory=list)
    message_blacklist: List[str] = field(default_factory=list)
    allowed_types: List[str] = field(default_factory=list)
    crypto_key: Optional[str] = None
    password: Optional[str] = None
    can_broadcast: bool = True
    can_escalate: bool = True
    can_propagate: bool = True

    def __post_init__(self):
        """
        Initializes the allowed types for the Client instance if not provided.
        """
        if not isinstance(self.client_id, int):
            raise ValueError("client_id should be an integer")
        if not isinstance(self.is_admin, bool):
            raise ValueError("is_admin should be a boolean")
        self.allowed_types = self.allowed_types or ["recognizer_loop:utterance",
                                                    "recognizer_loop:record_begin",
                                                    "recognizer_loop:record_end",
                                                    "recognizer_loop:audio_output_start",
                                                    "recognizer_loop:audio_output_end",
                                                    'recognizer_loop:b64_transcribe',
                                                    'speak:b64_audio',
                                                    "ovos.common_play.SEI.get.response"]
        if "recognizer_loop:utterance" not in self.allowed_types:
            self.allowed_types.append("recognizer_loop:utterance")

    def serialize(self) -> str:
        """
        Serializes the Client instance into a JSON string.

        Returns:
            A JSON string representing the client data.
        """
        return json.dumps(self.__dict__, sort_keys=True, ensure_ascii=False)

    @staticmethod
    def deserialize(client_data: Union[str, Dict]) -> 'Client':
        """
        Deserialize a client from JSON string or dictionary into a Client instance.

        Args:
            client_data: The data to be deserialized, either a string or dictionary.

        Returns:
            A Client instance.
        """
        if isinstance(client_data, str):
            client_data = json.loads(client_data)
        # TODO filter kwargs with inspect
        return Client(**client_data)

    def __getitem__(self, item: str) -> Any:
        """
        Access attributes of the client via item access.

        Args:
            item: The name of the attribute.

        Returns:
            The value of the attribute.

        Raises:
            KeyError: If the attribute does not exist.
        """
        if hasattr(self, item):
            return getattr(self, item)
        raise KeyError(f"Unknown key: {item}")

    def __setitem__(self, key: str, value: Any):
        """
        Set attributes of the client via item access.

        Args:
            key: The name of the attribute.
            value: The value to set.

        Raises:
            ValueError: If the attribute does not exist.
        """
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            raise ValueError(f"Unknown property: {key}")

    def __eq__(self, other: Any) -> bool:
        """
        Compares two Client instances for equality based on their serialized data.

        Args:
            other: The other Client or Client-compatible object to compare with.

        Returns:
            True if the clients are equal, False otherwise.
        """
        try:
            other = cast2client(other)
        except:
            pass
        if isinstance(other, Client):
            return self.serialize() == other.serialize()
        return False

    def __repr__(self) -> str:
        """
        Returns a string representation of the Client instance.

        Returns:
            A string representing the client.
        """
        return self.serialize()


class AbstractDB(abc.ABC):
    """
    Abstract base class for all database implementations.

    All database implementations should derive from this class and implement
    the abstract methods.
    """

    @abc.abstractmethod
    def add_item(self, client: Client) -> bool:
        """
        Add a client to the database.

        Args:
            client: The client to be added.

        Returns:
            True if the addition was successful, False otherwise.
        """
        pass

    def delete_item(self, client: Client) -> bool:
        """
        Delete a client from the database.

        Args:
            client: The client to be deleted.

        Returns:
            True if the deletion was successful, False otherwise.
        """
        # leave the deleted entry in db, do not allow reuse of client_id !
        client = Client(client_id=client.client_id, api_key="revoked")
        return self.update_item(client)

    def update_item(self, client: Client) -> bool:
        """
        Update an existing client in the database.

        Args:
            client: The client to be updated.

        Returns:
            True if the update was successful, False otherwise.
        """
        return self.add_item(client)

    def replace_item(self, old_client: Client, new_client: Client) -> bool:
        """
        Replace an old client with a new client.

        Args:
            old_client: The old client to be replaced.
            new_client: The new client to add.

        Returns:
            True if the replacement was successful, False otherwise.
        """
        self.delete_item(old_client)
        return self.add_item(new_client)

    @abc.abstractmethod
    def search_by_value(self, key: str, val: Union[str, bool, int, float]) -> List[Client]:
        """
        Search for clients by a specific key-value pair.

        Args:
            key: The key to search by.
            val: The value to search for.

        Returns:
            A list of clients that match the search criteria.
        """
        pass

    @abc.abstractmethod
    def __len__(self) -> int:
        """
        Get the number of items in the database.

        Returns:
            The number of items in the database.
        """
        return 0

    @abc.abstractmethod
    def __iter__(self) -> Iterable['Client']:
        """
        Iterate over all clients in the database.

        Returns:
            An iterator over the clients in the database.
        """
        pass

    def commit(self) -> bool:
        """
        Commit changes to the database.

        Returns:
            True if the commit was successful, False otherwise.
        """
        return True


class JsonDB(AbstractDB):
    """Database implementation using JSON files."""

    def __init__(self, name="clients", subfolder="hivemind-core"):
        self._db: Dict[int, ClientDict] = JsonStorageXDG(name, subfolder=subfolder, xdg_folder=xdg_data_home())
        LOG.debug(f"json database path: {self._db.path}")

    def add_item(self, client: Client) -> bool:
        """
        Add a client to the JSON database.

        Args:
            client: The client to be added.

        Returns:
            True if the addition was successful, False otherwise.
        """
        self._db[client.client_id] = client.__dict__
        return True

    def search_by_value(self, key: str, val: Union[str, bool, int, float]) -> List[Client]:
        """
        Search for clients by a specific key-value pair in the JSON database.

        Args:
            key: The key to search by.
            val: The value to search for.

        Returns:
            A list of clients that match the search criteria.
        """
        res = []
        if key == "client_id":
            v = self._db.get(val)
            if v:
                res.append(cast2client(v))
        else:
            for client in self._db.values():
                v = client.get(key)
                if v == val:
                    res.append(cast2client(client))
        return res

    def __len__(self) -> int:
        """
        Get the number of clients in the database.

        Returns:
            The number of clients in the database.
        """
        return len(self._db)

    def __iter__(self) -> Iterable['Client']:
        """
        Iterate over all clients in the JSON database.

        Returns:
            An iterator over the clients in the database.
        """
        for item in self._db.values():
            yield Client.deserialize(item)

    def commit(self) -> bool:
        """
        Commit changes to the JSON database.

        Returns:
            True if the commit was successful, False otherwise.
        """
        try:
            self._db.store()
            return True
        except Exception as e:
            LOG.error(f"Failed to save {self._db.path}")
            return False


class SQLiteDB(AbstractDB):
    """Database implementation using SQLite."""

    def __init__(self, name="clients", subfolder="hivemind-core"):
        """
        Initialize the SQLiteDB connection.
        """
        if sqlite3 is None:
            raise ImportError("pip install sqlite3")
        db_path = os.path.join(xdg_data_home(), subfolder, name + ".db")
        LOG.debug(f"sqlite database path: {db_path}")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._initialize_database()

    def _initialize_database(self):
        """Initialize the database schema."""
        with self.conn:
            # crypto key is always 16 chars
            # name description and api_key shouldnt be allowed to go over 255
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS clients (
                    client_id INTEGER PRIMARY KEY,
                    api_key VARCHAR(255) NOT NULL,
                    name VARCHAR(255),
                    description VARCHAR(255),
                    is_admin BOOLEAN DEFAULT FALSE,
                    last_seen REAL DEFAULT -1,
                    intent_blacklist TEXT,
                    skill_blacklist TEXT,
                    message_blacklist TEXT,
                    allowed_types TEXT,
                    crypto_key VARCHAR(16),
                    password TEXT,
                    can_broadcast BOOLEAN DEFAULT TRUE,
                    can_escalate BOOLEAN DEFAULT TRUE,
                    can_propagate BOOLEAN DEFAULT TRUE
                )
            """)

    def add_item(self, client: Client) -> bool:
        """
        Add a client to the SQLite database.

        Args:
            client: The client to be added.

        Returns:
            True if the addition was successful, False otherwise.
        """
        try:
            with self.conn:
                self.conn.execute("""
                    INSERT OR REPLACE INTO clients (
                        client_id, api_key, name, description, is_admin,
                        last_seen, intent_blacklist, skill_blacklist,
                        message_blacklist, allowed_types, crypto_key, password,
                        can_broadcast, can_escalate, can_propagate
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    client.client_id, client.api_key, client.name, client.description,
                    client.is_admin, client.last_seen,
                    json.dumps(client.intent_blacklist),
                    json.dumps(client.skill_blacklist),
                    json.dumps(client.message_blacklist),
                    json.dumps(client.allowed_types),
                    client.crypto_key, client.password,
                    client.can_broadcast, client.can_escalate, client.can_propagate
                ))
            return True
        except sqlite3.Error as e:
            LOG.error(f"Failed to add client to SQLite: {e}")
            return False

    def search_by_value(self, key: str, val: Union[str, bool, int, float]) -> List[Client]:
        """
        Search for clients by a specific key-value pair in the SQLite database.

        Args:
            key: The key to search by.
            val: The value to search for.

        Returns:
            A list of clients that match the search criteria.
        """
        try:
            with self.conn:
                cur = self.conn.execute(f"SELECT * FROM clients WHERE {key} = ?", (val,))
                rows = cur.fetchall()
                return [self._row_to_client(row) for row in rows]
        except sqlite3.Error as e:
            LOG.error(f"Failed to search clients in SQLite: {e}")
            return []

    def __len__(self) -> int:
        """Get the number of clients in the database."""
        cur = self.conn.execute("SELECT COUNT(*) FROM clients")
        return cur.fetchone()[0]

    def __iter__(self) -> Iterable['Client']:
        """
        Iterate over all clients in the SQLite database.

        Returns:
            An iterator over the clients in the database.
        """
        cur = self.conn.execute("SELECT * FROM clients")
        for row in cur:
            yield self._row_to_client(row)

    def commit(self) -> bool:
        """Commit changes to the SQLite database."""
        try:
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            LOG.error(f"Failed to commit SQLite database: {e}")
            return False

    @staticmethod
    def _row_to_client(row: sqlite3.Row) -> Client:
        """Convert a database row to a Client instance."""
        return Client(
            client_id=int(row["client_id"]),
            api_key=row["api_key"],
            name=row["name"],
            description=row["description"],
            is_admin=row["is_admin"] or False,
            last_seen=row["last_seen"],
            intent_blacklist=json.loads(row["intent_blacklist"] or "[]"),
            skill_blacklist=json.loads(row["skill_blacklist"] or "[]"),
            message_blacklist=json.loads(row["message_blacklist"] or "[]"),
            allowed_types=json.loads(row["allowed_types"] or "[]"),
            crypto_key=row["crypto_key"],
            password=row["password"],
            can_broadcast=row["can_broadcast"],
            can_escalate=row["can_escalate"],
            can_propagate=row["can_propagate"]
        )


class RedisDB(AbstractDB):
    """Database implementation using Redis with RediSearch support."""

    def __init__(self, host: str = "127.0.0.1", port: int = 6379, password: Optional[str] = None, redis_db: int = 0):
        """
        Initialize the RedisDB connection.

        Args:
            host: Redis server host.
            port: Redis server port.
            redis_db: Redis database index.
        """
        if redis is None:
            raise ImportError("pip install redis")
        self.redis = redis.StrictRedis(host=host, port=port, db=redis_db,
                                       password=password if password else None,
                                       decode_responses=True)
        # TODO - support for a proper search index

    def add_item(self, client: Client) -> bool:
        """
        Add a client to Redis and RediSearch.

        Args:
            client: The client to be added.

        Returns:
            True if the addition was successful, False otherwise.
        """
        item_key = f"client:{client.client_id}"
        serialized_data: str = client.serialize()
        try:
            # Store data in Redis
            self.redis.set(item_key, serialized_data)

            # Maintain indices for common search fields
            self.redis.sadd(f"client:index:name:{client.name}", client.client_id)
            self.redis.sadd(f"client:index:api_key:{client.api_key}", client.client_id)
            return True
        except Exception as e:
            LOG.error(f"Failed to add client to Redis/RediSearch: {e}")
            return False

    def search_by_value(self, key: str, val: Union[str, bool, int, float]) -> List[Client]:
        """
        Search for clients by a specific key-value pair in Redis.

        Args:
            key: The key to search by.
            val: The value to search for.

        Returns:
            A list of clients that match the search criteria.
        """
        # Use index if available
        if key in ['name', 'api_key']:
            client_ids = self.redis.smembers(f"client:index:{key}:{val}")
            res = [cast2client(self.redis.get(f"client:{cid}"))
                   for cid in client_ids]
            res = [c for c in res if c.api_key != "revoked"]
            return res

        res = []
        for client_id in self.redis.scan_iter(f"client:*"):
            if client_id.startswith("client:index:"):
                continue
            client_data = self.redis.get(client_id)
            client = cast2client(client_data)
            if hasattr(client, key) and getattr(client, key) == val:
                res.append(client)
        return res

    def __len__(self) -> int:
        """
        Get the number of items in the Redis database.

        Returns:
            The number of clients in the database.
        """
        return int(len(self.redis.keys("client:*")) / 3)  # because of index entries for name/key fastsearch

    def __iter__(self) -> Iterable['Client']:
        """
        Iterate over all clients in Redis.

        Returns:
            An iterator over the clients in the database.
        """
        for client_id in self.redis.scan_iter(f"client:*"):
            if client_id.startswith("client:index:"):
                continue
            try:
                yield cast2client(self.redis.get(client_id))
            except Exception as e:
                LOG.error(f"Failed to get client '{client_id}' : {e}")


class ClientDatabase:
    valid_backends = ["json", "redis", "sqlite"]

    def __init__(self, backend="json", **backend_kwargs):
        """
        Initialize the client database with the specified backend.
        """
        backend_kwargs = backend_kwargs or {}
        if backend not in self.valid_backends:
            raise NotImplementedError(f"{backend} not supported, choose one of {self.valid_backends}")

        if backend == "json":
            self.db = JsonDB(**backend_kwargs)
        elif backend == "redis":
            self.db = RedisDB(**backend_kwargs)
        elif backend == "sqlite":
            self.db = SQLiteDB(**backend_kwargs)
        else:
            raise NotImplementedError(f"{backend} not supported, valid databases: {self.valid_backends}")

    def delete_client(self, key: str) -> bool:
        user = self.get_client_by_api_key(key)
        if user:
            return self.db.delete_item(user)
        return False

    def get_clients_by_name(self, name: str) -> List[Client]:
        return self.db.search_by_value("name", name)

    def get_client_by_api_key(self, api_key: str) -> Optional[Client]:
        search: List[Client] = self.db.search_by_value("api_key", api_key)
        if len(search):
            return search[0]
        return None

    def add_client(self,
                   name: str,
                   key: str = "",
                   admin: bool = False,
                   intent_blacklist: Optional[List[str]] = None,
                   skill_blacklist: Optional[List[str]] = None,
                   message_blacklist: Optional[List[str]] = None,
                   allowed_types: Optional[List[str]] = None,
                   crypto_key: Optional[str] = None,
                   password: Optional[str] = None) -> bool:
        if crypto_key is not None:
            crypto_key = crypto_key[:16]

        user = self.get_client_by_api_key(key)
        if user:
            # Update the existing client object directly
            if name:
                user.name = name
            if intent_blacklist:
                user.intent_blacklist = intent_blacklist
            if skill_blacklist:
                user.skill_blacklist = skill_blacklist
            if message_blacklist:
                user.message_blacklist = message_blacklist
            if allowed_types:
                user.allowed_types = allowed_types
            if admin is not None:
                user.is_admin = admin
            if crypto_key:
                user.crypto_key = crypto_key
            if password:
                user.password = password
            return self.db.update_item(user)

        user = Client(
            api_key=key,
            name=name,
            intent_blacklist=intent_blacklist,
            skill_blacklist=skill_blacklist,
            message_blacklist=message_blacklist,
            crypto_key=crypto_key,
            client_id=self.total_clients() + 1,
            is_admin=admin,
            password=password,
            allowed_types=allowed_types,
        )
        return self.db.add_item(user)

    def total_clients(self) -> int:
        return len(self.db)

    def __enter__(self):
        """Context handler"""
        return self

    def __iter__(self) -> Iterable[Client]:
        yield from self.db

    def __exit__(self, _type, value, traceback):
        """Commits changes and Closes the session"""
        try:
            self.db.commit()
        except Exception as e:
            LOG.error(e)
