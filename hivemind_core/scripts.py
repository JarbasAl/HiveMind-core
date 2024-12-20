import os
from typing import Optional

import click
from ovos_utils.xdg_utils import xdg_data_home
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from hivemind_core.database import ClientDatabase


def get_db_kwargs(db_backend: str, db_name: str, db_folder: str,
                  redis_host: str, redis_port: int, redis_password: Optional[str]) -> dict:
    """Get database configuration kwargs based on backend type."""
    kwargs = {"backend": db_backend}
    if db_backend == "redis":
        kwargs.update({
            "host": redis_host,
            "port": redis_port,
            "password": redis_password
        })
    else:
        kwargs.update({
            "name": db_name,
            "subfolder": db_folder
        })
    return kwargs


@click.group()
def hmcore_cmds():
    pass


@hmcore_cmds.command(help="add credentials for a client", name="add-client")
@click.option("--name", required=False, type=str)
@click.option("--access-key", required=False, type=str)
@click.option("--password", required=False, type=str)
@click.option("--crypto-key", required=False, type=str)
@click.option("--db-backend", type=click.Choice(['redis', 'json', 'sqlite'], case_sensitive=False), default='json',
              help="Select the database backend to use. Options: redis, sqlite, json.")
@click.option("--db-name", type=str, default="clients",
              help="[json/sqlite] The name for the database file. ~/.cache/hivemind-core/{name}")
@click.option("--db-folder", type=str, default="hivemind-core",
              help="[json/sqlite] The subfolder where database files are stored. ~/.cache/{db_folder}}")
@click.option("--redis-host", default="localhost", help="[redis] Host for Redis. Default is localhost.")
@click.option("--redis-port", default=6379, help="[redis] Port for Redis. Default is 6379.")
@click.option("--redis-password", required=False, help="[redis] Password for Redis. Default None")
def add_client(name, access_key, password, crypto_key,
               db_backend, db_name, db_folder,
               redis_host, redis_port, redis_password):
    kwargs = get_db_kwargs(db_backend, db_name, db_folder, redis_host, redis_port, redis_password)

    key = crypto_key
    if key:
        print(
            "WARNING: crypto key is deprecated, use password instead if your client supports it"
        )
        print(
            "WARNING: for security the encryption key should be randomly generated\n"
            "Defining your own key is discouraged"
        )
        if len(key) != 16:
            print("Encryption key needs to be exactly 16 characters!")
            raise ValueError
    else:
        key = os.urandom(8).hex()

    password = password or os.urandom(16).hex()
    access_key = access_key or os.urandom(16).hex()

    with ClientDatabase(**kwargs) as db:
        name = name or f"HiveMind-Node-{db.total_clients()}"
        print(f"Database backend: {db.db.__class__.__name__}")
        success = db.add_client(name, access_key, crypto_key=key, password=password)
        if not success:
            raise ValueError(f"Error adding User to database: {name}")

        # verify
        user = db.get_client_by_api_key(access_key)
        if user is None:
            raise ValueError(f"User not found: {name}")

        print("Credentials added to database!\n")
        print("Node ID:", user.client_id)
        print("Friendly Name:", name)
        print("Access Key:", access_key)
        print("Password:", password)
        print("Encryption Key:", key)

        print(
            "WARNING: Encryption Key is deprecated, only use if your client does not support password"
        )


@hmcore_cmds.command(help="allow message types sent from a client", name="allow-msg")
@click.argument("msg_type", required=True, type=str)
@click.argument("node_id", required=False, type=int)
@click.option("--db-backend", type=click.Choice(['redis', 'json', 'sqlite'], case_sensitive=False), default='json',
              help="Select the database backend to use. Options: redis, sqlite, json.")
@click.option("--db-name", type=str, default="clients",
              help="[json/sqlite] The name for the database file. ~/.cache/hivemind-core/{name}")
@click.option("--db-folder", type=str, default="hivemind-core",
              help="[json/sqlite] The subfolder where database files are stored. ~/.cache/{db_folder}}")
