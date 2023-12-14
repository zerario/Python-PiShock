import enum
import json
import contextlib
from typing import Any, Dict, Optional, Iterator, Type

import rich
import rich.box
import rich.console
import rich.pretty
import rich.text
import rich.table
import rich.prompt
import typer
import requests
from typing_extensions import Annotated
import serial.tools  # type: ignore[import-untyped]

try:
    import esptool  # type: ignore[import-untyped]
except ModuleNotFoundError:
    esptool = None

from pishock.zap.cli import cli_utils
from pishock.zap import serialapi
from pishock import firmwareupdate

"""Serial interface commands for PiShock."""

app = typer.Typer(no_args_is_help=True)


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
    try:
        type_name = serialapi.DeviceType(pishock_type).name.capitalize()
    except ValueError:
        pass
    else:
        text = rich.text.Text(str(pishock_type))
        text.append(f" ({type_name})", style="bright_black")
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


@contextlib.contextmanager
def handle_errors(*args: Type[Exception]) -> Iterator[None]:
    try:
        yield
    except (serial.SerialException, *args) as e:
        cli_utils.print_exception(e)
        raise typer.Exit(1)


@app.command()
def info(
    ctx: typer.Context,
    show_passwords: Annotated[
        bool, typer.Option(help="Don't conceal WiFi passwords")
    ] = False,
    raw: Annotated[
        bool, typer.Option(help="Show raw JSON (implies --show-passwords)")
    ] = False,
    timeout: Annotated[
        Optional[int],
        typer.Option(
            help="How many seconds / serial lines to wait for an answer",
            show_default=False,
        ),
    ] = serialapi.INFO_TIMEOUT,
    debug: Annotated[
        bool, typer.Option(help="Show debug output while waiting", show_default=False)
    ] = False,
) -> None:
    """Show information about this PiShock."""
    with handle_errors(TimeoutError):
        data = ctx.obj.serial_api.info(timeout=timeout, debug=debug)

    if raw:
        rich.print(data)
    else:
        _enrich_toplevel_data(data, show_passwords=show_passwords)
        rich.print(_json_to_rich(data))


@app.command()
def add_network(ctx: typer.Context, ssid: str, password: str) -> None:
    """Add a new network to the PiShock config and reboot."""
    with handle_errors(TimeoutError):
        ctx.obj.serial_api.add_network(ssid, password)
        data = ctx.obj.serial_api.wait_info()

    _enrich_toplevel_data(data, show_passwords=False)
    rich.print(_json_to_rich(data["networks"]))


@app.command()
def remove_network(ctx: typer.Context, ssid: str) -> None:
    """Remove a network from the PiShock config."""
    with handle_errors(TimeoutError):
        ctx.obj.serial_api.remove_network(ssid)
        data = ctx.obj.serial_api.wait_info()

    _enrich_toplevel_data(data, show_passwords=False)
    rich.print(_json_to_rich(data["networks"]))


@app.command()
def try_connect(ctx: typer.Context, ssid: str, password: str) -> None:
    """Temporarily try connecting to the given network."""
    with handle_errors():
        ctx.obj.serial_api.try_connect(ssid, password)


@app.command()
def restart(ctx: typer.Context) -> None:
    """Restart the PiShock."""
    with handle_errors():
        ctx.obj.serial_api.restart()


@app.command()
def monitor(ctx: typer.Context) -> None:
    """Monitor serial output."""
    rich.print("[bright_black]Press Ctrl+C to exit.[/]")
    with handle_errors():
        for line in ctx.obj.serial_api.monitor():
            rich.print(line.decode("utf-8", errors="replace"), end="")
            if line.startswith(serialapi.SerialAPI.INFO_PREFIX):
                try:
                    info = ctx.obj.serial_api.decode_info(line)
                except json.JSONDecodeError:
                    pass
                else:
                    rich.print(_json_to_rich(info))


# Should line up with firmwareupdate.FirmwareType!
class FirmwareType(enum.Enum):
    V1_LITE = "v1-lite"
    VAULT = "vault"  # untested!
    V1_NEXT = "v1-next"
    V3_NEXT = "v3-next"
    V3_LITE = "v3-lite"


def _validate_before_flash(
    serial_api: serialapi.SerialAPI, firmware_type: firmwareupdate.FirmwareType
) -> Optional[Dict[str, Any]]:
    """Validate the info response."""
    try:
        info = serial_api.info()
    except (serial.SerialException, TimeoutError):
        ok = rich.prompt.Confirm.ask(
            f"Can't connect to PiShock at {serial_api.dev.port}, flash anyway?"
        )
        if ok:
            return None
        raise typer.Abort()

    try:
        device_type = serialapi.DeviceType(info.get("type"))
    except ValueError:
        ok = rich.prompt.Confirm.ask(
            f"Unknown device type {info.get('type')} at {serial_api.dev.port}, flash anyway?"
        )
        if ok:
            return info
        raise typer.Abort()

    if not firmwareupdate.is_compatible(
        device_type=device_type, firmware_type=firmware_type
    ):
        ok = rich.prompt.Confirm.ask(
            f"Device type {device_type.name} at {serial_api.dev.port} might not be "
            f"compatible with selected firmware {firmware_type.name}, flash anyway?"
        )
        if ok:
            return info
        raise typer.Abort()

    return info


@app.command()
def flash(
    ctx: typer.Context,
    firmware_type: Annotated[
        FirmwareType,
        typer.Argument(
            help=(
                "Which firmware to flash. V1/V3 are old/new firmare versions, Lite is "
                "a PiShock with a MicroUSB port, Next is a PiShock with an USB-C port."
            )
        ),
    ],
    restore_networks: Annotated[
        bool,
        typer.Option(help="Restore WiFi networks after flashing"),
    ] = True,
) -> None:
    """Flash the latest firmware."""
    if esptool is None:
        cli_utils.print_error(
            "Optional esptool dependency is required for firmware updates"
        )
        raise typer.Exit(1)

    rich.print("Checking device state...")
    api_type = firmwareupdate.FirmwareType[firmware_type.name]
    info = _validate_before_flash(ctx.obj.serial_api, firmware_type=api_type)

    if info is None or not restore_networks:
        networks = None
    else:
        networks = [
            (net["ssid"], net["password"])
            for net in info.get("networks", [])
            if net["ssid"] != "PiShock"
        ]
        rich.print(f"Saved networks: {', '.join(ssid for ssid, _ in networks)}")

    # FIXME nicer output
    rich.print("Downloading firmware...")
    with handle_errors(requests.HTTPError):
        data = firmwareupdate.download_firmware(api_type)

    rich.print("Truncating firmware...")
    with handle_errors(firmwareupdate.FirmwareUpdateError):
        data = firmwareupdate.truncate(data)

    rich.print("Flashing firmware...")
    with handle_errors(
        firmwareupdate.FirmwareUpdateError, esptool.FatalError, StopIteration, OSError
    ):
        firmwareupdate.flash(ctx.obj.serial_api.dev.port, data)

    rich.print("Waiting for info...")
    with handle_errors():
        info = ctx.obj.serial_api.wait_info(timeout=None)

    if networks is not None:
        with handle_errors():
            for ssid, password in networks:
                rich.print(f"Restoring network: {ssid}...")
                ctx.obj.serial_api.add_network(ssid, password)
                rich.print("Waiting for info...")
                ctx.obj.serial_api.wait_info(timeout=None, debug=True)
                rich.print("Waiting for reboot...")
                ctx.obj.serial_api.wait_info(timeout=None, debug=True)
