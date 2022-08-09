from os.path import basename, dirname
from json_database import JsonConfigXDG


class NodeIdentity:
    def __init__(self):
        self._identity = JsonConfigXDG("_identity", subfolder="hivemind")

    @property
    def name(self):
        """human readable label, not guaranteed unique
        can describe functionality, brand, capabilities or something else...
        """
        if not self._identity.get("name") and self._identity.get("key"):
            self._identity["name"] = basename(self._identity["key"])
        return self._identity.get("name") or "unnamed-node"

    @property
    def identity_file(self):
        """path to PRIVATE .asc PGP key, this cryptographic key
        uniquely identifies this device across the hive and proves it's identity"""
        return self._identity.get("key") or \
               f"{dirname(self._identity.path)}/{self.name}.asc"

    @property
    def password(self):
        """password is used to generate a session aes key on handshake.
        It should be used instead of users manually setting an encryption key.
        This password can be thought as identifying a sub-hive where all devices
        can connect to each other (access keys still need to be valid)"""
        return self._identity.get("password")

    def save(self):
        self._identity.store()

    def reload(self):
        self._identity.reload()