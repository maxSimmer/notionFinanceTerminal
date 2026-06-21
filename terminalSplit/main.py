import sys
import requests

from terminalSplit.config import NOTION_API_KEY, ACCOUNTS_DB_ID, BASE_URL, _sanitize
from terminalSplit.api import headers
from terminalSplit.ui import console
from terminalSplit.helpers import prefetch_startup_data
from terminalSplit.commands.transactions import cmd_add, cmd_add_batch, cmd_transfer, cmd_recent
from terminalSplit.commands.accounts import cmd_balance
from terminalSplit.commands.goals import cmd_goals
from terminalSplit.commands.recurring import cmd_recurring, cmd_bills
from terminalSplit.commands.monthly import cmd_month, cmd_rollover, cmd_startup_panel
from terminalSplit.commands.meta import cmd_help, cmd_clear, cmd_new, cmd_update


def main():
    if not NOTION_API_KEY:
        console.print("\n  [red]❌ NOTION_API_KEY not found.[/red]")
        console.print("  Set it one of these ways:\n")
        console.print("  [bold]Option 1[/bold] — Export in terminal:")
        console.print("    [dim]export NOTION_API_KEY='ntn_your_key_here'[/dim]")
        console.print("    [dim]python -m terminalSplit[/dim]\n")
        console.print("  [bold]Option 2[/bold] — Create a .env file in the same folder:")
        console.print("    [dim]echo \"NOTION_API_KEY=ntn_your_key_here\" > .env[/dim]")
        console.print("    [dim]pip install python-dotenv --break-system-packages[/dim]")
        console.print("    [dim]python -m terminalSplit[/dim]\n")
        sys.exit(1)

    console.print("\n  💰 Budget CLI — Connecting to Notion...", end="", highlight=False)
    try:
        test = requests.get(f"{BASE_URL}/databases/{ACCOUNTS_DB_ID}", headers=headers(), timeout=10)
        if test.status_code == 200:
            console.print(" [green]✅ Connected![/green]")
        elif test.status_code == 401:
            console.print(" [red]❌ Invalid API key.[/red]")
            console.print("  [dim]Check your NOTION_API_KEY and try again.[/dim]")
            sys.exit(1)
        elif test.status_code == 404:
            console.print(" [red]❌ Database not found.[/red]")
            console.print("  [dim]Make sure you shared the Budget Command Center page[/dim]")
            console.print("  [dim]with your integration (... menu → Connections → Add).[/dim]")
            sys.exit(1)
        else:
            console.print(f" [yellow]⚠️  Unexpected response: {test.status_code}[/yellow]")
            console.print(f"  [dim]{_sanitize(test.text[:200])}[/dim]")
    except requests.exceptions.ConnectionError:
        console.print(" [red]❌ No internet connection.[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f" [red]❌ Error: {_sanitize(str(e))}[/red]")
        sys.exit(1)

    console.print("  [bold]💰 Budget CLI[/bold]  [dim]Type [bold]help[/bold] for commands[/dim]")
    console.rule(style="dim")
    accounts, month, expense_txs = prefetch_startup_data()
    cmd_startup_panel(accounts, month, expense_txs)

    while True:
        try:
            raw = input("  budget> ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [bold]👋 Goodbye![/bold]")
            break

        if not raw:
            continue

        parts = raw.split(maxsplit=1)
        cmd = parts[0].lower()
        args_str = parts[1] if len(parts) > 1 else ""

        if cmd in ("quit", "exit", "q", "14"):
            console.print("  [bold]👋 Goodbye![/bold]")
            break
        elif cmd in ("help", "h", "13"):
            cmd_help()
        elif cmd in ("clear", "cls", "12"):
            cmd_clear()
        elif cmd in ("add", "1"):
            dry_run = "--dry-run" in args_str
            flags = args_str.split()
            if "--batch" in flags or "-b" in flags:
                cmd_add_batch(dry_run=dry_run)
            else:
                income = "--income" in flags or "-i" in flags
                cmd_add(dry_run=dry_run, tx_type_override="Income" if income else None)
        elif cmd in ("transfer", "t", "2"):
            cmd_transfer(dry_run="--dry-run" in args_str)
        elif cmd in ("update", "3"):
            cmd_update(dry_run="--dry-run" in args_str)
        elif cmd in ("new", "4"):
            cmd_new(dry_run="--dry-run" in args_str)
        elif cmd in ("balance", "5"):
            cmd_balance()
        elif cmd in ("month", "6"):
            cmd_month()
        elif cmd in ("recent", "7"):
            cmd_recent()
        elif cmd in ("bills", "8"):
            cmd_bills()
        elif cmd in ("goals", "9"):
            cmd_goals()
        elif cmd in ("rollover", "10"):
            cmd_rollover(dry_run="--dry-run" in args_str)
        elif cmd in ("recurring", "11"):
            cmd_recurring(dry_run="--dry-run" in args_str)
        else:
            console.print(f"  [red]Unknown command: {cmd}[/red]. Type '[bold]help[/bold]' for options.")
