import json
import os
import redis
from hivemind_core.plugins.database.utils import cast_to_client_obj, Client
from typing import Optional, List, Dict, Any
from redis.commands.json.path import Path
from redis.commands.search.query import Query


class Clients:
    def __init__(self):
        self.r = redis.Redis(host="localhost", port=6379)
        self.rs = self.r.ft("idx:clients")

    @cast_to_client_obj()
    def get_client_by_api_key(self, api_key: str) -> Optional[Client]:
        search = self.rs.search(Query(f"@api_key:{api_key}"))
        if len(search.docs):
            return json.loads(search.docs[0].json)
        return None

    @cast_to_client_obj()
    def get_clients_by_name(self, name: str) -> Optional[List[Client]]:
        search = self.rs.search(Query(f"@name:{name}"))
        if len(search.docs):
            return json.loads(search.docs)
        return None

    def get_all_clients(
        self, sort_by: str = "id", asc: bool = True
    ) -> Optional[List[Client]]:
        clients: List = []
        search = self.rs.search(Query("@id:[0 +inf]").sort_by(sort_by, asc))
        for client in search.docs:
            clients.append(json.loads(client.json))
        return clients

    @cast_to_client_obj()
    def add_client(
        self,
        name: str,
        key: str = "",
        admin: bool = False,
        blacklist: Optional[Dict[str, Any]] = None,
        allowed_types: Optional[List[str]] = None,
        crypto_key: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Client:
        user = None
        if key:
            user = self.get_client_by_api_key(key)
        if crypto_key is not None:
            crypto_key = crypto_key[:16]
        if user is not None:
            if name:
                user["name"] = name
            if blacklist:
                user["blacklist"] = blacklist
            if allowed_types:
                user["allowed_types"] = allowed_types
            if admin is not None:
                user["is_admin"] = admin
            if crypto_key:
                user["crypto_key"] = crypto_key
            if password:
                user["password"] = password
            self.update_item(item_id, user)
        else:
            client_id = 0
            if len(self.get_all_clients()) > 0:
                client_id: str = self.get_all_clients(asc=False)[0]["client_id"] + 1             
            user = Client(
                api_key=key,
                name=name,
                blacklist=blacklist,
                crypto_key=crypto_key,
                client_id=client_id,
                is_admin=admin,
                password=password,
                allowed_types=allowed_types,
            )
            self.r.json().set(f"client:{client_id}", Path.root_path(), user.__dict__)
        return user.__dict__

    @cast_to_client_obj()
    def update_client(self, client_id: int, client: Client) -> Client:
        self.r.json().set(f"client:{client_id}", Path.root_path(), client)
        return client

    def delete_client(self, client_id: int) -> None:
        self.r.json().delete(f"client:{client_id}")
        return None
