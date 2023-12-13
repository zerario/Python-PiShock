import contextlib
import difflib
import pathlib
import random
import sys
from typing import Iterator, List, Optional

import serial
import rich
import rich.progress
import rich.prompt
import rich.table
import typer
from typing_extensions import Annotated, TypeAlias

from pishock.zap import serialapi, core, httpapi
from pishock.zap.cli import cli_random, cli_serial, cli_utils, cli_code

"""Command-line interface for PiShock."""

app = typer.Typer()
app.add_typer(cli_serial.app, name="serial", help="Serial interface commands")
app.add_typer(cli_code.app, name="code", help="Manage share codes")


# TODO:
# - Accept multiple share codes for commands
# - Random mode
# - Handle basic invalid configs?
# - selftest mode?


ShareCodeArg: TypeAlias = Annotated[
    str, typer.Argument(help="Share code for the shocker.")
]
DurationOpt: TypeAlias = Annotated[
    float,
    typer.Option("-d", "--duration", min=0, help="Duration in seconds."),
]
IntensityOpt: TypeAlias = Annotated[
    int,
    typer.Option(
        "-i", "--intensity", min=0, max=100, help="Intensity in percent (0-100)."
    ),
]


@contextlib.contextmanager
def handle_errors() -> Iterator[None]:
    try:
        yield
    except (httpapi.APIError, ValueError, serial.SerialException, TimeoutError) as e:
        cli_utils.print_exception(e)
        raise typer.Exit(1)


def get_shocker(app_ctx: cli_utils.AppContext, share_code: str) -> core.Shocker:
    if app_ctx.serial_api is not None:
        try:
            shocker_id = int(share_code)
        except ValueError as e:
            cli_utils.print_exception(e)
            raise typer.Exit(1)

        return serialapi.SerialShocker(app_ctx.serial_api, shocker_id)

    assert app_ctx.pishock_api is not None
    share_codes = app_ctx.config.sharecodes

    name = None
    if share_code in share_codes:
        name = share_code
        share_code = share_codes[share_code]
    elif not cli_utils.SHARE_CODE_REGEX.match(share_code):
        rich.print(
            f"[yellow]Error:[/] Share code [green]{share_code}[/] not in valid share "
            f"code format and not found in saved codes."
        )
        matches = difflib.get_close_matches(share_code, share_codes.keys(), n=1)
        if matches:
            rich.print(f"Did you mean [green]{matches[0]}[/]?")
        raise typer.Exit(1)

    return app_ctx.pishock_api.shocker(
        share_code, name=name, log_name=f"{httpapi.NAME} CLI"
    )


def print_emoji(name: str, duration: float) -> None:
    rich.print(f":{name}:" * max(int(duration), 1))


@app.command(rich_help_panel="Actions")
def shock(
    ctx: typer.Context,
    share_code: ShareCodeArg,
    duration: DurationOpt,
    intensity: IntensityOpt,
) -> None:
    """Send a shock to the given share code."""
    shocker = get_shocker(ctx.obj, share_code)
    with handle_errors():
        shocker.shock(duration=duration, intensity=intensity)

    print_emoji("zap", duration)
    if random.random() < 0.1:
        print("".join(random.choices("asdfghjkl", k=random.randint(5, 20))))


@app.command(rich_help_panel="Actions")
def vibrate(
    ctx: typer.Context,
    share_code: ShareCodeArg,
    duration: DurationOpt,
    intensity: IntensityOpt,
) -> None:
    """Send a vibration to the given share code."""
    shocker = get_shocker(ctx.obj, share_code)
    with handle_errors():
        shocker.vibrate(duration=duration, intensity=intensity)
    print_emoji("vibration_mode", duration)


@app.command(rich_help_panel="Actions")
def beep(ctx: typer.Context, share_code: ShareCodeArg, duration: DurationOpt) -> None:
    """Send a beep to the given share code."""
    shocker = get_shocker(ctx.obj, share_code)
    with handle_errors():
        shocker.beep(duration=duration)
    print_emoji("loud_sound", duration)


