import json
from typing import Any, Dict, Optional

import rich
import rich.box
import rich.console
import rich.pretty
import rich.text
import rich.table
import typer
from typing_extensions import Annotated

import serial.tools  # type: ignore[import-untyped]

from pishock.zap.cli import cli_utils
from pishock.zap import serialapi

"""Serial interface commands for PiShock."""

app = typer.Typer(no_args_is_help=True)
serial_api = None

DEVICE_TYPES = {3: "Lite", 4: "Next"}
SHOCKER_TYPES = {0: "SmallOne", 1: "Petrainer"}


def print_serial_ports() -> None:
    """Print available serial ports."""
    table = rich.table.Table(title="Available serial ports")
    table.add_column("Device", style="bold")
    table.add_column("Description")
    table.add_column("USB VID")
    table.add_column("USB PID")
    table.add_column("USB Serial Number")
    table.add_column("USB Manufacturer")
    table.add_column("USB Product")
    for info in serial.tools.list_ports.comports():
        table.add_row(
            info.device,
            info.description if info.description != "n/a" else "",
            hex(info.vid) if info.vid is not None else "",
            hex(info.pid) if info.pid is not None else "",
            info.serial_number,
            info.manufacturer,
            info.product,
            style=None if serialapi.is_maybe_pishock(info) else "bright_black",
        )

    rich.print()
    rich.print(table)
    rich.print("\nUse [green]--port[/] option to specify a serial port.")
    rich.print(
        "[bright_black]Note:[/] If you see your PiShock greyed out above, "
        "please report this as a bug: "
        "https://github.com/zerario/Python-PiShock/issues/new"
    )


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
    ] = False,
    raw: Annotated[
        bool, typer.Option(help="Show raw JSON (implies --show-passwords)")
    ] = False,
) -> None:
    """Show information about this PiShock."""
    assert serial_api is not None
    data = serial_api.info()
    if raw:
        rich.print(data)
    else:
        _enrich_toplevel_data(data, show_passwords=show_passwords)
        rich.print(_json_to_rich(data))


@app.command()
def add_network(ssid: str, password: str) -> None:
    """Add a new network to the PiShock config and reboot."""
    assert serial_api is not None
    serial_api.add_network(ssid, password)
    data = serial_api.wait_info()
    _enrich_toplevel_data(data, show_passwords=False)
    rich.print(_json_to_rich(data["networks"]))


@app.command()
def remove_network(ssid: str) -> None:
    """Remove a network from the PiShock config."""
    assert serial_api is not None
    serial_api.remove_network(ssid)
    data = serial_api.wait_info()
    _enrich_toplevel_data(data, show_passwords=False)
    rich.print(_json_to_rich(data["networks"]))


@app.command()
def try_connect(ssid: str, password: str) -> None:
    """Temporarily try connecting to the given network."""
    assert serial_api is not None
    serial_api.try_connect(ssid, password)


@app.command()
def restart() -> None:
    """Restart the PiShock."""
    assert serial_api is not None
    serial_api.restart()


@app.command()
def monitor() -> None:
    """Monitor serial output."""
    assert serial_api is not None
    for line in serial_api.monitor():
        rich.print(line.decode("utf-8", errors="replace"), end="")
        if line.startswith(serialapi.SerialAPI.INFO_PREFIX):
            try:
                info = serial_api.decode_info(line)
            except json.JSONDecodeError:
                pass
            else:
                rich.print(_json_to_rich(info))


@app.callback()
def callback(
    port: Annotated[Optional[str], typer.Option(help="Serial port")] = None,
) -> None:
    """PiShock serial interface commands."""
    global serial_api
    try:
        serial_api = serialapi.SerialAPI(port)
    except serialapi.SerialAutodetectError as e:
        cli_utils.print_exception(e)
        print_serial_ports()
        raise typer.Exit(1)
    # FIXME close?
