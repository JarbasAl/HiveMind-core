from hivemind_core.plugins.database.redis import clients
from hivemind_core.plugins.database.utils import Client
from typing import Optional, List, Dict, Any


class ClientDatabase:
    def __init__(self):
        self.db = clients.Clients()

    def __repr__(self) -> str:
        return str(self.db.get_all_clients())

    def __enter__(self):
        """Context handler"""
        return self

    def __exit__(self, _type, value, traceback):
        return True

    def get_client_by_api_key(self, api_key: str) -> Optional[Client]:
        return self.db.get_client_by_api_key(api_key)

    def get_all_clients(
        self, sort_by: str = "id", asc: bool = True
    ) -> Optional[List[Client]]:
        return self.db.get_all_clients(sort_by, asc)

    def total_clients(self) -> int:
        return len(self.get_all_clients())

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
        return self.db.add_client(
            name=name,
            key=key,
            admin=admin,
            blacklist=blacklist,
            allowed_types=allowed_types,
            crypto_key=crypto_key,
            password=password,
        )

    def update_client(self, client_id: int, client: Client) -> Client:
        return self.db.update_client(client_id, client)

    def delete_client(self, client_id: int) -> None:
        self.db.delete_client(client_id)
        return None