@app.command(rich_help_panel="Shockers")
def info(ctx: typer.Context, share_code: ShareCodeArg) -> None:
    """Get information about the given shocker."""
    shocker = get_shocker(ctx.obj, share_code)
    with handle_errors():
        info = shocker.info()

    table = rich.table.Table(show_header=False)
    table.add_column()
    table.add_column()

    table.add_row("Name", info.name)
    table.add_row("PiShock ID", str(info.client_id))
    table.add_row("Shocker ID", str(info.shocker_id))

    pause = cli_utils.paused_emoji(info.is_paused)
    if isinstance(info, httpapi.DetailedShockerInfo):
        online = cli_utils.bool_emoji(info.is_online)
        table.add_row("Online / Paused", f"{online} {pause}")
        table.add_row("Max intensity", f"{info.max_intensity}%")
        table.add_row("Max duration", f"{info.max_duration}s")
    else:
        table.add_row("Paused", pause)

    rich.print(table)


@app.command(rich_help_panel="Shockers")
def pause(ctx: typer.Context, share_code: ShareCodeArg) -> None:
    """Pause the given shocker."""
    ctx.obj.ensure_pishock_api()
    shocker = get_shocker(ctx.obj, share_code)
    assert isinstance(shocker, httpapi.HTTPShocker)
    with handle_errors():
        shocker.pause(True)


@app.command(rich_help_panel="Shockers")
def unpause(ctx: typer.Context, share_code: ShareCodeArg) -> None:
    """Unpause the given shocker."""
    ctx.obj.ensure_pishock_api()
    shocker = get_shocker(ctx.obj, share_code)
    assert isinstance(shocker, httpapi.HTTPShocker)
    with handle_errors():
        shocker.pause(False)


@app.command(rich_help_panel="Shockers")
def shockers(
    ctx: typer.Context,
    client_id: Annotated[int, typer.Argument(help="PiShock client ID.")],
) -> None:
    """Get a list of all shockers for the given client (PiShock) ID."""
    with handle_errors():
        shockers = ctx.obj.ensure_pishock_api().get_shockers(client_id)

    for shocker in shockers:
        emoji = cli_utils.paused_emoji(shocker.is_paused)
        rich.print(f"{shocker.shocker_id}: {shocker.name} {emoji}")


@app.command(name="random")
def random_mode(
    ctx: typer.Context,
    share_codes: Annotated[
        List[str], typer.Argument(help="Share code for the shocker.")
    ],
    duration: cli_random.DurationArg,
    intensity: cli_random.IntensityArg,
    pause: cli_random.PauseArg,
    spam_possibility: cli_random.SpamPossibilityArg = 0,
    spam_operations: cli_random.SpamOperationsArg = cli_utils.Range(5, 25),
    spam_pause: cli_random.SpamPauseArg = cli_utils.Range(0, 0),
    spam_duration: cli_random.SpamDurationArg = cli_utils.Range(1, 1),
    spam_intensity: cli_random.SpamIntensityArg = None,  # use -i
    max_runtime: cli_random.MaxRuntimeArg = None,
    vibrate_duration: cli_random.VibrateDurationArg = None,  # use -d
    vibrate_intensity: cli_random.VibrateIntensityArg = None,  # use -i
    shock: cli_random.ShockArg = True,
    vibrate: cli_random.VibrateArg = False,
) -> None:
    """Send operations to random shockers."""
    spam_settings = cli_random.SpamSettings(
        possibility=spam_possibility,
        operations=spam_operations,
        pause=spam_pause,
        duration=spam_duration,
        intensity=spam_intensity,
    )
    shockers = [get_shocker(ctx.obj, share_code) for share_code in share_codes]
    random_shocker = cli_random.RandomShocker(
        shockers=shockers,
        duration=duration,
        intensity=intensity,
        pause=pause,
        spam_settings=spam_settings,
        max_runtime=max_runtime,
        vibrate_duration=vibrate_duration,
        vibrate_intensity=vibrate_intensity,
        shock=shock,
        vibrate=vibrate,
    )
    random_shocker.run()


@app.command(rich_help_panel="API credentials")
def verify(ctx: typer.Context) -> None:
    """Verify that the API credentials are correct."""
    with handle_errors():
        ok = ctx.obj.ensure_pishock_api().verify_credentials()
    if ok:
        rich.print("[green]:white_check_mark: Credentials are valid.[/]")
    else:
        rich.print("[red]:x: Credentials are invalid.[/]")
        raise typer.Exit(1)


