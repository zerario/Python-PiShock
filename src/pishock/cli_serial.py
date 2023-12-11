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

from pishock import cli_utils

"""Serial interface commands for PiShock."""

app = typer.Typer(no_args_is_help=True)
serial_port = None

DEVICE_TYPES = {3: "Lite", 4: "Next"}
SHOCKER_TYPES = {0: "SmallOne", 1: "Petrainer"}


def _build_cmd(cmd: str) -> bytes:
    data = json.dumps({"cmd": cmd}) + "\n"
    return data.encode("utf-8")  # FIXME encoding?


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


def _json_to_rich(
    data: Dict[str, Any], toplevel: bool = False, show_passwords: bool = False
) -> rich.console.RenderableType:
    if toplevel:
        _enrich_toplevel_data(data, show_passwords=show_passwords)

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
    prefix = b"TERMINALINFO: "
    serial_port.write(_build_cmd("info"))
    while True:
        line = serial_port.readline()
        if line.startswith(prefix):
            break

    data = json.loads(line[len(prefix) :])
    rich.print(_json_to_rich(data, toplevel=True, show_passwords=show_passwords))


@app.callback()
def callback(
    port: Annotated[Optional[str], typer.Option(help="Serial port")] = None
) -> None:
    """PiShock serial interface commands."""
    global serial_port
    if port is None:
        rich.print("TODO")
        raise typer.Exit(1)

    serial_port = serial.Serial(port, 115200, timeout=1)
    # FIXME close?
