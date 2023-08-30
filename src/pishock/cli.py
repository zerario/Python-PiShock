import contextlib
import json
import pathlib
import random
import sys
from typing import Iterator, Optional

import platformdirs
import rich
import rich.prompt
import rich.table
import typer
from typing_extensions import Annotated, TypeAlias

from pishock import zap

"""Command-line interface for PiShock."""

app = typer.Typer()
api = None
config = None


# TODO:
# - Address book
#   code-add [--force]
#   code-del
#   code-list [--info]
#   code-rename
#
# - Accept multiple share codes for commands
# - --force for init
# - Rename verify-credentials to verify
# - Random mode
# - Warn when only username or only API key was given
# - Handle basic invalid configs?
# - selftest mode?


class Config:
    def __init__(self) -> None:
        self.username: Optional[str] = None
        self.api_key: Optional[str] = None
        self._path = pathlib.Path(
            platformdirs.user_config_dir(appname="PiShock-CLI", appauthor="PiShock"),
            "config.json",
        )

    def load(self) -> None:
        if not self._path.exists():
            return
        with self._path.open("r") as f:
            data = json.load(f)
        self.username = data["api"]["username"]
        self.api_key = data["api"]["key"]

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "api": {
                "username": self.username,
                "key": self.api_key,
            }
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
    online = ":white_check_mark:" if info.is_online else ":x:"

    table.add_row("Online / Paused", f"{online} {pause}")
    table.add_row("Max intensity", str(info.max_intensity))
    table.add_row("Max duration", str(info.max_duration))

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


@app.command(rich_help_panel="API credentials")
def verify_credentials() -> None:
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
def init() -> None:
    """Initialize the API credentials."""
    assert config is not None
    if config.username is not None or config.api_key is not None:
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
