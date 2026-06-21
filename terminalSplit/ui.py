from datetime import datetime

from rich.console import Console

console = Console()


class UserCancelled(Exception):
    pass


def prompt(msg):
    """input() wrapper — typing 'back' or 'b' cancels the current command."""
    val = input(msg).strip()
    if val.lower() in ("back", "b"):
        raise UserCancelled()
    return val


def confirm(lines):
    """Print a summary and ask y/n. Returns True if confirmed."""
    console.print("\n  [bold]Confirm:[/bold]")
    for line in lines:
        console.print(f"    {line}")
    ans = input("  Proceed? (y/n): ").strip().lower()
    if ans != "y":
        console.print("  [yellow]Cancelled.[/yellow]")
        return False
    return True


def pick(label, items, *, format_item=str, default=None):
    """Display a numbered list and return the selected item.

    Re-prompts on invalid input. Raises UserCancelled on 'back'/'b'.
    """
    console.print(f"\n  [bold]{label}:[/bold]")
    for i, item in enumerate(items, 1):
        console.print(f"    [cyan]{i:2}.[/cyan] {format_item(item)}")

    suffix = f" [{default}]" if default else ""
    while True:
        raw = prompt(f"  {label} #{suffix}: ")
        if not raw and default is not None:
            return items[default - 1]
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(items):
                return items[idx]
        except ValueError:
            pass
        console.print("  [red]Invalid selection, try again.[/red]")


def prompt_amount(label="Amount"):
    """Prompt for a dollar amount. Re-prompts on invalid input."""
    while True:
        raw = prompt(f"  {label}: $")
        try:
            return float(raw)
        except ValueError:
            console.print("  [red]Invalid amount, try again.[/red]")


def prompt_date(label="Date"):
    """Prompt for a YYYY-MM-DD date. Enter accepts today."""
    today = datetime.now().strftime("%Y-%m-%d")
    while True:
        raw = prompt(f"  {label} [{today}]: ")
        if not raw:
            return today
        try:
            datetime.strptime(raw, "%Y-%m-%d")
            return raw
        except ValueError:
            console.print("  [red]Invalid date format. Use YYYY-MM-DD.[/red]")