@click.option("--redis-host", default="localhost", help="[redis] Host for Redis. Default is localhost.")
@click.option("--redis-port", default=6379, help="[redis] Port for Redis. Default is 6379.")
@click.option("--redis-password", required=False, help="[redis] Password for Redis. Default None")
def allow_msg(msg_type, node_id,
              db_backend, db_name, db_folder, redis_host, redis_port, redis_password):
    kwargs = get_db_kwargs(db_backend, db_name, db_folder, redis_host, redis_port, redis_password)

    if not node_id:
        # list clients and prompt for id using rich
        table = Table(title="HiveMind Clients")
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Name", style="magenta")
        table.add_column("Allowed Msg Types", style="yellow")
        _choices = []
        for client in ClientDatabase(**kwargs):
            if client.client_id != -1:
                table.add_row(
                    str(client.client_id),
                    client.name,
                    str(client.allowed_types),
                )
                _choices.append(str(client.client_id))

        if not _choices:
            print("No clients found!")
            exit()
        elif len(_choices) > 1:
            console = Console()
            console.print(table)
            _exit = str(max(int(i) for i in _choices) + 1)
            node_id = Prompt.ask(
                f"To which client you want to add '{msg_type}'? ({_exit}='Exit')",
                choices=_choices + [_exit],
            )
            if node_id == _exit:
                console.print("User exit", style="red")
                exit()
        else:
            node_id = _choices[0]

    with ClientDatabase(**kwargs) as db:
        for client in db:
            if client.client_id == int(node_id):
                if msg_type in client.allowed_types:
                    print(f"Client {client.name} already allowed '{msg_type}'")
                    exit()
                client.allowed_types.append(msg_type)
                db.update_item(client)
                print(f"Allowed '{msg_type}' for {client.name}")
                break


@hmcore_cmds.command(
    help="remove credentials for a client (numeric unique ID)", name="delete-client"
)
@click.argument("node_id", required=True, type=int)
@click.option("--db-backend", type=click.Choice(['redis', 'json', 'sqlite'], case_sensitive=False), default='json',
              help="Select the database backend to use. Options: redis, sqlite, json.")
@click.option("--db-name", type=str, default="clients",
              help="[json/sqlite] The name for the database file. ~/.cache/hivemind-core/{name}")
@click.option("--db-folder", type=str, default="hivemind-core",
              help="[json/sqlite] The subfolder where database files are stored. ~/.cache/{db_folder}}")
@click.option("--redis-host", default="localhost", help="[redis] Host for Redis. Default is localhost.")
@click.option("--redis-port", default=6379, help="[redis] Port for Redis. Default is 6379.")
@click.option("--redis-password", required=False, help="[redis] Password for Redis. Default None")
def delete_client(node_id, db_name, db_folder,
                  db_backend, redis_host, redis_port, redis_password):
    kwargs = get_db_kwargs(db_backend, db_name, db_folder, redis_host, redis_port, redis_password)
    with ClientDatabase(**kwargs) as db:
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
@click.option("--db-backend", type=click.Choice(['redis', 'json', 'sqlite'], case_sensitive=False), default='json',
              help="Select the database backend to use. Options: redis, sqlite, json.")
@click.option("--db-name", type=str, default="clients",
              help="[json/sqlite] The name for the database file. ~/.cache/hivemind-core/{name}")
@click.option("--db-folder", type=str, default="hivemind-core",
              help="[json/sqlite] The subfolder where database files are stored. ~/.cache/{db_folder}}")
@click.option("--redis-host", default="localhost", help="[redis] Host for Redis. Default is localhost.")
@click.option("--redis-port", default=6379, help="[redis] Port for Redis. Default is 6379.")
@click.option("--redis-password", required=False, help="[redis] Password for Redis. Default None")
def list_clients(db_backend, db_name, db_folder, redis_host, redis_port, redis_password):
    kwargs = get_db_kwargs(db_backend, db_name, db_folder, redis_host, redis_port, redis_password)
    console = Console()
    table = Table(title="HiveMind Credentials:")
    table.add_column("ID", justify="center")
    table.add_column("Name", justify="center")
    table.add_column("Access Key", justify="center")
    table.add_column("Password", justify="center")
    table.add_column("Crypto Key", justify="center")

    with ClientDatabase(**kwargs) as db:
        for x in db:
            if x["client_id"] != -1:
                table.add_row(
                    str(x["client_id"]),
                    x["name"],
                    x["api_key"],
                    x["password"],
                    x["crypto_key"],
                )

    console.print(table)


