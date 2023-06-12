<p align="center">
  <img src="https://github.com/JarbasHiveMind/HiveMind-assets/raw/master/logo/hivemind-512.png">
</p>

HiveMind is a community-developed superset or extension of [Mycroft](https://www.github.com/MycroftAI/mycroft-core), the open-source voice assistant.

With HiveMind, you can extend one (or more, but usually just one!) instance of Mycroft to as many devices as you want, including devices that can't ordinarily run Mycroft!

HiveMind's developers have successfully connected to Mycroft from a PinePhone, a 2009 MacBook, and a Raspberry Pi 0, among other devices. Mycroft itself usually runs on our desktop computers or our home servers, but you can use any Mycroft-branded device, or [OpenVoiceOS](https://github.com/OpenVoiceOS/), as your central unit.

Work in progress documentation can be found in the [wiki](https://github.com/JarbasHiveMind/HiveMind-core/wiki)

You can also join the [Hivemind Matrix chat](https://matrix.to/#/#jarbashivemind:matrix.org) for general news, support and chit chat

# Usage

```
hivemind-core --help
Usage: hivemind-core [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  add-keys       add a device and keys
  delete-device  remove a device
  list-keys      list devices and keys
  listen         start listening for HiveMind connections
```

# HiveMind components

![](./resources/1m5s.svg)

## Client Libraries

- [HiveMind-websocket-client](https://github.com/JarbasHiveMind/hivemind_websocket_client)
- [HiveMindJs](https://github.com/JarbasHiveMind/HiveMind-js)

## Terminals

- [Remote Cli](https://github.com/OpenJarbas/HiveMind-cli) **\<-- USE THIS FIRST**
- [Voice Satellite](https://github.com/OpenJarbas/HiveMind-voice-sat)
- [Flask Chatroom](https://github.com/JarbasHiveMind/HiveMind-flask-template)
- [Webchat](https://github.com/OpenJarbas/HiveMind-webchat)

## Bridges

- [Mattermost Bridge](https://github.com/OpenJarbas/HiveMind_mattermost_bridge)
- [HackChat Bridge](https://github.com/OpenJarbas/HiveMind-HackChatBridge)
- [Twitch Bridge](https://github.com/OpenJarbas/HiveMind-twitch-bridge)
- [DeltaChat Bridge](https://github.com/JarbasHiveMind/HiveMind-deltachat-bridge)

## Minds

- [NodeRed](https://github.com/OpenJarbas/HiveMind-NodeRed)

