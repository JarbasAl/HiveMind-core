import os
from unittest import TestCase

from hivemind_core.database import ClientDatabase, Client


class TestDB(TestCase):
    def test_add_entry(self):
        key = os.urandom(8).hex()
        access_key = os.urandom(16).hex()
        password = None

        with ClientDatabase() as db:
            n = db.total_clients()
            name = f"HiveMind-Node-{n}"
            user = db.add_client(name, access_key, crypto_key=key, password=password)
            # verify data
            self.assertTrue(isinstance(user, Client))
            self.assertEqual(user.name, name)
            self.assertEqual(user.api_key, access_key)

            # test search entry in db
            node_id = db.get_item_id(user)
            self.assertEqual(node_id, n)

            user2 = db.get_client_by_api_key(access_key)
            self.assertEqual(user, user2)

            for u in db.get_clients_by_name(name):
                self.assertEqual(user.name, u.name)

            # test delete entry
            db.delete_client(access_key)
            node_id = db.get_item_id(user)
            self.assertEqual(node_id, -1)
            user = db.get_client_by_api_key(access_key)
            self.assertIsNone(user)