@hmcore_cmds.command(help="start listening for HiveMind connections", name="listen")
@click.option(
    "--ovos_bus_address",
    help="Open Voice OS bus address",
    type=str,
    default="127.0.0.1",
)
@click.option(
    "--ovos_bus_port", help="Open Voice OS bus port number", type=int, default=8181
)
@click.option(
    "--host",
    help="HiveMind host",
    type=str,
    default="0.0.0.0",
)
@click.option("--port", help="HiveMind port number", type=int, default=5678)
@click.option("--ssl", help="use wss://", type=bool, default=False)
@click.option(
    "--cert_dir",
    help="HiveMind SSL certificate directory",
    type=str,
    default=f"{xdg_data_home()}/hivemind",
)
@click.option(
    "--cert_name",
    help="HiveMind SSL certificate file name",
    type=str,
    default="hivemind",
)
@click.option("--db-backend", type=click.Choice(['redis', 'json', 'sqlite'], case_sensitive=False), default='json',
              help="Select the database backend to use. Options: redis, sqlite, json.")
@click.option("--db-name", type=str, default="clients",
              help="[json/sqlite] The name for the database file. ~/.cache/hivemind-core/{name}")
@click.option("--db-folder", type=str, default="hivemind-core",
              help="[json/sqlite] The subfolder where database files are stored. ~/.cache/{db_folder}}")
@click.option("--redis-host", default="localhost", help="[redis] Host for Redis. Default is localhost.")
@click.option("--redis-port", default=6379, help="[redis] Port for Redis. Default is 6379.")
@click.option("--redis-password", required=False, help="[redis] Password for Redis. Default None")
def listen(ovos_bus_address: str, ovos_bus_port: int, host: str, port: int,
           ssl: bool, cert_dir: str, cert_name: str,
           db_backend, db_name, db_folder,
           redis_host, redis_port, redis_password):
    kwargs = get_db_kwargs(db_backend, db_name, db_folder, redis_host, redis_port, redis_password)
    from hivemind_core.service import HiveMindService

    ovos_bus_config = {
        "host": ovos_bus_address,
        "port": ovos_bus_port,
    }

    websocket_config = {
        "host": host,
        "port": port,
        "ssl": ssl,
        "cert_dir": cert_dir,
        "cert_name": cert_name,
    }
    service = HiveMindService(
        ovos_bus_config=ovos_bus_config,
        websocket_config=websocket_config,
        db=ClientDatabase(**kwargs)
    )
    service.run()


@hmcore_cmds.command(help="blacklist skills from being triggered by a client", name="blacklist-skill")
@click.argument("skill_id", required=True, type=str)
@click.argument("node_id", required=False, type=int)
@click.option("--db-backend", type=click.Choice(['redis', 'json', 'sqlite'], case_sensitive=False), default='json',
              help="Select the database backend to use. Options: redis, sqlite, json.")
@click.option("--db-name", type=str, default="clients",
              help="[json/sqlite] The name for the database file. ~/.cache/hivemind-core/{name}")
@click.option("--db-folder", type=str, default="hivemind-core",
              help="[json/sqlite] The subfolder where database files are stored. ~/.cache/{db_folder}}")
@click.option("--redis-host", default="localhost", help="[redis] Host for Redis. Default is localhost.")
@click.option("--redis-port", default=6379, help="[redis] Port for Redis. Default is 6379.")
@click.option("--redis-password", required=False, help="[redis] Password for Redis. Default None")
def blacklist_skill(skill_id, node_id,
                    db_backend, db_name, db_folder, redis_host, redis_port, redis_password):
    kwargs = get_db_kwargs(db_backend, db_name, db_folder, redis_host, redis_port, redis_password)

    if not node_id:
        # list clients and prompt for id using rich
        table = Table(title="HiveMind Clients")
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Name", style="magenta")
        table.add_column("Allowed Msg Types", style="yellow")
        _choices = []
        for client in ClientDatabase(**kwargs):
            if client.client_id != -1:
                table.add_row(
                    str(client.client_id),
                    client.name,
                    str(client.allowed_types),
                )
                _choices.append(str(client.client_id))

        if not _choices:
            print("No clients found!")
            exit()
        elif len(_choices) > 1:
            console = Console()
            console.print(table)
            _exit = str(max(int(i) for i in _choices) + 1)
            node_id = Prompt.ask(
                f"To which client you want to blacklist '{skill_id}'? ({_exit}='Exit')",
                choices=_choices + [_exit],
            )
            if node_id == _exit:
                console.print("User exit", style="red")
                exit()
        else:
            node_id = _choices[0]

    with ClientDatabase(**kwargs) as db:
        for client in db:
            if client.client_id == int(node_id):
                if skill_id in client.skill_blacklist:
                    print(f"Client {client.name} already blacklisted '{skill_id}'")
                    exit()

                client.skill_blacklist.append(skill_id)
                db.update_item(client)
                print(f"Blacklisted '{skill_id}' for {client.name}")
                break


