from jarbas_hive_mind import get_listener
from jarbas_hive_mind.configuration import CONFIGURATION

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Start HiveMind as a server')
    parser.add_argument("--name", help="human readable name")
    parser.add_argument("--access_key", help="access key")
    parser.add_argument("--crypto_key", help="payload encryption key")
    parser.add_argument("--mail", help="human readable mail")
    parser.add_argument("--port", help="HiveMind port number")
    args = parser.parse_args()
    # Check if a user was defined
    if args.name is not None:
        from jarbas_hive_mind.database import ClientDatabase
        with ClientDatabase() as db:
            db.add_client(args.name, args.mail, args.access_key, crypto_key=args.crypto_key)
    config = config or CONFIGURATION
    listener = get_listener()
    listener.load_config(config)
    # Replace defined values
    if args.port is not None:
        listener.port = int(args.port)
    listener.listen()

if __name__ == '__main__':
    main()
