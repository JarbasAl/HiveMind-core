from hivemind_core.database import ClientDatabase

name = "JarbasCliTerminal"
key = "RESISTENCEisFUTILE"
crypto_key = "resistanceISfutile"


with ClientDatabase() as db:
    db.add_client(name, key, crypto_key=crypto_key)