@hmcore_cmds.command(help="remove skills from a client blacklist", name="unblacklist-skill")
@click.argument("skill_id", required=True, type=str)
@click.argument("node_id", required=False, type=int)
@click.option("--db-backend", type=click.Choice(['redis', 'json', 'sqlite'], case_sensitive=False), default='json',
              help="Select the database backend to use. Options: redis, sqlite, json.")
@click.option("--db-name", type=str, default="clients",
              help="[json/sqlite] The name for the database file. ~/.cache/hivemind-core/{name}")
@click.option("--db-folder", type=str, default="hivemind-core",
              help="[json/sqlite] The subfolder where database files are stored. ~/.cache/{db_folder}}")
@click.option("--redis-host", default="localhost", help="[redis] Host for Redis. Default is localhost.")
@click.option("--redis-port", default=6379, help="[redis] Port for Redis. Default is 6379.")
@click.option("--redis-password", required=False, help="[redis] Password for Redis. Default None")
def unblacklist_skill(skill_id, node_id,
                      db_backend, db_name, db_folder, redis_host, redis_port, redis_password):
    kwargs = get_db_kwargs(db_backend, db_name, db_folder, redis_host, redis_port, redis_password)

    if not node_id:
        # list clients and prompt for id using rich
        table = Table(title="HiveMind Clients")
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Name", style="magenta")
        table.add_column("Allowed Msg Types", style="yellow")
        _choices = []
        for client in ClientDatabase(**kwargs):
            if client.client_id != -1:
                table.add_row(
                    str(client.client_id),
                    client.name,
                    str(client.allowed_types),
                )
                _choices.append(str(client.client_id))

        if not _choices:
            print("No clients found!")
            exit()
        elif len(_choices) > 1:
            console = Console()
            console.print(table)
            _exit = str(max(int(i) for i in _choices) + 1)
            node_id = Prompt.ask(
                f"To which client you want to blacklist '{skill_id}'? ({_exit}='Exit')",
                choices=_choices + [_exit],
            )
            if node_id == _exit:
                console.print("User exit", style="red")
                exit()
        else:
            node_id = _choices[0]

    with ClientDatabase(**kwargs) as db:
        for client in db:
            if client.client_id == int(node_id):
                if skill_id not in client.skill_blacklist:
                    print(f"'{skill_id}' is not blacklisted for client {client.name}")
                    exit()
                client.skill_blacklist.remove(skill_id)
                db.update_item(client)
                print(f"Blacklisted '{skill_id}' for {client.name}")
                break


@hmcore_cmds.command(help="blacklist intents from being triggered by a client", name="blacklist-intent")
@click.argument("intent_id", required=True, type=str)
@click.argument("node_id", required=False, type=int)
@click.option("--db-backend", type=click.Choice(['redis', 'json', 'sqlite'], case_sensitive=False), default='json',
              help="Select the database backend to use. Options: redis, sqlite, json.")
@click.option("--db-name", type=str, default="clients",
              help="[json/sqlite] The name for the database file. ~/.cache/hivemind-core/{name}")
@click.option("--db-folder", type=str, default="hivemind-core",
              help="[json/sqlite] The subfolder where database files are stored. ~/.cache/{db_folder}}")
