import json
import unittest
from unittest.mock import patch, MagicMock

from hivemind_core.database import Client, JsonDB, RedisDB, cast2client, ClientDatabase


class TestClient(unittest.TestCase):

    def test_client_creation(self):
        client_data = {
            "client_id": 1,
            "api_key": "test_api_key",
            "name": "Test Client",
            "description": "A test client",
            "is_admin": False
        }
        client = Client(**client_data)
        self.assertEqual(client.client_id, 1)
        self.assertEqual(client.api_key, "test_api_key")
        self.assertEqual(client.name, "Test Client")
        self.assertEqual(client.description, "A test client")
        self.assertFalse(client.is_admin)

    def test_client_serialization(self):
        client_data = {
            "client_id": 1,
            "api_key": "test_api_key",
            "name": "Test Client",
            "description": "A test client",
            "is_admin": False
        }
        client = Client(**client_data)
        serialized_data = client.serialize()
        self.assertIsInstance(serialized_data, str)
        self.assertIn('"client_id": 1', serialized_data)

    def test_client_deserialization(self):
        client_data = {
            "client_id": 1,
            "api_key": "test_api_key",
            "name": "Test Client",
            "description": "A test client",
            "is_admin": False
        }
        serialized_data = json.dumps(client_data)
        client = Client.deserialize(serialized_data)
        self.assertEqual(client.client_id, 1)
        self.assertEqual(client.api_key, "test_api_key")

    def test_cast2client(self):
        client_data = {
            "client_id": 1,
            "api_key": "test_api_key",
            "name": "Test Client",
            "description": "A test client",
            "is_admin": False
        }
        client = Client(**client_data)
        serialized_client = client.serialize()
        deserialized_client = cast2client(serialized_client)
        self.assertEqual(client, deserialized_client)

        client_list = [client, client]
        deserialized_client_list = cast2client([serialized_client, serialized_client])
        self.assertEqual(client_list, deserialized_client_list)


class TestJsonDB(unittest.TestCase):

    def setUp(self):
        self.db = JsonDB(name=".hivemind-test")

    def test_add_item(self):
        client_data = {
            "client_id": 1,
            "api_key": "test_api_key",
            "name": "Test Client",
            "description": "A test client",
            "is_admin": False
        }
        client = Client(**client_data)
        self.db.add_item(client)
        self.assertTrue(client.client_id in self.db._db)

    def test_delete_item(self):
        client_data = {
            "client_id": 1,
            "api_key": "test_api_key",
            "name": "Test Client",
            "description": "A test client",
            "is_admin": False
        }
        client = Client(**client_data)
        self.db.add_item(client)
        result = self.db.delete_item(client)
        self.assertTrue(result)

    def test_search_by_value(self):
        client_data = {
            "client_id": 1,
            "api_key": "test_api_key",
            "name": "Test Client",
            "description": "A test client",
            "is_admin": False
        }
        client = Client(**client_data)
        self.db.add_item(client)
        clients = self.db.search_by_value("name", "Test Client")
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0].name, "Test Client")


class TestRedisDB(unittest.TestCase):

    @patch('hivemind_core.database.redis.StrictRedis')
    def setUp(self, MockRedis):
        self.mock_redis = MagicMock()
        MockRedis.return_value = self.mock_redis
        self.db = RedisDB()

    def test_add_item(self):
        client_data = {
            "client_id": 1,
            "api_key": "test_api_key",
            "name": "Test Client",
            "description": "A test client",
            "is_admin": False
        }
        client = Client(**client_data)
        self.db.add_item(client)
        self.mock_redis.set.assert_called_once()

    def test_delete_item(self):
        client_data = {
            "client_id": 1,
            "api_key": "test_api_key",
            "name": "Test Client",
            "description": "A test client",
            "is_admin": False
        }
        client = Client(**client_data)
        self.db.add_item(client)
        result = self.db.delete_item(client)
        self.assertTrue(result)


class TestClientDatabase(unittest.TestCase):

    def test_delete_client(self):
        db = MagicMock()
        db.delete_item.return_value = True
        client_db = ClientDatabase(backend="json")
        client_db.db = db
        client_db.get_client_by_api_key = MagicMock()
        client_db.get_client_by_api_key.return_value = Client(1, "A")

        result = client_db.delete_client("test_api_key")
        self.assertTrue(result)
        db.delete_item.assert_called_once()

    def test_get_clients_by_name(self):
        db = MagicMock()
        client_data = {
            "client_id": 1,
            "api_key": "test_api_key",
            "name": "Test Client",
            "description": "A test client",
            "is_admin": False
        }
        client = Client(**client_data)
        db.search_by_value.return_value = [client]

        client_db = ClientDatabase(backend="json")
        client_db.db = db
        clients = client_db.get_clients_by_name("Test Client")
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0].name, "Test Client")


if __name__ == '__main__':
    unittest.main()
