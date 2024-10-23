import os

import click
from ovos_utils.xdg_utils import xdg_data_home
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from hivemind_core.database import ClientDatabase


@click.group()
def hmcore_cmds():
    pass


@hmcore_cmds.command(help="add credentials for a client", name="add-client")
@click.option("--name", required=False, type=str)
@click.option("--access-key", required=False, type=str)
@click.option("--password", required=False, type=str)
@click.option("--crypto-key", required=False, type=str)
def add_client(name, access_key, password, crypto_key):
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

        print(
            "WARNING: Encryption Key is deprecated, only use if your client does not support password"
        )


@hmcore_cmds.command(help="allow message types sent from a client", name="allow-msg")
@click.argument("msg_type", required=True, type=str)
@click.argument("node_id", required=False, type=int)
def allow_msg(msg_type, node_id):
    if not node_id:
        # list clients and prompt for id using rich
        table = Table(title="HiveMind Clients")
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Name", style="magenta")
        table.add_column("Allowed Msg Types", style="yellow")
        _choices = []
        for client in ClientDatabase():
            if client["client_id"] != -1:
                table.add_row(
                    str(client["client_id"]),
                    client["name"],
                    str(client.get("allowed_types", [])),
                )
                _choices.append(str(client["client_id"]))

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

    with ClientDatabase() as db:
        for client in db:
            if client["client_id"] == int(node_id):
                allowed_types = client.get("allowed_types", [])
                if msg_type in allowed_types:
                    print(f"Client {client['name']} already allowed '{msg_type}'")
                    exit()

                allowed_types.append(msg_type)
                client["allowed_types"] = allowed_types
                item_id = db.get_item_id(client)
                db.update_item(item_id, client)
                print(f"Allowed '{msg_type}' for {client['name']}")
                break


@hmcore_cmds.command(
    help="remove credentials for a client (numeric unique ID)", name="delete-client"
)
@click.argument("node_id", required=True, type=int)
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
    table.add_column("Password", justify="center")
    table.add_column("Crypto Key", justify="center")

    with ClientDatabase() as db:
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
def listen(
        ovos_bus_address: str,
        ovos_bus_port: int,
        host: str,
        port: int,
        ssl: bool,
        cert_dir: str,
        cert_name: str,
):
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
        ovos_bus_config=ovos_bus_config, websocket_config=websocket_config
    )
    service.run()


@hmcore_cmds.command(help="blacklist skills from being triggered by a client", name="blacklist-skill")
@click.argument("skill_id", required=True, type=str)
@click.argument("node_id", required=False, type=int)
def blacklist_skill(skill_id, node_id):
    if not node_id:
        # list clients and prompt for id using rich
        table = Table(title="HiveMind Clients")
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Name", style="magenta")
        table.add_column("Allowed Msg Types", style="yellow")
        _choices = []
        for client in ClientDatabase():
            if client["client_id"] != -1:
                table.add_row(
                    str(client["client_id"]),
                    client["name"],
                    str(client.get("allowed_types", [])),
                )
                _choices.append(str(client["client_id"]))

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

    with ClientDatabase() as db:
        for client in db:
            if client["client_id"] == int(node_id):
                blacklist = client.get("blacklist", {"messages": [], "skills": [], "intents": []})
                if skill_id in blacklist["skills"]:
                    print(f"Client {client['name']} already blacklisted '{skill_id}'")
                    exit()

                blacklist["skills"].append(skill_id)
                client["blacklist"] = blacklist
                item_id = db.get_item_id(client)
                db.update_item(item_id, client)
                print(f"Blacklisted '{skill_id}' for {client['name']}")
                break


@hmcore_cmds.command(help="remove skills from a client blacklist", name="unblacklist-skill")
@click.argument("skill_id", required=True, type=str)
@click.argument("node_id", required=False, type=int)
def unblacklist_skill(skill_id, node_id):
    if not node_id:
        # list clients and prompt for id using rich
        table = Table(title="HiveMind Clients")
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Name", style="magenta")
        table.add_column("Allowed Msg Types", style="yellow")
        _choices = []
        for client in ClientDatabase():
            if client["client_id"] != -1:
                table.add_row(
                    str(client["client_id"]),
                    client["name"],
                    str(client.get("allowed_types", [])),
                )
                _choices.append(str(client["client_id"]))

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

    with ClientDatabase() as db:
        for client in db:
            if client["client_id"] == int(node_id):
                blacklist = client.get("blacklist", {"messages": [], "skills": [], "intents": []})
                if skill_id not in blacklist["skills"]:
                    print(f"'{skill_id}' is not blacklisted for client {client['name']}")
                    exit()

                blacklist["skills"].pop(skill_id)
                client["blacklist"] = blacklist
                item_id = db.get_item_id(client)
                db.update_item(item_id, client)
                print(f"Blacklisted '{skill_id}' for {client['name']}")
                break


@hmcore_cmds.command(help="blacklist intents from being triggered by a client", name="blacklist-intent")
@click.argument("intent_id", required=True, type=str)
@click.argument("node_id", required=False, type=int)
def blacklist_intent(intent_id, node_id):
    if not node_id:
        # list clients and prompt for id using rich
        table = Table(title="HiveMind Clients")
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Name", style="magenta")
        table.add_column("Allowed Msg Types", style="yellow")
        _choices = []
        for client in ClientDatabase():
            if client["client_id"] != -1:
                table.add_row(
                    str(client["client_id"]),
                    client["name"],
                    str(client.get("allowed_types", [])),
                )
                _choices.append(str(client["client_id"]))

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

    with ClientDatabase() as db:
        for client in db:
            if client["client_id"] == int(node_id):
                blacklist = client.get("blacklist", {"messages": [], "skills": [], "intents": []})
                if intent_id in blacklist["intents"]:
                    print(f"Client {client['name']} already blacklisted '{intent_id}'")
                    exit()

                blacklist["intents"].append(intent_id)
                client["blacklist"] = blacklist
                item_id = db.get_item_id(client)
                db.update_item(item_id, client)
                print(f"Blacklisted '{intent_id}' for {client['name']}")
                break


@hmcore_cmds.command(help="remove intents from a client blacklist", name="unblacklist-intent")
@click.argument("intent_id", required=True, type=str)
@click.argument("node_id", required=False, type=int)
def unblacklist_intent(intent_id, node_id):
    if not node_id:
        # list clients and prompt for id using rich
        table = Table(title="HiveMind Clients")
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Name", style="magenta")
        table.add_column("Allowed Msg Types", style="yellow")
        _choices = []
        for client in ClientDatabase():
            if client["client_id"] != -1:
                table.add_row(
                    str(client["client_id"]),
                    client["name"],
                    str(client.get("allowed_types", [])),
                )
                _choices.append(str(client["client_id"]))

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

    with ClientDatabase() as db:
        for client in db:
            if client["client_id"] == int(node_id):
                blacklist = client.get("blacklist", {"messages": [], "skills": [], "intents": []})
                if intent_id not in blacklist["intents"]:
                    print(f" '{intent_id}' not blacklisted for Client {client['name']} ")
                    exit()

                blacklist["intents"].pop(intent_id)
                client["blacklist"] = blacklist
                item_id = db.get_item_id(client)
                db.update_item(item_id, client)
                print(f"Blacklisted '{intent_id}' for {client['name']}")
                break


if __name__ == "__main__":
    hmcore_cmds()