@click.option("--redis-host", default="localhost", help="[redis] Host for Redis. Default is localhost.")
@click.option("--redis-port", default=6379, help="[redis] Port for Redis. Default is 6379.")
@click.option("--redis-password", required=False, help="[redis] Password for Redis. Default None")
def blacklist_intent(intent_id, node_id,
                     db_backend, db_name, db_folder, redis_host, redis_port, redis_password):
    kwargs = get_db_kwargs(db_backend, db_name, db_folder, redis_host, redis_port, redis_password)

    if not node_id:
        # list clients and prompt for id using rich
        table = Table(title="HiveMind Clients")
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Name", style="magenta")
        table.add_column("Allowed Msg Types", style="yellow")
        _choices = []
        for client in ClientDatabase(**kwargs):
            if client.client_id != -1:
                table.add_row(
                    str(client.client_id),
                    client.name,
                    str(client.allowed_types),
                )
                _choices.append(str(client.client_id))

        if not _choices:
            print("No clients found!")
            exit()
        elif len(_choices) > 1:
            console = Console()
            console.print(table)
            _exit = str(max(int(i) for i in _choices) + 1)
            node_id = Prompt.ask(
                f"To which client you want to blacklist '{intent_id}'? ({_exit}='Exit')",
                choices=_choices + [_exit],
            )
            if node_id == _exit:
                console.print("User exit", style="red")
                exit()
        else:
            node_id = _choices[0]

    with ClientDatabase(**kwargs) as db:
        for client in db:
            if client.client_id == int(node_id):
                if intent_id in client.intent_blacklist:
                    print(f"Client {client.name} already blacklisted '{intent_id}'")
                    exit()
                client.intent_blacklist.append(intent_id)
                db.update_item(client)
                print(f"Blacklisted '{intent_id}' for {client.name}")
                break


@hmcore_cmds.command(help="remove intents from a client blacklist", name="unblacklist-intent")
@click.argument("intent_id", required=True, type=str)
@click.argument("node_id", required=False, type=int)
@click.option("--db-backend", type=click.Choice(['redis', 'json', 'sqlite'], case_sensitive=False), default='json',
              help="Select the database backend to use. Options: redis, sqlite, json.")
@click.option("--db-name", type=str, default="clients",
              help="[json/sqlite] The name for the database file. ~/.cache/hivemind-core/{name}")
@click.option("--db-folder", type=str, default="hivemind-core",
              help="[json/sqlite] The subfolder where database files are stored. ~/.cache/{db_folder}}")
@click.option("--redis-host", default="localhost", help="[redis] Host for Redis. Default is localhost.")
@click.option("--redis-port", default=6379, help="[redis] Port for Redis. Default is 6379.")
@click.option("--redis-password", required=False, help="[redis] Password for Redis. Default None")
def unblacklist_intent(intent_id, node_id,
                       db_backend, db_name, db_folder, redis_host, redis_port, redis_password):
    kwargs = get_db_kwargs(db_backend, db_name, db_folder, redis_host, redis_port, redis_password)

    if not node_id:
        # list clients and prompt for id using rich
        table = Table(title="HiveMind Clients")
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Name", style="magenta")
        table.add_column("Allowed Msg Types", style="yellow")
        _choices = []
        for client in ClientDatabase(**kwargs):
            if client.client_id != -1:
                table.add_row(
                    str(client.client_id),
                    client.name,
                    str(client.allowed_types),
                )
                _choices.append(str(client.client_id))

        if not _choices:
            print("No clients found!")
            exit()
        elif len(_choices) > 1:
            console = Console()
            console.print(table)
            _exit = str(max(int(i) for i in _choices) + 1)
            node_id = Prompt.ask(
                f"To which client you want to blacklist '{intent_id}'? ({_exit}='Exit')",
                choices=_choices + [_exit],
            )
            if node_id == _exit:
                console.print("User exit", style="red")
                exit()
        else:
            node_id = _choices[0]

    with ClientDatabase(**kwargs) as db:
        for client in db:
            if client.client_id == int(node_id):
                if intent_id not in client.intent_blacklist:
                    print(f" '{intent_id}' not blacklisted for Client {client.name} ")
                    exit()
                client.intent_blacklist.remove(intent_id)
                db.update_item(client)
                print(f"Unblacklisted '{intent_id}' for {client.name}")
                break


if __name__ == "__main__":
    hmcore_cmds()
