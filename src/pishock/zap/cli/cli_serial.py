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
import rich.progress
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


SHOCKER_TYPES = {0: "Petrainer", 1: "SmallOne"}


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
    elif isinstance(data, rich.console.ConsoleRenderable):
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
    with handle_errors(TimeoutError, json.JSONDecodeError):
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


class FlashProgress(enum.Enum):
    CHECK_STATE = "Checking device state"
    DOWNLOAD = "Downloading firmware"
    TRUNCATE = "Truncating firmware"
    FLASH = "Flashing firmware"
    WAIT_INFO = "Waiting for info"
    RESTORE_NETWORKS = "Restoring networks"


def _validate_before_flash(
    serial_api: serialapi.SerialAPI,
    firmware_type: firmwareupdate.FirmwareType,
    progress: rich.progress.Progress,
) -> Optional[Dict[str, Any]]:
    """Validate the info response."""
    try:
        info = serial_api.info()
    except (serial.SerialException, TimeoutError, json.JSONDecodeError):
        with hide_progress(progress):
            ok = rich.prompt.Confirm.ask(
                "Can't communicate with PiShock firmware at "
                f"[green]{serial_api.dev.port}[/], flash anyway?"
            )
            if ok:
                return None
            raise typer.Abort()

    try:
        device_type = serialapi.DeviceType(info.get("type"))
    except ValueError:
        with hide_progress(progress):
            ok = rich.prompt.Confirm.ask(
                f"Unknown device type [green]{info.get('type')}[/] at "
                f"[green]{serial_api.dev.port}[/], flash anyway?"
            )
            if ok:
                return info
            raise typer.Abort()

    if not firmwareupdate.is_compatible(
        device_type=device_type, firmware_type=firmware_type
    ):
        with hide_progress(progress):
            ok = rich.prompt.Confirm.ask(
                f"Device type [green]{device_type.name}[/] at "
                f"[green]{serial_api.dev.port}[/] might not be compatible with "
                f"selected firmware [green]{firmware_type.name}[/], flash anyway?"
            )
            if ok:
                return info
            raise typer.Abort()

    if not info.get("networks"):
        with hide_progress(progress):
            ok = rich.prompt.Confirm.ask(
                "No existing networks found on PiShock at "
                f"[green]{serial_api.dev.port}[/], flash anyway?"
            )
            if ok:
                return info
            raise typer.Abort()

    return info


@contextlib.contextmanager
def hide_progress(progress: rich.progress.Progress) -> Iterator[None]:
    """Temporarily hide progress for confirm messages.

    See https://github.com/Textualize/rich/issues/1535#issuecomment-1745297594
    """
    transient = progress.live.transient  # save the old value
    progress.live.transient = True
    progress.stop()
    progress.live.transient = transient  # restore the old value
    try:
        yield
    finally:
        # make space for the progress to use so it doesn't overwrite any previous lines
        print("\n" * (len(progress.tasks) - 2))
        progress.start()


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
    check: Annotated[
        bool,
        typer.Option(
            help=(
                "Run additional checks on device. Passing --no-check allows flashing "
                "devices currently not running propely without waiting for a timeout, "
                "but implies --no-restore-networks."
            )
        ),
    ] = True,
) -> None:
    """Flash the latest firmware."""
    if esptool is None:
        cli_utils.print_error(
            "Optional esptool dependency is required for firmware updates"
        )
        raise typer.Exit(1)

    with rich.progress.Progress(
        rich.progress.SpinnerColumn(),
        *rich.progress.Progress.get_default_columns()[:-1],  # no ETA
    ) as progress:
        task = progress.add_task(
            FlashProgress.CHECK_STATE.value, total=len(FlashProgress)
        )

        api_type = firmwareupdate.FirmwareType[firmware_type.name]
        if check:
            info = _validate_before_flash(
                ctx.obj.serial_api, firmware_type=api_type, progress=progress
            )
        else:
            info = None

        if info is None or not restore_networks:
            networks = None
        else:
            networks = [
                (net["ssid"], net["password"])
                for net in info.get("networks", [])
                if net["ssid"] != "PiShock"
            ]
            if networks:
                rich.print(f"Saved networks: {', '.join(ssid for ssid, _ in networks)}")
                rich.print()

        progress.update(task, advance=1, description=FlashProgress.DOWNLOAD.value)

        chunks = []
        with handle_errors(requests.HTTPError):
            size, data_iter = firmwareupdate.download_firmware(api_type)
            download_task = progress.add_task("Downloading...", total=size)
            for chunk in data_iter:
                progress.advance(download_task, len(chunk))
                chunks.append(chunk)

        progress.update(download_task, visible=False)
        data = b"".join(chunks)

        progress.update(task, advance=1, description=FlashProgress.TRUNCATE.value)
        with handle_errors(firmwareupdate.FirmwareUpdateError):
            data = firmwareupdate.truncate(data)

        progress.update(task, advance=1, description=FlashProgress.FLASH.value)
        with handle_errors(
            firmwareupdate.FirmwareUpdateError,
            esptool.FatalError,
            StopIteration,
            OSError,
        ):
            firmwareupdate.flash(ctx.obj.serial_api.dev.port, data)

        rich.print()

        progress.update(task, advance=1, description=FlashProgress.WAIT_INFO.value)
        with handle_errors():
            ctx.obj.serial_api.wait_info(timeout=None)

        progress.update(
            task, advance=1, description=FlashProgress.RESTORE_NETWORKS.value
        )
        if networks:
            net_task = progress.add_task("Restoring networks", total=len(networks) + 2)
            with handle_errors():
                for ssid, password in networks:
                    progress.update(net_task, advance=1, description=ssid)
                    rich.print("Adding network...")
                    ctx.obj.serial_api.add_network(ssid, password)
                    rich.print("Waiting for info...")
                    ctx.obj.serial_api.wait_info(timeout=None)
                    rich.print("Waiting for reboot...")
                    ctx.obj.serial_api.wait_info(timeout=None)

            progress.update(net_task, advance=1, description="Validating")
            new_info = ctx.obj.serial_api.info()
            restored = [
                (net["ssid"], net["password"])
                for net in new_info.get("networks", [])
                if net["ssid"] != "PiShock"
            ]
            if networks != restored:
                rich.print("[red]Restored networks don't match saved networks:[/]")
                rich.print(f"Saved:    {networks}")
                rich.print(f"Restored: {restored}")

            progress.update(net_task, visible=False)

        progress.update(task, visible=False)
