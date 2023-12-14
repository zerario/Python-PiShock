from typing import Optional

import rich
import rich.table
import rich.progress
import rich.prompt
import typer
from typing_extensions import Annotated

from pishock.zap import httpapi
from pishock.zap.cli import cli_utils


app = typer.Typer()


def list_sharecodes_info(app_ctx: cli_utils.AppContext) -> None:
    """List all saved share codes with additional info from the API."""
    if not app_ctx.config.shockers:
        rich.print("[yellow]No share codes saved.[/]")
        return

    pishock_api = app_ctx.ensure_pishock_api()
    if not pishock_api.verify_credentials():
        # explicit check because this might save a lot of time when invalid, but
        # when valid, doesn't add much (assuming multiple requests below anyways).
        rich.print("[yellow]Warning:[/] Credentials are invalid. Skipping info.\n")
        list_sharecodes(app_ctx.config)
        raise typer.Exit(1)

    table = rich.table.Table()
    table.add_column("Name", style="green")
    table.add_column("Share code")
    table.add_column("Shocker Name")
    table.add_column("PiShock ID")
    table.add_column("Shocker ID")
    table.add_column("Paused")
    table.add_column("Max intensity")
    table.add_column("Max duration")

    for name, info in rich.progress.track(
        sorted(app_ctx.config.shockers.items()), description="Gathering info..."
    ):
        try:
            api_info = pishock_api.shocker(info.sharecode).info()
        except httpapi.APIError as e:
            table.add_row(name, info.sharecode, f"[red]{e}[/]")
            continue

        if api_info.shocker_id != info.shocker_id:
            rich.print(
                f"[yellow]Warning:[/] Shocker ID mismatch for [green]{name}[/]: "
                f"config has [green]{info.shocker_id}[/] but API claims "
                f"[green]{api_info.shocker_id}[/]. Consider deleting and re-adding."
            )

        pause = cli_utils.paused_emoji(api_info.is_paused)
        table.add_row(
            name,
            info.sharecode,
            api_info.name,
            str(api_info.client_id),
            str(api_info.shocker_id),
            pause,
            f"{api_info.max_intensity}%",
            f"{api_info.max_duration}s",
        )

    rich.print()
    rich.print(table)


def list_sharecodes(
    config: cli_utils.Config,
    added: Optional[str] = None,
    removed: Optional[str] = None,
) -> None:
    """List all saved share codes."""
    if not config.shockers:
        rich.print("[yellow]No share codes saved.[/]")
        return

    table = rich.table.Table.grid(padding=(0, 2))

    table.add_column("")  # emoji
    table.add_column("Name", style="green")
    table.add_column("Share code")
    table.add_column("Shocker ID")

    for name, info in sorted(config.shockers.items()):
        if name == added:
            emoji = ":white_check_mark:"
            style = "green"
        elif name == removed:
            emoji = ":x:"
            style = "red"
        else:
            emoji = ":link:"
            style = None
        table.add_row(emoji, name, info.sharecode, str(info.shocker_id), style=style)

    rich.print(table)


@app.command()
def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name for the share code.")],
    share_code: Annotated[str, typer.Argument(help="Share code to add.")],
    force: Annotated[bool, typer.Option(help="Overwrite existing code.")] = False,
) -> None:
    """Add a new share code to the saved codes."""
    config = ctx.obj.config

    if not cli_utils.SHARE_CODE_REGEX.match(share_code):
        rich.print(f"[yellow]Error:[/] Share code [green]{share_code}[/] is not valid.")
        raise typer.Exit(1)

    if name in config.shockers and not force:
        info = config.shockers[name]
        ok = rich.prompt.Confirm.ask(
            f"Name [green]{name}[/] already exists ({info}). Overwrite?"
        )
        if not ok:
            raise typer.Abort()

    pishock_api = ctx.obj.ensure_pishock_api()
    try:
        shocker_id = pishock_api.shocker(share_code).info().shocker_id
    except httpapi.APIError as e:
        cli_utils.print_exception(e)
        raise typer.Exit(1)

    config.shockers[name] = cli_utils.ShockerInfo(
        sharecode=share_code, shocker_id=shocker_id
    )
    config.save()
    list_sharecodes(config, added=name)


@app.command("del")
def del_(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the share code to delete.")],
) -> None:
    """Delete a saved share code."""
    config = ctx.obj.config

    if name not in config.shockers:
        rich.print(f"[red]Error:[/] Name [green]{name}[/] not found.")
        raise typer.Exit(1)

    list_sharecodes(config, removed=name)
    del config.shockers[name]
    config.save()


@app.command()
def rename(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the share code to rename.")],
    new_name: Annotated[str, typer.Argument(help="New name for the share code.")],
    force: Annotated[bool, typer.Option(help="Overwrite existing code.")] = False,
) -> None:
    """Rename a saved share code."""
    config = ctx.obj.config

    if name not in config.shockers:
        rich.print(f"[red]Error:[/] Name [green]{name}[/] not found.")
        raise typer.Exit(1)
    if name == new_name:
        rich.print("[red]Error:[/] New name is the same as the old name.")
        raise typer.Exit(1)

    if new_name in config.shockers and not force:
        info = config.shockers[name]
        ok = rich.prompt.Confirm.ask(
            f"Name [green]{name}[/] already exists ({info}). Overwrite?"
        )
        if not ok:
            raise typer.Exit(1)

    config.shockers[new_name] = config.shockers[name]
    del config.shockers[name]
    config.save()
    list_sharecodes(config, added=new_name, removed=name)


@app.command("list")
def list_(
    ctx: typer.Context,
    info: Annotated[
        bool, typer.Option(help="Show information about each code.")
    ] = False,
) -> None:
    """List all saved share codes."""
    if info:
        list_sharecodes_info(ctx.obj)
    else:
        list_sharecodes(ctx.obj.config)
