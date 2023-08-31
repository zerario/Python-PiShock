import contextlib
import difflib
import json
import pathlib
import random
import time
import re
import sys
from typing import List, Tuple, Dict, Iterator, Optional

import platformdirs
import rich
import rich.progress
import rich.prompt
import rich.table
import typer
from typing_extensions import Annotated, TypeAlias

from pishock import zap, cli_random

"""Command-line interface for PiShock."""

app = typer.Typer()
api = None
config = None


SHARE_CODE_REGEX = re.compile(r"^[0-9A-F]{11}$")  # 11 upper case hex digits


# TODO:
# - Accept multiple share codes for commands
# - Random mode
# - Handle basic invalid configs?
# - selftest mode?


class Config:
    def __init__(self) -> None:
        self._path = pathlib.Path(
            platformdirs.user_config_dir(appname="PiShock-CLI", appauthor="PiShock"),
            "config.json",
        )

        self.username: Optional[str] = None
        self.api_key: Optional[str] = None
        self.sharecodes: Dict[str, str] = {}

    def load(self) -> None:
        if not self._path.exists():
            return
        with self._path.open("r") as f:
            data = json.load(f)

        self.username = data["api"]["username"]
        self.api_key = data["api"]["key"]
        self.sharecodes = data.get("sharecodes", {})

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "api": {
                "username": self.username,
                "key": self.api_key,
            },
            "sharecodes": self.sharecodes,
        }
        with self._path.open("w") as f:
            json.dump(data, f)


