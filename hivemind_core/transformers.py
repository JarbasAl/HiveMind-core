from typing import Optional, List
from typing import Tuple

from ovos_bus_client.session import Session, SessionManager
from ovos_config import Configuration
from ovos_plugin_manager.dialog_transformers import find_dialog_transformer_plugins
from ovos_plugin_manager.metadata_transformers import find_metadata_transformer_plugins
from ovos_plugin_manager.text_transformers import find_utterance_transformer_plugins
from ovos_utils.json_helper import merge_dict
from ovos_utils.log import LOG


class DialogTransformersService:
    """ transform dialogs before being sent to TTS """

    def __init__(self, bus, config=None):
        self.loaded_plugins = {}
        self.has_loaded = False
        self.bus = bus
        # to activate a plugin, just add an entry to mycroft.conf for it
        self.config = config or Configuration().get("dialog_transformers", {})
        self.load_plugins()

    @property
    def blacklisted_skills(self):
        # dialog should NEVER be rewritten if it comes from these skills
        return self.config.get("blacklisted_skills",
                               ["skill-ovos-icanhazdadjokes.openvoiceos"]  # blacklist jokes by default
                               )

    def load_plugins(self):
        for plug_name, plug in find_dialog_transformer_plugins().items():
            if plug_name in self.config:
                # if disabled skip it
                if not self.config[plug_name].get("active", True):
                    continue
                try:
                    self.loaded_plugins[plug_name] = plug(config=self.config[plug_name])
                    self.loaded_plugins[plug_name].bind(self.bus)
                    LOG.info(f"loaded audio transformer plugin: {plug_name}")
                except Exception as e:
                    LOG.exception(f"Failed to load dialog transformer plugin: "
                                  f"{plug_name}")
        self.has_loaded = True

    @property
    def plugins(self) -> list:
        """
        Return loaded transformers in priority order, such that modules with a
        higher `priority` rank are called first and changes from lower ranked
        transformers are applied last.

        A plugin of `priority` 1 will override any existing context keys and
        will be the last to modify `audio_data`
        """
        return sorted(self.loaded_plugins.values(),
                      key=lambda k: k.priority, reverse=True)

    def shutdown(self):
        """
        Shutdown all loaded plugins
        """
        for module in self.plugins:
            try:
                module.shutdown()
            except Exception as e:
                LOG.warning(e)

    def transform(self, dialog: str, context: dict = None, sess: Session = None) -> Tuple[str, dict]:
        """
        Get transformed audio and context for the preceding audio
        @param dialog: str to be spoken
        @return: transformed dialog to be sent to TTS
        """

        # TODO property not yet introduced in Session
        sess = sess or SessionManager.get()
        # if isinstance(sess, dict):
        #    sess = Session.deserialize(sess)
        # active_transformers = sess.dialog_transformers or self.plugins

        active_transformers = self.plugins

        for module in active_transformers:
            try:
                LOG.debug(f"checking dialog transformer: {module}")
                dialog, context = module.transform(dialog, context=context)
                LOG.debug(f"{module.name}: {dialog}")
            except Exception as e:
                LOG.exception(e)
        return dialog, context


class UtteranceTransformersService:

    def __init__(self, bus, config=None):
        self.config_core = config or {}
        self.loaded_plugins = {}
        self.has_loaded = False
        self.bus = bus
        self.config = self.config_core.get("utterance_transformers") or {}
        self.load_plugins()

    def load_plugins(self):
        for plug_name, plug in find_utterance_transformer_plugins().items():
            if plug_name in self.config:
                # if disabled skip it
                if not self.config[plug_name].get("active", True):
                    continue
                try:
                    self.loaded_plugins[plug_name] = plug()
                    LOG.info(f"loaded utterance transformer plugin: {plug_name}")
                except Exception as e:
                    LOG.error(e)
                    LOG.exception(f"Failed to load utterance transformer plugin: {plug_name}")

    @property
    def plugins(self):
        """
        Return loaded transformers in priority order, such that modules with a
        higher `priority` rank are called first and changes from lower ranked
        transformers are applied last

        A plugin of `priority` 1 will override any existing context keys and
        will be the last to modify utterances`
        """
        return sorted(self.loaded_plugins.values(),
                      key=lambda k: k.priority, reverse=True)

    def shutdown(self):
        for module in self.plugins:
            try:
                module.shutdown()
            except:
                pass

    def transform(self, utterances: List[str], context: Optional[dict] = None):
        context = context or {}

        for module in self.plugins:
            try:
                utterances, data = module.transform(utterances, context)
                _safe = {k: v for k, v in data.items() if k != "session"}  # no leaking TTS/STT creds in logs
                LOG.debug(f"{module.name}: {_safe}")
                context = merge_dict(context, data)
            except Exception as e:
                LOG.warning(f"{module.name} transform exception: {e}")
        return utterances, context


class MetadataTransformersService:

    def __init__(self, bus, config=None):
        self.config_core = config or {}
        self.loaded_plugins = {}
        self.has_loaded = False
        self.bus = bus
        self.config = self.config_core.get("metadata_transformers") or {}
        self.load_plugins()

    def load_plugins(self):
        for plug_name, plug in find_metadata_transformer_plugins().items():
            if plug_name in self.config:
                # if disabled skip it
                if not self.config[plug_name].get("active", True):
                    continue
                try:
                    self.loaded_plugins[plug_name] = plug()
                    LOG.info(f"loaded metadata transformer plugin: {plug_name}")
                except Exception as e:
                    LOG.error(e)
                    LOG.exception(f"Failed to load metadata transformer plugin: {plug_name}")

    @property
    def plugins(self):
        """
        Return loaded transformers in priority order, such that modules with a
        higher `priority` rank are called first and changes from lower ranked
        transformers are applied last.

        A plugin of `priority` 1 will override any existing context keys
        """
        return sorted(self.loaded_plugins.values(),
                      key=lambda k: k.priority, reverse=True)

    def shutdown(self):
        for module in self.plugins:
            try:
                module.shutdown()
            except:
                pass

    def transform(self, context: Optional[dict] = None):
        context = context or {}

        for module in self.plugins:
            try:
                data = module.transform(context)
                _safe = {k: v for k, v in data.items() if k != "session"}  # no leaking TTS/STT creds in logs
                LOG.debug(f"{module.name}: {_safe}")
                context = merge_dict(context, data)
            except Exception as e:
                LOG.warning(f"{module.name} transform exception: {e}")
        return context
