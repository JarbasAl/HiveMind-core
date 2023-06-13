import os

import click
from rich.console import Console
from rich.table import Table
from ovos_config import Configuration
from hivemind_core.database import ClientDatabase
from ovos_utils.xdg_utils import xdg_data_home


@click.group()
def hmcore_cmds():
    pass


@hmcore_cmds.command(help="add credentials for a client", name="add-client")
@click.argument("name", required=False)
@click.argument("access_key", required=False)
@click.argument("password",  required=False)
@click.argument("crypto_key",  required=False)
def add_client(name, access_key, password, crypto_key):
    key = crypto_key
    if key:
        print("WARNING: crypto key is deprecated, use password instead if your client supports it")
        print("WARNING: for security the encryption key should be randomly generated\n"
              "Defining your own key is discouraged")
        if len(key) != 16:
            print("Encryption key needs to be exactly 16 characters!")
            raise ValueError
    else:
        key = os.urandom(8).hex()

    password = password or os.urandom(16).hex()

    access_key = access_key or os.urandom(16).hex()
    with ClientDatabase() as db:
        name = name or f"HiveMind-Node-{db.total_clients()}"
        db.add_client(name, access_key, crypto_key=key, password=password)

        # verify
        user = db.get_client_by_api_key(access_key)
        node_id = db.get_item_id(user)

        print("Credentials added to database!\n")
        print("Node ID:", node_id)
        print("Friendly Name:", name)
        print("Access Key:", access_key)
        print("Password:", password)
        print("Encryption Key:", key)

        print("WARNING: Encryption Key is deprecated, only use if your client does not support password")


@hmcore_cmds.command(help="remove credentials for a client", name="delete-client")
@click.argument("node_id", required=True)
def delete_client(node_id):
    with ClientDatabase() as db:
        for x in db:
            if x["client_id"] == int(node_id):
                item_id = db.get_item_id(x)
                db.update_item(item_id, dict(client_id=-1, api_key="revoked"))
                print(f"Revoked credentials!\n")
                print("Node ID:", x["client_id"])
                print("Friendly Name:", x["name"])
                print("Access Key:", x["api_key"])
                print("Password:", x["password"])
                print("Encryption Key:", x["crypto_key"])
                break
        else:
            print("Invalid Node ID!")


@hmcore_cmds.command(help="list clients and credentials", name="list-clients")
def list_clients():
    console = Console()
    table = Table(title="HiveMind Credentials:")
    table.add_column("ID", justify="center")
    table.add_column("Name", justify="center")
    table.add_column("Access Key", justify="center")
    table.add_column("Passwordy", justify="center")
    table.add_column("Crypto Key", justify="center")

    with ClientDatabase() as db:
        for x in db:
            if x["client_id"] != -1:
                table.add_row(str(x["client_id"]), x["name"], x["api_key"], x["password"], x["crypto_key"])

    console.print(table)


@hmcore_cmds.command(help="start listening for HiveMind connections", name="listen")
@click.option("--host", help="HiveMind host", type=str,
              default=Configuration().get('websocket', {}).get("host", "0.0.0.0"))
@click.option("--port", help="HiveMind port number", type=int,
              default=Configuration().get('websocket', {}).get("port", 5678))
@click.option("--ssl", help="use wss://", type=bool,
              default=Configuration().get('websocket', {}).get("ssl", False))
@click.option("--cert_dir", help="HiveMind SSL certificate directory", type=str,
              default=Configuration().get('websocket', {}).get("cert_dir", f"{xdg_data_home()}/hivemind"))
@click.option("--cert_name", help="HiveMind SSL certificate file name", type=str,
              default=Configuration().get('websocket', {}).get("cert_name", "hivemind"))
def listen(host: str, port: int, ssl: bool, cert_dir: str, cert_name: str):
    from hivemind_core.service import HiveMindService

    websocket_config = {
        "host": host,
        "port": port,
        "ssl": ssl,
        "cert_dir": cert_dir,
        "cert_name": cert_name
    }

    service = HiveMindService(websocket_config=websocket_config)
    service.start()


if __name__ == "__main__":
    hmcore_cmds()

