import json
# If sqlalchemy not installed will fallback to json based database
from sqlalchemy import Column, Text, String, Integer, create_engine, Boolean
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base


from ovos_utils.log import LOG
from jarbas_hive_mind.configuration import CONFIGURATION

Base = declarative_base()


def model_to_dict(obj):
    serialized_data = {c.key: getattr(obj, c.key) for c in obj.__table__.columns}
    return serialized_data


def props(cls):
    return [i for i in cls.__dict__.keys() if i[:1] != '_']


class Client(Base):
    __tablename__ = "clients"
    client_id = Column(Integer, primary_key=True)
    description = Column(Text)
    api_key = Column(String)
    name = Column(String)
    crypto_key = Column(String)
    last_seen = Column(Integer, default=0)
    is_admin = Column(Boolean, default=False)
    blacklist = Column(Text)  # json string


class SQLClientDatabase:
    def __init__(self, path=CONFIGURATION["database"], debug=False, session=None):
        self.db = create_engine(path)
        self.db.echo = debug
        if session:
            self.session = session
        else:
            Session = sessionmaker(bind=self.db)
            self.session = Session()
        Base.metadata.create_all(self.db)

    def update_timestamp(self, key, timestamp):
        user = self.get_client_by_api_key(key)
        if not user:
            return False
        user.last_seen = timestamp
        return True

    def delete_client(self, key):
        user = self.get_client_by_api_key(key)
        if user:
            self.session.delete(user)
            return True
        return False

    def change_key(self, old_key, new_key):
        user = self.get_client_by_api_key(old_key)
        if not user:
            return False
        user.api_key = new_key
        return True

    def change_crypto_key(self, api_key, new_key):
        user = self.get_client_by_api_key(api_key)
        if not user:
            return False
        user.crypto_key = new_key
        return True

    def change_name(self, new_name, key):
        user = self.get_client_by_api_key(key)
        if not user:
            return False
        user.name = new_name
        return True

    def change_blacklist(self, blacklist, key):
        if isinstance(blacklist, dict):
            blacklist = json.dumps(blacklist)
        user = self.get_client_by_api_key(key)
        if not user:
            return False
        user.blacklist = blacklist
        return True

    def get_blacklist_by_api_key(self, api_key):
        user = self.session.query(Client).filter_by(api_key=api_key).first()
        return json.loads(user.blacklist)

    def get_client_by_api_key(self, api_key):
        return self.session.query(Client).filter_by(api_key=api_key).first()

    def get_client_by_name(self, name):
        return self.session.query(Client).filter_by(name=name).all()

    def get_crypto_key(self, api_key):
        user = self.get_client_by_api_key(api_key)
        if not user:
            return None
        return user.crypto_key

    def add_client(self, name=None, key="", admin=False,
                   blacklist="{}", crypto_key=None):
        if isinstance(blacklist, dict):
            blacklist = json.dumps(blacklist)

        user = self.get_client_by_api_key(key)
        if crypto_key is not None:
            crypto_key = crypto_key[:16]
        if user:
            user.name = name
            user.blacklist = blacklist
            user.is_admin = admin
            user.crypto_key = crypto_key if crypto_key else user.crypto_key
        else:
            user = Client(api_key=key, name=name,
                          blacklist=blacklist, crypto_key=crypto_key,
                          client_id=self.total_clients() + 1,
                          is_admin=admin)
            self.session.add(user)

    def total_clients(self):
        return self.session.query(Client).count()

    def commit(self):
        try:
            self.session.commit()
            return True
        except IntegrityError:
            self.session.rollback()
        return False

    def close(self):
        self.session.close()

    def __enter__(self):
        """ Context handler """
        return self

    def __exit__(self, _type, value, traceback):
        """ Commits changes and Closes the session """
        try:
            self.commit()
        except Exception as e:
            LOG.error(e)
        finally:
            self.close()
