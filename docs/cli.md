# Commandline Interface

## Setup

First, run `pishock init` to supply your PiShock.com username and [API key](https://pishock.com/#/account):

```console
$ pishock init
👤 PiShock username (your own username): Zerario
🔑 PiShock API key (https://pishock.com/#/account): 964f1513-c76a-48cc-82d4-41e757d4eb04
✅ Credentials saved.
```

This saves the credentials in a config file in an appropriate location for your
system (e.g. `~/.config/PiShock-CLI/config.json` on a typical Linux setup).

Alternatively, you can set `PISHOCK_API_USER` and `PISHOCK_API` in your
environment, or use the `--username` and `--api-key` arguments for every
invocation.

`pishock init` automatically will verify that the credentials are correct, but
`pishock verify` can also be used to do so manually.

## Basic usage

After setting up credentials, it's recommended to
[save your share code](#managing-share-codes) for easier usage:

```console
$ pishock code add my-shocker ABCDEF12345
✅  my-shocker    ABCDEF12345  1001
```

Finally, send e.g. a vibrate:

```console
$ pishock vibrate my-shocker --duration 1 --intensity 20
📳
```

Similarly, `shock` and `beep` can be used in place of `vibrate` (with `beep` not
having an `--intensity`).

```console
$ pishock shock my-shocker -d 1 -i 20
⚡

$ pishock beep my-shocker -d 1
🔊
```

(managing-share-codes)=
## Managing share codes

The CLI stores a list of known share codes in its config. When you add a new
share code using `pishock code add NAME CODE`, it will ensure the share code is
valid, and save the code plus the associated shocker ID:

```console
$ pishock code add my-shocker ABCDEF12345
✅  my-shocker    ABCDEF12345  1001
```

In subsequent operations such as `pishock vibrate`, you can now use the name
`my-shocker` in place of a share code. If you plan to use this CLI for shocking
other people as well, consider using a naming convention such as
`some-cutie/shocker1`.

Once you added your share codes, use `pishock code list` to show them:

```console
$ pishock code list
🔗  my-shocker     ABCDEF12345  1001
🔗  other-shocker  ABC123DEF45  1002
```

add `--info` to show information gathered from the API for the entire list:

```console
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Name          ┃ Share code  ┃ Shocker Name ┃ PiShock ID ┃ Shocker ID ┃ Paused ┃ Max intensity ┃ Max duration ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ my-shocker    │ ABCDEF12345 │ shocker1     │ 621        │ 1001       │ ▶      │ 100%          │ 15s          │
│ other-shocker │ ABC123DEF45 │ shocker2     │ 621        │ 1002       │ ▶      │ 100%          │ 15s          │
└───────────────┴─────────────┴──────────────┴────────────┴────────────┴────────┴───────────────┴──────────────┘
```

A saved code can be removed via `pishock code del NAME`, and renamed via `pishock code rename OLD NEW`.

## Other operations

A shocker can be paused and unpaused via `pishock pause SHOCKER` and `pishock unpause SHOCKER`.

Information about a shocker can be shown via `pishock info SHOCKER`:

```console
$ pishock info my-shocker
┌───────────────┬──────────┐
│ Name          │ shocker1 │
│ PiShock ID    │ 621      │
│ Shocker ID    │ 1001     │
│ Paused        │ ▶        │
│ Max intensity │ 100%     │
│ Max duration  │ 15s      │
└───────────────┴──────────┘
```

A list of all shockers associated with a given PiShock can be shown with
`pishock shockers ID`, with `ID` being the ID of the PiShock:

```
$ pishock shockers 621
1001: shocker1 ▶
1002: shocker2 ▶
```

## Random mode

For some unpredictable fun, random mode can be used to send shocks to random
shockers, with a random duration and intensity:

```console
$ pishock random shocker1 shocker2 --duration 1-15 --intensity 30-100 --pause 5-30
⚡ Shocking shocker1 for 9s at 82%.
💤 Sleeping for 15 seconds.
⚡ Shocking shocker2 for 14s at 55%.
💤 Sleeping for 10 seconds.
⚡ Shocking shocker2 for 4s at 89%.
💤 Sleeping for 15 seconds.
```

All of `-d` / `--duration`, `-i` / `--intensity` and `-p` / `--pause` are
required, and will be randomly picked from the given `min-max` range.

By default, only shocks are sent. To also send random vibrations, add
`--vibrate`, optionally with a separate `--vibration-duration` and
`--vibrate-intensity` (which, if not given, default to `--duration` and
`--intensity`). To only send vibrations, add `--no-shock`.

A `--max-runtime` can be given (e.g. `--max-runtime 1h`) to automatically
terminate the script after the given duration. With a `min-max` range, it is
picked at random.

With an `--initial-delay` (same values as with `--max-runtime`), the tool sleeps
before the first operation. The initial delay will not be part of the maximium
runtime.

For some extra fun, a `--spam-possibility` in percent can be given. For every
random operation, there is the given possibility of entering "spam mode", where
a random amount of shocks are sent in rapid succession. The following arguments
can be used to customize the behavior (default values are shown):

- `--spam-operations 5-25`: How many shocks to send before returning to normal
  operation
- `--spam-pause 0-0`: Additional pause between spam shocks (by default, 0.3s
  delay after the shock duration is used to ensure API operations arrive
  correctly)
- `--spam-duration 1-1`: Duration for spam shocks
- `--spam-intensity`: Intensity for spam shocks (by default, the given
  `--intensity` is used)

## Session mode

To schedule shock, spam, vibrate and beep events over a session, the session
command takes a json file as input allowing automation of multiple shockers for
completely handsfree use.

```console
$ pishock session examples/session.json
✔ Validating events
✔ Event list is valid
▶ Session started
🟩  Count in mode is set to beep
🔔 Beeping shocker1 for 1s
🔔 Beeping shocker1 for 1s
🔔 Beeping shocker1 for 1s
🕐 Max runtime is 3600 seconds
🕐 Spam Cooldown is 120 seconds
⚡ Shocking shocker1 for 9s at 82%
⚡ Shocking shocker2 for 14s at 55%
```

Following similar field names to the random mode, the JSON format is as follows:

```js
{
  "shocker_names": ["shocker-1", "shocker-2"], // cli shocker names
  "max_runtime": "1h", // automatically end the session (default 1h inclusive of init_delay)
  "init_delay": "2m", // delay the start of the script
  "spam_cooldown": "2m", // limit how much you can be spammed
  "count_in_mode": "beep", // if specified, the script will count down to session start
  "events": [ // a list of events. add as many breakpoints as needed
    {
      "time": "0", // a time in seconds for when the session changes
      "sync_mode": "sync", // random-shocker, sync, round-robin, dealers-choice
      "break_duration": "1-10", // add spaces between shocker operations
      "vibrate": { // by default, the program will vibe randomly between events
        "intensity": "20-60", // intensity out of 100
        "duration": "1-6" // duration in seconds (1-15)
      },
      "shock": {
        "possibility": 15, // the percent chance of this event happening
        "intensity": "3-8",
        "duration": "1-6"
      },
      "spam": {
        "possibility": 1,
        "operations": "10-20", // how many times to send the shocks consecutively
        "intensity": "3-5",
        "duration": "1-2",
        "delay": 0.3 // delay in seconds between spammed shocks
      },
      "beep": {
        "possibility": 5,
        "duration": "1-6"
      }
    },
    {
      "time": "60s", // the session will change after the specified time
      "sync_mode": "random-shocker", // change the way your shockers are chosen with each step
      "vibrate": {
        "possibility": 5,
        "intensity": "70-90",
        "duration": "3-6"
      }
      "shock": {
        "possibility": 5,
        "intensity": "1-2",
        "duration": "12-15"
      }
  },
  ... // define as many events as needed
  ]
}
```

## Serial usage

When a PiShock is attached via USB, the commands `shock`, `vibrate`, `beep` and
`info` can be used with `pishock --serial` to communicate over serial rather
than using the HTTP API.

Instead of taking a share code to specify which shocker to operate, commands
take a shocker ID as shown on the PiShock website. Share codes can still be
specified in place of a shocker ID, but this results in an additional HTTP
request to map it to a shocker ID. When adding a share code via `pishock code
add`, the shocker ID is automatically retrieved and stored in the config, so
that saved share codes can be used either with or without `--serial`, without an
additional request being necessary.

Auto-detection of attached PiShock devices is attempted. If no device was found,
or multiple were found, add `--port` to specify the port to use:

```console
$ pishock --serial --port /dev/ttyUSB1 vibrate -d 1 -i 1 1001
📳
```

Additional serial operations are available via `pishock serial COMMAND` (no `--serial` flag is needed in this case, though `--port` might be):

### Network management

- `pishock serial add-network SSID PASSWORD` and
  `pishock serial remove-network SSID` to manage WiFi networks stored on the device.
- `pishock serial try-connect SSID PASSWORD` to temporarily connect to the given network.

### Other

- `pishock serial info` to show information about the device (`--show-passwords` to show WiFi passwords; `--raw` to show raw data, `--debug` to show the received data while waiting for an answer).
- `pishock serial monitor` to show serial logs, while adding syntax highlighting and rendering any info responses
- `pishock serial reboot` to restart the PiShock

### Firmware upgrade

After installing the optional `esptool` dependency (`pip install esptool`), `pishock serial flash TYPE` can be used to upgrade your PiShock to the latest firmware, with `TYPE` being one of:

- `v1-lite`: Old V1 firmware on a PiShock Lite (older hardware with microUSB)
- `v1-next`: Old V1 firmware on a PiShock Next (newer hardware with USB-C)
- `v3-lite`: New V3 firmware on a PiShock Lite (older hardware with microUSB)
- `v3-next`: New V3 firmware on a PiShock Next (newer hardware with USB-C)
- `vault`: PiVault firmware (currently untested!)

By default, it's expected that the PiShock already runs correctly, and the given
type is checked against the reported hardware. If no firmware is currently
installed already, `--no-check` will be needed to skip that check.

Networks currently saved on the PiShock are saved before the upgrade, and then
it's attempted to restore them afterwards. `--no-restore-networks` can be used
to not restore existing network credentials.