@app.command(rich_help_panel="API credentials")
def init(
    ctx: typer.Context,
    force: Annotated[
        bool, typer.Option(help="Overwrite existing information without asking")
    ] = False,
) -> None:
    """Initialize the API credentials."""
    config = ctx.obj.config
    api = ctx.obj.pishock_api

    if (config.username is not None or config.api_key is not None) and not force:
        yes = rich.prompt.Confirm.ask(
            f"Overwrite existing information for [green]{config.username}[/]?"
        )
        if not yes:
            raise typer.Abort()

    if api is None:
        username = rich.prompt.Prompt.ask(
            ":bust_in_silhouette: PiShock [green]username[/] "
            "([blue]your own username[/])"
        ).strip()
        api_key = rich.prompt.Prompt.ask(
            ":key: PiShock [green]API key[/] "
            "([blue][link]https://pishock.com/#/account[/][/])"
        ).strip()
        temp_api = httpapi.PiShockAPI(username, api_key)
    else:
        # Credentials already given via environment or arguments
        username = api.username
        api_key = api.api_key
        temp_api = api

    if not temp_api.verify_credentials():
        rich.print("[red]:x: Credentials are invalid.[/]")
        raise typer.Exit(1)

    config.username = username
    config.api_key = api_key
    config.save()

    rich.print("[green]:white_check_mark: Credentials saved.[/]")


def init_serial(port: Optional[str]) -> cli_utils.AppContext:
    config = cli_utils.Config()
    config.load()

    # FIXME close?
    try:
        with handle_errors():
            serial_api = serialapi.SerialAPI(port)
    except serialapi.SerialAutodetectError as e:
        cli_utils.print_exception(e)
        cli_serial.print_serial_ports()
        raise typer.Exit(1)

    return cli_utils.AppContext(config=config, pishock_api=None, serial_api=serial_api)


def init_pishock_api(
    username: Optional[str], api_key: Optional[str], *, is_init: bool
) -> cli_utils.AppContext:
    config = cli_utils.Config()
    config.load()

    if username is None or api_key is None:
        if username is not None:
            rich.print("[yellow]Warning:[/] Username given but no API key. Ignoring.\n")
        if api_key is not None:
            rich.print("[yellow]Warning:[/] API key given but no username. Ignoring.\n")

        if is_init:
            return cli_utils.AppContext(
                config=cli_utils.Config(), pishock_api=None, serial_api=None
            )

        if config.username is None or config.api_key is None:
            cmd = pathlib.PurePath(sys.argv[0]).name
            rich.print(
                "[red]No API credentials found.[/] To fix this, do either of:\n\n"
                f"- Run [green]{cmd} init[/] to create a new config file\n"
                "- Set [green]PISHOCK_API_USER[/] and [green]PISHOCK_API_KEY[/] "
                "environment variables\n"
                "- Pass [green]--username[/] and [green]--api-key[/] options"
            )
            raise typer.Exit(1)
        username = config.username
        api_key = config.api_key
        assert username is not None
        assert api_key is not None

    pishock_api = httpapi.PiShockAPI(username, api_key)
    return cli_utils.AppContext(config=config, pishock_api=pishock_api, serial_api=None)


@app.callback()
def main(
    ctx: typer.Context,
    username: Annotated[
        Optional[str],
        typer.Option(
            help="Username for the PiShock account.",
            envvar="PISHOCK_API_USER",
        ),
    ] = None,
    api_key: Annotated[
        Optional[str],
        typer.Option(
            help="API key for the PiShock account.",
            envvar="PISHOCK_API_KEY",
        ),
    ] = None,
    serial: Annotated[
        bool, typer.Option("--serial", help="Use serial interface instead of HTTP API.")
    ] = False,
    port: Annotated[
        Optional[str],
        typer.Option(
            help="Serial port to use with --serial. Auto-detection is attempted if not given."
        ),
    ] = None,
) -> None:
    if serial or ctx.invoked_subcommand == "serial":
        ctx.obj = init_serial(port)
    elif port is not None:
        cli_utils.print_error(
            "--port option only valid with --serial or serial subcommand."
        )
        raise typer.Exit(1)
    else:
        ctx.obj = init_pishock_api(
            username, api_key, is_init=ctx.invoked_subcommand == "init"
        )


if __name__ == "__main__":
    app()  # pragma: no cover
