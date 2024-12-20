# HiveMind Core

HiveMind is an extension of [OpenVoiceOS (OVOS)](https://github.com/OpenVoiceOS/), the open-source voice assistant
platform. It enables you to extend a single instance of `ovos-core` across multiple devices, even those with limited
hardware capabilities that can't typically run OVOS.

Demo videos in [youtube](https://www.youtube.com/channel/UCYoV5kxp2zrH6pnoqVZpKSA/)

---

## 🌟 Key Features

- **Expand Your Ecosystem**: Seamlessly connect lightweight or legacy devices as satellites to a central OVOS hub.
- **Centralized Control**: Manage and monitor all connected devices from a single hivemind-core instance.
- **Fine-Grained Permissions**: Control skills, intents, and message access per client.
- **Flexible Database Support**: Choose from JSON, SQLite, or Redis to fit your setup.

---

## 📖 Documentation & Community

- 📚 **Documentation**: [HiveMind Docs (WIP)](https://jarbashivemind.github.io/HiveMind-community-docs)
- 💬 **Chat**: Join the [HiveMind Matrix Chat](https://matrix.to/#/#jarbashivemind:matrix.org) for news, support, and
  discussion.

---

## 🚀 Getting Started

To get started, HiveMind Core provides a command-line interface (CLI) for managing clients, permissions, and
connections.

### Installation

```bash
pip install hivemind-core
```

### Adding a satellite

Add credentials for each satellite device

```bash
$ hivemind-core add-client --db-backend sqlite 
Database backend: SQLiteDB
Credentials added to database!

Node ID: 3
Friendly Name: HiveMind-Node-2
Access Key: 42caf3d2405075fb9e7a4e1ff44e4c4f
Password: 5ae486f7f1c26bd4645bd052e4af3ea3
Encryption Key: f46351c54f61a715
WARNING: Encryption Key is deprecated, only use if your client does not support password
```

**NOTE**: you will need to provide this info on the client devices in order to connect

### Running the Server

Start the HiveMind Core server to accept connections:

```bash
$ hivemind-core listen --port 5678
```

---

## 🛠️ Commands Overview

HiveMind Core CLI supports the following commands:

```bash
$ hivemind-core --help
Usage: hivemind-core [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  add-client          Add credentials for a client.
  allow-msg           Allow specific message types from a client.
  blacklist-intent    Block certain intents for a client.
  blacklist-skill     Block certain skills for a client.
  delete-client       Remove client credentials.
  list-clients        Display a list of registered clients.
  listen              Start listening for HiveMind connections.
  unblacklist-intent  Remove intents from a client's blacklist.
  unblacklist-skill   Remove skills from a client's blacklist.
```

For detailed help on each command, use `--help` (e.g., `hivemind-core add-client --help`).

---

### `add-client`

Add credentials for a new client that will connect to the HiveMind instance.

```bash
$ hivemind-core add-client --name "satellite_1" --access-key "mykey123" --password "mypass" --db-backend json
```

- **When to use**:  
  Use this command when setting up a new HiveMind client device (e.g., a Raspberry Pi or another satellite). You’ll need
  to provide the credentials for secure communication.

---

### `list-clients`

List all the registered clients and their credentials.

```bash
$ hivemind-core list-clients --db-backend json
```

- **When to use**:  
  Use this command to verify which clients are currently registered or to inspect their credentials. This is helpful for
  debugging or managing connected devices.

---

### `delete-client`

Remove a registered client from the HiveMind instance.

```bash
$ hivemind-core delete-client 1
```

- **When to use**:  
  Use this command to revoke access for a specific client. For instance, if a device is lost, no longer in use, or
  compromised, you can remove it to maintain security.

---

### `allow-msg`

Allow specific message types to be sent by a client.

```bash
$ hivemind-core allow-msg "speak"
```

- **When to use**:  
  This command is used to fine-tune the communication protocol by enabling specific message types. This is especially
  useful in scenarios where certain clients should only perform limited actions (e.g., making another device speak via
  TTS).

---

### `blacklist-skill`

Prevent a specific skill from being triggered by a client.

```bash
$ hivemind-core blacklist-skill "skill-weather" 1
```

- **When to use**:  
  Use this command to restrict a client from interacting with a particular skill. For example, a child’s device could be
  restricted from accessing skills that are not age-appropriate.

---

### `unblacklist-skill`

Remove a skill from a client’s blacklist.

```bash
$ hivemind-core unblacklist-skill "skill-weather" 1
```

- **When to use**:  
  If restrictions are no longer needed, use this command to restore access to the blacklisted skill.

---

### `blacklist-intent`

Block a specific intent from being triggered by a client.

```bash
$ hivemind-core blacklist-intent "intent.check_weather" 1
```

- **When to use**:  
  Use this command when fine-grained control is needed to block individual intents for a specific client, especially in
  environments with shared skills but different permission levels.

---

### `unblacklist-intent`

Remove an intent from a client’s blacklist.

```bash
$ hivemind-core unblacklist-intent "intent.check_weather" 1
```

- **When to use**:  
  This command allows you to reinstate access to previously blocked intents.

---

### `listen`

Start the HiveMind instance to accept client connections.

```bash
$ hivemind-core listen --ovos_bus_address "127.0.0.1" --port 5678
```

- **When to use**:  
  Run this command on the central HiveMind instance (e.g., a server or desktop) to start listening for connections from
  satellite devices. Configure host, port, and security options as needed.

---

#### Running in Distributed Environments

By default, HiveMind listens for the OpenVoiceOS bus on `127.0.0.1`. When running in distributed environments (e.g.,
Kubernetes), use the `--ovos_bus_address` and `--ovos_bus_port` options to specify the bus address and port.

---

## 📦 Database Backends

HiveMind-Core supports multiple database backends to store client credentials and settings. Each has its own use case:

| Backend            | Use Case                                       | Default Location                            | Command Line options                               |
|--------------------|------------------------------------------------|---------------------------------------------|----------------------------------------------------|
| **JSON** (default) | Simple, file-based setup for local use         | `~/.local/share/hivemind-core/clients.json` | Configurable via `--db-name` and `--db-folder`     |
| **SQLite**         | Lightweight relational DB for single instances | `~/.local/share/hivemind-core/clients.db`   | Configurable via `--db-name` and `--db-folder`     |
| **Redis**          | Distributed, high-performance environments     | `localhost:6379`                            | Configurable via `--redis-host` and `--redis-port` |

**How to Choose?**

- For **scalability** or multi-instance setups, use Redis.
- For **simplicity** or single-device environments, use JSON or SQLite.

---

## 🔒 Protocol Support

| Feature              | Protocol v0 | Protocol v1 |
|----------------------|-------------|-------------|
| JSON serialization   | ✅           | ✅           |
| Binary serialization | ❌           | ✅           |
| Pre-shared AES key   | ✅           | ✅           |
| Password handshake   | ❌           | ✅           |
| PGP handshake        | ❌           | ✅           |
| Zlib compression     | ❌           | ✅           |

> **Note**: Some clients (e.g., HiveMind-JS) do not yet support Protocol v1.

---

## 🧩 HiveMind Ecosystem

### Minds

You must run at least one of these

- **HiveMind Core** (this repository): The central hub for managing connections and routing messages between devices.
  *text* input only
- [Hivemind Listener](https://github.com/JarbasHiveMind/HiveMind-listener) - an extension of `hivemind-core` for
  streaming *audio* from satellites **<- you likely want this one**
- [Persona](https://github.com/JarbasHiveMind/HiveMind-persona) - run
  a [persona](https://github.com/OpenVoiceOS/ovos-persona) (eg. LLM). *text* input only

### Client Libraries

- [HiveMind WebSocket Client](https://github.com/JarbasHiveMind/hivemind_websocket_client)
- [HiveMind JS](https://github.com/JarbasHiveMind/HiveMind-js)

### Terminals

- [Voice Satellite](https://github.com/OpenJarbas/HiveMind-voice-sat)  (standalone OVOS *local* audio stack)
- [Voice Relay](https://github.com/JarbasHiveMind/HiveMind-voice-relay)  (lightweight audio satellite, STT/TTS
  processed *server* side, **requires** `hivemind-listener`)
- [Mic Satellite](https://github.com/JarbasHiveMind/hivemind-mic-satellite) (only VAD runs on device, audio streamed
  and fully processed *server* side, **requires** `hivemind-listener`)
- [Web Chat](https://github.com/OpenJarbas/HiveMind-webchat) (*client-side* browser hivemind connection)
- [Flask Chatroom](https://github.com/JarbasHiveMind/HiveMind-flask-template)  (**boilerplate template** - *server-side*
  hivemind connection)

### Bridges

- [Mattermost Bridge](https://github.com/OpenJarbas/HiveMind_mattermost_bridge)
- [DeltaChat Bridge](https://github.com/JarbasHiveMind/HiveMind-deltachat-bridge)

---

## Voice Satellite Comparison

| Feature                            | **HiveMind Voice Satellite**               | **HiveMind Voice Relay**                                                                  | **HiveMind Microphone Satellite**                            |
|------------------------------------|--------------------------------------------|-------------------------------------------------------------------------------------------|--------------------------------------------------------------|
| **Use Case**                       | Full voice satellite with local processing | Offloads voice processing to **HiveMind Listener**, better suited for secure environments | Super lightweight satellite for fully remote audio streaming |
| **Audio Processing**               | Local (STT, TTS, Wake Word, VAD)           | STT and TTS handled on **HiveMind Listener**                                              | Wake Word, STT and TTS handled on **HiveMind Listener**      |
| **Server Requirements**            | Works with **all** mind implementations    | Requires **hivemind-listener**                                                            | Requires **hivemind-listener**                               |
| **Voice Activity Detection (VAD)** | Handled locally                            | Handled locally                                                                           | Handled locally                                              |
| **Wake Word Detection**            | Handled locally                            | Handled locally                                                                           | Handled by **HiveMind Listener**                             |
| **STT Processing**                 | Handled locally                            | Handled by **HiveMind Listener**                                                          | Handled by **HiveMind Listener**                             |
| **TTS Processing**                 | Handled locally                            | Handled by **HiveMind Listener**                                                          | Handled by **HiveMind Listener**                             |
| **Media Playback Support**         | Yes, with supported plugins                | Yes, with supported plugins                                                               | No                                                           |
| **PHAL plugins**                   | Supported                                  | Supported                                                                                 | Unsupported                                                  |
| **Transformer plugins**            | Supported                                  | Supported                                                                                 | Unsupported                                                  |

---

## 🤝 Contributing

Contributions are welcome!

---

## ⚖️ License

HiveMind is open-source software, licensed under the [Apache 2.0 License](LICENSE).


