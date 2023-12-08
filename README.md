# FLEYBACH Agent ![Latest Stable Version](https://img.shields.io/github/v/release/florianschleuss/fleybach-agent) ![Repository Size](https://img.shields.io/github/repo-size/florianschleuss/fleybach-agent) ![License](https://img.shields.io/github/license/florianschleuss/fleybach-agent)

#### Table of Contents

1. [SocketIO Communication Scheme](#socketio-communication-scheme)
2. [License](#license)

## SocketIO Communication Scheme

Basic Instruction with [Wikipedia](https://de.wikipedia.org/).

WS 'task' event data scheme

```json
{
  "deviceId": "heat_pump",
  "action": "on",
  "args": {
    "user": "flo", 
    "state": false, 
    "delay": 10
    }
}
```

Function Catalog

```python
Action.SWITCH
Action.ON
Action.OFF
Action.TIMER
Action.STATE
```

## License

The Repository is licensed under the terms of the [GPL Open Source](LICENSE) license and is available for free.
