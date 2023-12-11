import json
from typing import Optional, Any, Dict

from typing_extensions import Annotated
import rich
import rich.console
import rich.pretty
import rich.text
import rich.box
import typer
import serial  # type: ignore[import-not-found]
import serial.tools.list_ports  # type: ignore[import-not-found]

from pishock import cli_utils

"""Serial interface commands for PiShock."""

app = typer.Typer(no_args_is_help=True)
serial_port = None

DEVICE_TYPES = {3: "Lite", 4: "Next"}
SHOCKER_TYPES = {0: "SmallOne", 1: "Petrainer"}
INFO_PREFIX = b"TERMINALINFO: "
USB_IDS = [
    (0x1A86, 0x7523),  # CH340, PiShock Next
    (0x1A86, 0x55D4),  # CH9102, PiShock Lite
]


def _build_cmd(cmd: str, value: Any = None) -> bytes:
    data = {"cmd": cmd}
    if value:
        data["value"] = value
    doc = json.dumps(data) + "\n"
    return doc.encode("utf-8")  # FIXME encoding?


def _enrich_toplevel_data(data: Dict[str, Any], show_passwords: bool) -> None:
    """Adjust some data for nicer display."""
    if "networks" in data:
        networks = rich.table.Table(box=rich.box.ROUNDED)
        networks.add_column("ssid")
        networks.add_column("password")
        for net in data["networks"]:
            ssid = net.get("ssid")
            password = (
                net.get("password")
                if show_passwords
                else rich.text.Text(
                    "(use --show-passwords to show)", style="bright_black"
                )
            )
            networks.add_row(ssid, password)
        data["networks"] = networks

    if "shockers" in data:
        shockers = rich.table.Table(box=rich.box.ROUNDED)
        shockers.add_column("id")
        shockers.add_column("type")
        shockers.add_column("paused")
        for shocker in data["shockers"]:
            shocker_type = shocker.get("type")
            if shocker_type is not None and shocker_type in SHOCKER_TYPES:
                text = rich.text.Text(str(shocker_type))
                text.append(f" ({SHOCKER_TYPES[shocker_type]})", style="bright_black")
                shocker_type = text

            shockers.add_row(
                rich.pretty.Pretty(shocker.get("id")),
                shocker_type,
                cli_utils.bool_emoji(shocker.get("paused")),
            )
        data["shockers"] = shockers

    pishock_type = data.get("type")
    if pishock_type is not None and pishock_type in DEVICE_TYPES:
        text = rich.text.Text(str(pishock_type))
        text.append(f" ({DEVICE_TYPES[pishock_type]})", style="bright_black")
        data["type"] = text


def _json_to_rich(data: Dict[str, Any]) -> rich.console.RenderableType:
    if isinstance(data, bool):
        return cli_utils.bool_emoji(data)
    elif isinstance(data, list):
        return rich.console.Group(*[_json_to_rich(e) for e in data])
    elif isinstance(data, dict):
        table = rich.table.Table(show_header=False)
        table.add_column(style="bold")
        table.add_column()

        for k, v in sorted(data.items()):
            table.add_row(k, _json_to_rich(v))

        return table
    elif isinstance(data, str):
        return data
    elif isinstance(data, rich.console.RenderableType):
        return data
    else:
        return rich.pretty.Pretty(data)


@app.command()
def info(
    show_passwords: Annotated[
        bool, typer.Option(help="Don't conceal WiFi passwords")
    ] = False
) -> None:
    """Show information about this PiShock."""
    assert serial_port is not None
    serial_port.write(_build_cmd("info"))
    data = _wait_device_info()
    _enrich_toplevel_data(data, show_passwords=show_passwords)
    rich.print(_json_to_rich(data))


def _wait_device_info() -> Dict[str, Any]:
    assert serial_port is not None
    while True:
        line = serial_port.readline()
        if line.startswith(INFO_PREFIX):
            break

    return json.loads(line[len(INFO_PREFIX) :])


@app.command()
def add_network(ssid: str, password: str) -> None:
    """Add a new network to the PiShock config and reboot."""
    assert serial_port is not None
    serial_port.write(_build_cmd("addnetwork", {"ssid": ssid, "password": password}))
    data = _wait_device_info()
    _enrich_toplevel_data(data, show_passwords=False)
    rich.print(_json_to_rich(data["networks"]))


@app.command()
def remove_network(ssid: str) -> None:
    """Remove a network from the PiShock config."""
    assert serial_port is not None
    serial_port.write(_build_cmd("removenetwork", ssid))
    data = _wait_device_info()
    _enrich_toplevel_data(data, show_passwords=False)
    rich.print(_json_to_rich(data["networks"]))


@app.command()
def try_connect(ssid: str, password: str) -> None:
    """Temporarily try connecting to the given network."""
    assert serial_port is not None
    serial_port.write(_build_cmd("connect", ssid))


@app.command()
def restart() -> None:
    """Restart the PiShock."""
    assert serial_port is not None
    serial_port.write(_build_cmd("restart"))


@app.command()
def monitor() -> None:
    """Monitor serial output."""
    assert serial_port is not None
    while True:
        line = serial_port.readline()
        rich.print(line.decode("utf-8", errors="replace"), end="")
        if line.startswith(INFO_PREFIX):
            try:
                info = json.loads(line[len(INFO_PREFIX) :])
            except json.JSONDecodeError:
                pass
            else:
                rich.print(_json_to_rich(info))


def _autodetect_port() -> str:
    candidates = []
    for info in serial.tools.list_ports.comports():
        if (info.vid, info.pid) in USB_IDS:
            candidates.append(info.device)

    if len(candidates) == 1:
        return candidates[0]
    elif not candidates:
        raise typer.Exit("No PiShock found via port autodetection.")
    else:
        raise typer.Exit(
            "Multiple (possibly) PiShocks found via port autodetection: "
            f"{', '.join(candidates)}. Use --port to select one."
        )


@app.callback()
def callback(
    port: Annotated[Optional[str], typer.Option(help="Serial port")] = None
) -> None:
    """PiShock serial interface commands."""
    global serial_port
    if port is None:
        port = _autodetect_port()

    serial_port = serial.Serial(port, 115200, timeout=1)

    # FIXME close?