ShareCodeArg: TypeAlias = Annotated[
    str, typer.Argument(help="Share code for the shocker.")
]
DurationOpt: TypeAlias = Annotated[
    float,
    typer.Option("-d", "--duration", min=0, max=15, help="Duration in seconds (0-15)."),
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
    except (zap.APIError, ValueError) as e:
        rich.print(f"[red]Error:[/] {e} ([red bold]{type(e).__name__}[/])")
        raise typer.Exit(1)


def get_shocker(share_code: str) -> zap.Shocker:
    assert api is not None
    assert config is not None

    if share_code in config.sharecodes:
        share_code = config.sharecodes[share_code]
    elif not SHARE_CODE_REGEX.match(share_code):
        rich.print(
            f"[yellow]Error:[/] Share code [green]{share_code}[/] not in valid share "
            f"code format and not found in saved codes."
        )
        matches = difflib.get_close_matches(share_code, config.sharecodes.keys(), n=1)
        if matches:
            rich.print(f"Did you mean [green]{matches[0]}[/]?")
        raise typer.Exit(1)

    return api.shocker(share_code, name=f"{zap.NAME} CLI")


def print_emoji(name: str, duration: float) -> None:
    rich.print(f":{name}:" * max(int(duration), 1))


@app.command(rich_help_panel="Actions")
def shock(
    share_code: ShareCodeArg, duration: DurationOpt, intensity: IntensityOpt
) -> None:
    """Send a shock to the given share code."""
    shocker = get_shocker(share_code)
    with handle_errors():
        shocker.shock(duration=duration, intensity=intensity)

    print_emoji("zap", duration)
    if random.random() < 0.1:
        print("".join(random.choices("asdfghjkl", k=random.randint(5, 20))))


@app.command(rich_help_panel="Actions")
def vibrate(
    share_code: ShareCodeArg, duration: DurationOpt, intensity: IntensityOpt
) -> None:
    """Send a vibration to the given share code."""
    shocker = get_shocker(share_code)
    with handle_errors():
        shocker.vibrate(duration=duration, intensity=intensity)
    print_emoji("vibration_mode", duration)


@app.command(rich_help_panel="Actions")
def beep(share_code: ShareCodeArg, duration: DurationOpt) -> None:
    """Send a beep to the given share code."""
    shocker = get_shocker(share_code)
    with handle_errors():
        shocker.beep(duration=duration)
    print_emoji("loud_sound", duration)


def paused_emoji(is_paused: bool) -> str:
    return ":double_vertical_bar:" if is_paused else ":arrow_forward:"


def online_emoji(is_online: bool) -> str:
    return ":white_check_mark:" if is_online else ":x:"


@app.command(rich_help_panel="Shockers")
def info(share_code: ShareCodeArg) -> None:
    """Get information about the given shocker."""
    shocker = get_shocker(share_code)
    with handle_errors():
        info = shocker.info()

    table = rich.table.Table(show_header=False)
    table.add_column()
    table.add_column()

    table.add_row("Name", info.name)
    table.add_row("PiShock ID", str(info.client_id))
    table.add_row("Shocker ID", str(info.shocker_id))

    pause = paused_emoji(info.is_paused)
    online = online_emoji(info.is_online)

    table.add_row("Online / Paused", f"{online} {pause}")
    table.add_row("Max intensity", f"{info.max_intensity}%")
    table.add_row("Max duration", f"{info.max_duration}s")

    rich.print(table)


@app.command(rich_help_panel="Shockers")
def pause(share_code: ShareCodeArg) -> None:
    """Pause the given shocker."""
    shocker = get_shocker(share_code)
    with handle_errors():
        shocker.pause(True)


@app.command(rich_help_panel="Shockers")
def unpause(share_code: ShareCodeArg) -> None:
    """Unpause the given shocker."""
    shocker = get_shocker(share_code)
    with handle_errors():
        shocker.pause(False)


@app.command(rich_help_panel="Shockers")
def shockers(
    client_id: Annotated[int, typer.Argument(help="PiShock client ID.")],
) -> None:
    """Get a list of all shockers for the given client (PiShock) ID."""
    assert api is not None
    with handle_errors():
        shockers = api.get_shockers(client_id)

    for shocker in shockers:
        emoji = paused_emoji(shocker.is_paused)
        rich.print(f"{shocker.shocker_id}: {shocker.name} {emoji}")


def list_sharecodes_info() -> None:
    """List all saved share codes with additional info from the API."""
    assert config is not None
    assert api is not None

    if not config.sharecodes:
        rich.print("[yellow]No share codes saved.[/]")
        return

    if not api.verify_credentials():
        # explicit check because this might save a lot of time when invalid, but
        # when valid, doesn't add much (assuming multiple requests below anyways).
        rich.print("[yellow]Warning:[/] Credentials are invalid. Skipping info.\n")
        list_sharecodes()
        raise typer.Exit(1)

    table = rich.table.Table()
    table.add_column("Name", style="green")
    table.add_column("Share code")
    table.add_column("Shocker Name")
    table.add_column("PiShock ID")
    table.add_column("Shocker ID")
    table.add_column("Online / Paused")
    table.add_column("Max intensity")
    table.add_column("Max duration")

    for name, share_code in rich.progress.track(
        sorted(config.sharecodes.items()), description="Gathering info..."
    ):
        try:
            info = api.shocker(share_code).info()
        except zap.APIError as e:
            table.add_row(name, share_code, f"[red]{e}[/]")
            continue

        pause = paused_emoji(info.is_paused)
        online = online_emoji(info.is_online)
        table.add_row(
            name,
            share_code,
            info.name,
            str(info.client_id),
            str(info.shocker_id),
            f"{online} {pause}",
            f"{info.max_intensity}%",
            f"{info.max_duration}s",
        )

    rich.print(table)


def list_sharecodes(
    added: Optional[str] = None,
    removed: Optional[str] = None,
) -> None:
    """List all saved share codes."""
    assert config is not None

    if not config.sharecodes:
        rich.print("[yellow]No share codes saved.[/]")
        return

    table = rich.table.Table.grid(padding=(0, 2))

    table.add_column("")  # emoji
    table.add_column("Name", style="green")
    table.add_column("Share code")

    for name, share_code in sorted(config.sharecodes.items()):
        if name == added:
            emoji = ":white_check_mark:"
            style = "green"
        elif name == removed:
            emoji = ":x:"
            style = "red"
        else:
            emoji = ":link:"
            style = None
        table.add_row(emoji, name, share_code, style=style)

    rich.print(table)


@app.command(rich_help_panel="Share codes")
def code_add(
    name: Annotated[str, typer.Argument(help="Name for the share code.")],
    share_code: Annotated[str, typer.Argument(help="Share code to add.")],
    force: Annotated[bool, typer.Option(help="Overwrite existing code.")] = False,
) -> None:
    """Add a new share code to the saved codes."""
    assert config is not None
    if not SHARE_CODE_REGEX.match(share_code):
        rich.print(f"[yellow]Error:[/] Share code [green]{share_code}[/] is not valid.")
        raise typer.Exit(1)

    if name in config.sharecodes and not force:
        code = config.sharecodes[name]
        ok = rich.prompt.Confirm.ask(
            f"Name [green]{name}[/] already exists ({code}). Overwrite?"
        )
        if not ok:
            raise typer.Abort()

    config.sharecodes[name] = share_code
    config.save()
    list_sharecodes(added=name)


@app.command(rich_help_panel="Share codes")
def code_del(
    name: Annotated[str, typer.Argument(help="Name of the share code to delete.")],
) -> None:
    """Delete a saved share code."""
    assert config is not None
    if name not in config.sharecodes:
        rich.print(f"[red]Error:[/] Name [green]{name}[/] not found.")
        raise typer.Exit(1)

    list_sharecodes(removed=name)
    del config.sharecodes[name]
    config.save()


@app.command(rich_help_panel="Share codes")
def code_rename(
    name: Annotated[str, typer.Argument(help="Name of the share code to rename.")],
    new_name: Annotated[str, typer.Argument(help="New name for the share code.")],
    force: Annotated[bool, typer.Option(help="Overwrite existing code.")] = False,
) -> None:
    """Rename a saved share code."""
    assert config is not None
    if name not in config.sharecodes:
        rich.print(f"[red]Error:[/] Name [green]{name}[/] not found.")
        raise typer.Exit(1)
    if name == new_name:
        rich.print(f"[red]Error:[/] New name is the same as the old name.")
        raise typer.Exit(1)

    if new_name in config.sharecodes and not force:
        code = config.sharecodes[name]
        ok = rich.prompt.Confirm.ask(
            f"Name [green]{name}[/] already exists ({code}). Overwrite?"
        )
        if not ok:
            raise typer.Exit(1)

    config.sharecodes[new_name] = config.sharecodes[name]
    del config.sharecodes[name]
    config.save()
    list_sharecodes(added=new_name, removed=name)


@app.command(rich_help_panel="Share codes")
def code_list(
    info: Annotated[
        bool, typer.Option(help="Show information about each code.")
    ] = False,
) -> None:
    """List all saved share codes."""
    assert config is not None
    if info:
        list_sharecodes_info()
    else:
        list_sharecodes()


@app.command(name="random")
def random_mode(
    share_codes: List[ShareCodeArg],
    duration: cli_random.DurationArg,
    intensity: cli_random.IntensityArg,
    pause: cli_random.PauseArg,
    spam_possibility: cli_random.SpamPossibilityArg = 0,
    spam_operations: cli_random.SpamOperationsArg = (5, 25),
    spam_pause: cli_random.SpamPauseArg = (0, 0),
    spam_duration: cli_random.SpamDurationArg = (1, 1),
    spam_intensity: cli_random.SpamIntensityArg = None,  # use -i
    max_runtime: cli_random.MaxRuntimeArg = None,
    vibrate_duration: cli_random.VibrateDurationArg = None,  # use -d
    vibrate_intensity: cli_random.VibrateIntensityArg = None,  # use -i
    shock: cli_random.ShockArg = True,
    vibrate: cli_random.VibrateArg = False,
) -> None:
    """Send operations to random shockers."""
    assert api is not None
    spam_settings = cli_random.SpamSettings(
        possibility=spam_possibility,
        operations=spam_operations,
        pause=spam_pause,
        duration=spam_duration,
        intensity=spam_intensity,
    )
    random_shocker = cli_random.RandomShocker(
        api=api,
        share_codes=share_codes,
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
def verify() -> None:
    """Verify that the API credentials are correct."""
    assert api is not None
    with handle_errors():
        ok = api.verify_credentials()
    if ok:
        rich.print("[green]:white_check_mark: Credentials are valid.[/]")
    else:
        rich.print("[red]:x: Credentials are invalid.[/]")
        raise typer.Exit(1)


@app.command(rich_help_panel="API credentials")
def init(
    force: Annotated[
        bool, typer.Option(help="Overwrite existing information without asking")
    ] = False
) -> None:
    """Initialize the API credentials."""
    assert config is not None
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
        temp_api = zap.API(username, api_key)
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
) -> None:
    global api, config
    config = Config()
    config.load()

    if username is None or api_key is None:
        if username is not None:
            rich.print("[yellow]Warning:[/] Username given but no API key. Ignoring.\n")
        if api_key is not None:
            rich.print("[yellow]Warning:[/] API key given but no username. Ignoring.\n")

        if ctx.invoked_subcommand == "init":
            return

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
    api = zap.API(username, api_key)


if __name__ == "__main__":
    app()  # pragma: no cover
