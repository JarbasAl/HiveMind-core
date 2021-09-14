import json
from jarbas_hive_mind.configuration import CONFIGURATION
from json_database import JsonDatabase
from ovos_utils.log import LOG


class Client:
    def __init__(self, client_id, api_key, name="",
                 description="", is_admin=False, last_seen=-1,
                 blacklist=None, crypto_key=None):
        self.client_id = client_id
        self.description = description
        self.api_key = api_key
        self.name = name
        self.last_seen = last_seen
        self.is_admin = is_admin
        self.crypto_key = crypto_key
        self.blacklist = blacklist or {
            "messages": [],
            "skills": [],
            "intents": []
        }


class JsonClientDatabase(JsonDatabase):
    def __init__(self, path=CONFIGURATION["database"]):
        super().__init__("clients", path)

    def update_timestamp(self, key, timestamp):
        user = self.get_client_by_api_key(key)
        if not user:
            return False
        item_id = self.get_item_id(user)
        user["last_seen"] = timestamp
        self.update_item(item_id, user)
        return True

    def delete_client(self, key):
        user = self.get_client_by_api_key(key)
        if user:
            item_id = self.get_item_id(user)
            self.update_item(item_id, Client(-1, api_key="revoked"))
            return True
        return False

    def change_key(self, old_key, new_key):
        user = self.get_client_by_api_key(old_key)
        if not user:
            return False
        item_id = self.get_item_id(user)
        user["api_key"] = new_key
        self.update_item(item_id, user)
        return True

    def change_crypto_key(self, api_key, new_key):
        user = self.get_client_by_api_key(api_key)
        if not user:
            return False
        item_id = self.get_item_id(user)
        user["crypto_key"] = new_key
        self.update_item(item_id, user)
        return True

    def get_crypto_key(self, api_key):
        user = self.get_client_by_api_key(api_key)
        if not user:
            return None
        return user["crypto_key"]

    def change_name(self, new_name, key):
        user = self.get_client_by_api_key(key)
        if not user:
            return False
        item_id = self.get_item_id(user)
        user["name"] = new_name
        self.update_item(item_id, user)
        return True

    def change_blacklist(self, blacklist, key):
        if isinstance(blacklist, dict):
            blacklist = json.dumps(blacklist)
        user = self.get_client_by_api_key(key)
        if not user:
            return False
        item_id = self.get_item_id(user)
        user["blacklist"] = blacklist
        self.update_item(item_id, user)
        return True

    def get_blacklist_by_api_key(self, api_key):
        search = self.search_by_value("api_key", api_key)
        if len(search):
            return search[0]["blacklist"]
        return None

    def get_client_by_api_key(self, api_key):
        search = self.search_by_value("api_key", api_key)
        if len(search):
            return search[0]
        return None

    def get_clients_by_name(self, name):
        return self.search_by_value("name", name)

    def add_client(self, name=None, key="",
                   admin=None, blacklist=None, crypto_key=None):

        user = self.get_client_by_api_key(key)
        item_id = self.get_item_id(user)
        if crypto_key is not None:
            crypto_key = crypto_key[:16]
        if item_id >= 0:
            if name:
                user["name"] = name
            if blacklist:
                user["blacklist"] = blacklist
            if admin is not None:
                user["is_admin"] = admin
            user["crypto_key"] = crypto_key

            self.update_item(item_id, user)
        else:
            user = Client(api_key=key, name=name,
                          blacklist=blacklist, crypto_key=crypto_key,
                          client_id=self.total_clients() + 1,
                          is_admin=admin)
            self.add_item(user)

    def total_clients(self):
        return len(self)

    def __enter__(self):
        """ Context handler """
        return self

    def __exit__(self, _type, value, traceback):
        """ Commits changes and Closes the session """
        try:
            self.commit()
        except Exception as e:
            LOG.error(e)
