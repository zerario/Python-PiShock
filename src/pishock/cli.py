import contextlib
import random
from typing import Union

try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated
try:
    from typing import TypeAlias
except ImportError:
    from typing_extensions import TypeAlias

import typer
import rich
import rich.table

from pishock import zap

"""Command-line interface for PiShock."""

app = typer.Typer()
api = None


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
def handle_errors() -> None:
    try:
        yield
    except (zap.APIError, ValueError) as e:
        rich.print(f"[red]Error: {e} ({type(e).__name__})[/red]")
        raise typer.Exit(1)


def get_shocker(share_code: str) -> zap.Shocker:
    assert api is not None
    return api.shocker(share_code, name=f"{zap.NAME} CLI")


def print_emoji(name: str, duration: float) -> None:
    rich.print(f":{name}:" * max(int(duration), 1))


@app.command()
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


@app.command()
def vibrate(
    share_code: ShareCodeArg, duration: DurationOpt, intensity: IntensityOpt
) -> None:
    """Send a vibration to the given share code."""
    shocker = get_shocker(share_code)
    with handle_errors():
        shocker.vibrate(duration=duration, intensity=intensity)
    print_emoji("vibration_mode", duration)


@app.command()
def beep(share_code: ShareCodeArg, duration: DurationOpt) -> None:
    """Send a beep to the given share code."""
    shocker = get_shocker(share_code)
    with handle_errors():
        shocker.beep(duration=duration)
    print_emoji("loud_sound", duration)


def paused_emoji(is_paused: bool) -> str:
    return ":double_vertical_bar:" if is_paused else ":arrow_forward:"


@app.command()
def info(share_code: ShareCodeArg):
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

    pause = ":double_vertical_bar:" if info.is_paused else ":arrow_forward:"
    online = ":white_check_mark:" if info.is_online else ":x:"

    table.add_row("Online / Paused", f"{online} {pause}")
    table.add_row("Max intensity", str(info.max_intensity))
    table.add_row("Max duration", str(info.max_duration))

    rich.print(table)


@app.command()
def pause(share_code: ShareCodeArg):
    """Pause the given shocker."""
    shocker = get_shocker(share_code)
    with handle_errors():
        shocker.pause(True)


@app.command()
def unpause(share_code: ShareCodeArg):
    """Unpause the given shocker."""
    shocker = get_shocker(share_code)
    with handle_errors():
        shocker.pause(False)


@app.command()
def shockers(
    client_id: Annotated[int, typer.Argument(help="PiShock client ID.")],
):
    """Get a list of all shockers for the given client (PiShock) ID."""
    assert api is not None
    with handle_errors():
        shockers = api.get_shockers(client_id)

    for shocker in shockers:
        emoji = paused_emoji(shocker.is_paused)
        rich.print(f"{shocker.shocker_id}: {shocker.name} {emoji}")


@app.callback()
def main(
    username: Annotated[
        str,
        typer.Option(
            help="Username for the PiShock account.", envvar="PISHOCK_API_USER"
        ),
    ],
    api_key: Annotated[
        str,
        typer.Option(help="API key for the PiShock account.", envvar="PISHOCK_API_KEY"),
    ],
):
    global api
    api = zap.API(username, api_key)


if __name__ == "__main__":
    app()
