import logging
import random
from os import makedirs
from os.path import exists, join
from socket import gethostname

from OpenSSL import crypto
import json
from jarbas_hive_mind.settings import CERTS_PATH, LOG_BLACKLIST
from jarbas_hive_mind.exceptions import DecryptionKeyError, EncryptionKeyError
from ovos_utils.log import LOG
from ovos_utils.security import encrypt, decrypt
from binascii import hexlify, unhexlify

# TODO ovos_utils for all of these
# this used to be a method here, keep here for now in case something is
# importing it, TODO deprecate
from ovos_utils import get_ip


def validate_param(value, name):
    if not value:
        raise ValueError("Missing or empty %s in conf " % name)


def create_self_signed_cert(cert_dir=CERTS_PATH, name="jarbas_hivemind"):
    """
    If name.crt and name.key don't exist in cert_dir, create a new
    self-signed cert and key pair and write them into that directory.
    """

    CERT_FILE = name + ".crt"
    KEY_FILE = name + ".key"
    cert_path = join(cert_dir, CERT_FILE)
    key_path = join(cert_dir, KEY_FILE)

    if not exists(join(cert_dir, CERT_FILE)) \
            or not exists(join(cert_dir, KEY_FILE)):
        # create a key pair
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, 2048)

        # create a self-signed cert
        cert = crypto.X509()
        cert.get_subject().C = "PT"
        cert.get_subject().ST = "Europe"
        cert.get_subject().L = "Mountains"
        cert.get_subject().O = "Jarbas AI"
        cert.get_subject().OU = "Powered by Mycroft-Core"
        cert.get_subject().CN = gethostname()
        cert.set_serial_number(random.randint(0, 2000))
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(k)
        cert.sign(k, 'sha1')
        if not exists(cert_dir):
            makedirs(cert_dir)
        open(cert_path, "wb").write(
            crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        open(join(cert_dir, KEY_FILE), "wb").write(
            crypto.dump_privatekey(crypto.FILETYPE_PEM, k))

    return cert_path, key_path


def create_echo_function(name, whitelist=None):
    """ Standard logging mechanism for Mycroft processes.

    This handles the setup of the basic logging for all Mycroft
    messagebus-based processes.

    Args:
        name (str): Reference name of the process
        whitelist (list, optional): List of "type" strings.  If defined, only
                                    messages in this list will be logged.

    Returns:
        func: The echo function
    """
    blacklist = LOG_BLACKLIST

    def echo(message):
        global _log_all_bus_messages
        try:
            msg = json.loads(message)

            if whitelist and msg.get("type") not in whitelist:
                return

            if blacklist and msg.get("type") in blacklist:
                return

            if msg.get("type") == "mycroft.debug.log":
                # Respond to requests to adjust the logger settings
                lvl = msg["data"].get("level", "").upper()
                if lvl in ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]:
                    LOG.level = lvl
                    LOG(name).info("Changing log level to: {}".format(lvl))
                    try:
                        logging.getLogger('urllib3').setLevel(lvl)
                    except Exception:
                        pass  # We don't really care about if this fails...

                # Allow enable/disable of messagebus traffic
                log_bus = msg["data"].get("bus", None)
                if log_bus is not None:
                    LOG(name).info("Bus logging: " + str(log_bus))
                    _log_all_bus_messages = log_bus
            elif msg.get("type") == "registration":
                # do not log tokens from registration messages
                msg["data"]["token"] = None
                message = json.dumps(msg)
        except Exception:
            pass

        if _log_all_bus_messages:
            # Listen for messages and echo them for logging
            LOG(name).debug(message)

    return echo


def serialize_message(message):
    # convert a Message object into raw data that can be sent over
    # websocket
    if hasattr(message, 'serialize'):
        return message.serialize()
    elif isinstance(message, dict):
        message = {k: v if not hasattr(v, 'serialize') else serialize_message(v)
                   for k, v in message.items()}
        return json.dumps(message)
    else:
        return json.dumps(message.__dict__)


def encrypt_as_json(key, data, nonce=None):
    if isinstance(data, dict):
        data = json.dumps(data)
    if len(key) > 16:
        key = key[0:16]
    try:
        ciphertext, tag, nonce = encrypt(key, data, nonce=nonce)
    except:
        raise EncryptionKeyError
    return json.dumps({"ciphertext": hexlify(ciphertext).decode('utf-8'),
            "tag": hexlify(tag).decode('utf-8'),
            "nonce": hexlify(nonce).decode('utf-8')})


def decrypt_from_json(key, data):
    if isinstance(data, str):
        data = json.loads(data)
    if len(key) > 16:
        key = key[0:16]
    ciphertext = unhexlify(data["ciphertext"])
    if data.get("tag") is None:  # web crypto
        ciphertext, tag = ciphertext[:-16], ciphertext[-16:]
    else:
        tag = unhexlify(data["tag"])
    nonce = unhexlify(data["nonce"])
    try:
        return decrypt(key, ciphertext, tag, nonce)
    except ValueError:
        raise DecryptionKeyError
