from datetime import datetime
from rich.table import Table
from rich import box as rich_box

from terminalSplit.config import ACCOUNTS_DB_ID
from terminalSplit.api import create_page, update_page, get_database_select_options
from terminalSplit.properties import (
    get_title, get_select, get_number,
    make_title, make_select, make_number, make_date,
)
from terminalSplit.helpers import get_all_accounts
from terminalSplit.ui import console, prompt, confirm


def _build_accounts_table(accounts):
    """Build and return an accounts Rich Table (assets/liabilities grouped)."""
    assets, liabilities = [], []
    for a in accounts:
        name = get_title(a)
        atype = get_select(a, "Type")
        balance = get_number(a, "Current Balance")
        if atype == "Credit Card":
            liabilities.append((name, balance))
        else:
            assets.append((name, balance))

    asset_total = sum(b for _, b in assets)
    debt_total = sum(b for _, b in liabilities)
    net_worth = asset_total + debt_total

    def fmt(val):
        sign = "-" if val < 0 else ""
        color = "red" if val < 0 else "green"
        return f"[{color}]{sign}${abs(val):,.2f}[/{color}]"

    def fmt_bold(val):
        sign = "-" if val < 0 else ""
        color = "red" if val < 0 else "bold green"
        return f"[{color}]{sign}${abs(val):,.2f}[/{color}]"

    table = Table(
        title="[dim]ACCOUNTS[/dim]  [dim italic]liquid cash: Checking[/dim italic]",
        box=rich_box.SIMPLE_HEAD,
        padding=(0, 1),
        show_footer=False,
        title_justify="left",
    )
    table.add_column("", style="bold")
    table.add_column("", justify="right")

    for name, bal in assets:
        table.add_row(name, fmt(bal))
    table.add_section()
    table.add_row("[dim]Assets[/dim]", fmt_bold(asset_total))

    if liabilities:
        table.add_section()
        for name, bal in liabilities:
            table.add_row(name, fmt(bal))
        table.add_section()
        table.add_row("[dim]Total Debt[/dim]", fmt_bold(debt_total))

    table.add_section()
    nw_color = "red" if net_worth < 0 else "bold yellow"
    nw_sign = "-" if net_worth < 0 else ""
    table.add_row(
        "[bold]Net Worth[/bold]",
        f"[{nw_color}]{nw_sign}${abs(net_worth):,.2f}[/{nw_color}]",
    )

    return table


def cmd_balance(accounts=None):
    """Show all account balances."""
    if accounts is None:
        accounts = get_all_accounts()
    if not accounts:
        console.print("  No accounts found.")
        return
    console.print(_build_accounts_table(accounts))


def _new_account(dry_run=False):
    """Create a new account."""
    console.print("\n  [bold cyan]➕ New Account[/bold cyan]")
    console.print("  [dim]Type 'back' at any prompt to return to menu.[/dim]\n")

    name = prompt("  Account name: ").strip()
    if not name:
        console.print("  [red]❌ Name required.[/red]")
        return

    acct_types = get_database_select_options(ACCOUNTS_DB_ID, "Type")
    if acct_types:
        console.print("\n  [bold]Account type:[/bold]")
        for i, t in enumerate(acct_types, 1):
            console.print(f"    [cyan]{i}.[/cyan] {t}")
        try:
            acct_type = acct_types[int(prompt("  Type # [1]: ") or "1") - 1]
        except (ValueError, IndexError):
            acct_type = acct_types[0]
    else:
        acct_type = prompt("  Account type: ").strip() or "Checking"

    raw = prompt("  Starting balance [$0.00]: $").strip()
    try:
        balance = float(raw) if raw else 0.0
    except ValueError:
        console.print("  [red]❌ Invalid amount.[/red]")
        return

    if not confirm([
        f"Name:    [bold]{name}[/bold]",
        f"Type:    {acct_type}",
        f"Balance: [green]${balance:,.2f}[/green]",
    ]):
        return

    props = {
        "Account Name": make_title(name),
        "Type": make_select(acct_type),
        "Current Balance": make_number(balance),
        "Last Updated": make_date(datetime.now().strftime("%Y-%m-%d")),
    }
    if dry_run:
        console.print(f"  [yellow]🔍 Would create account: [bold]{name}[/bold] ({acct_type}, ${balance:,.2f})[/yellow]")
    else:
        result = create_page(ACCOUNTS_DB_ID, props)
        if result:
            console.print(f"  [green]✅ Account [bold]{name}[/bold] created.[/green]")


def _update_account(dry_run=False):
    """Update an account balance."""
    accounts = get_all_accounts()
    if not accounts:
        console.print("  [red]No accounts found.[/red]")
        return

    console.print("\n  [bold]Select account to update:[/bold]")
    console.print("  [dim]Type 'back' at any prompt to return to menu.[/dim]")
    for i, a in enumerate(accounts, 1):
        name = get_title(a)
        balance = get_number(a, "Current Balance")
        color = "red" if balance < 0 else "green"
        console.print(f"    [cyan]{i}.[/cyan] {name} ([{color}]${balance:,.2f}[/{color}])")

    try:
        idx = int(prompt("  Account #: ")) - 1
        account = accounts[idx]
    except (ValueError, IndexError):
        console.print("  [red]❌ Invalid selection.[/red]")
        return

    old_balance = get_number(account, "Current Balance")
    account_name = get_title(account)

    try:
        new_balance = float(prompt("  New balance: $"))
    except ValueError:
        console.print("  [red]❌ Invalid amount.[/red]")
        return

    diff = new_balance - old_balance
    sign = "+" if diff >= 0 else ""
    diff_color = "green" if diff >= 0 else "red"
    if not confirm([
        f"Account: [bold]{account_name}[/bold]",
        f"${old_balance:,.2f} → [bold]${new_balance:,.2f}[/bold]  ([{diff_color}]{sign}${diff:,.2f}[/{diff_color}])",
    ]):
        return

    props = {
        "Current Balance": make_number(new_balance),
        "Last Updated": make_date(datetime.now().strftime("%Y-%m-%d")),
    }
    if dry_run:
        console.print(f"  [yellow]🔍 Would update {account_name}: ${old_balance:,.2f} → [bold]${new_balance:,.2f}[/bold][/yellow]")
    else:
        result = update_page(account["id"], props)
        if result:
            console.print(f"  [green]✅ {account_name} updated to [bold]${new_balance:,.2f}[/bold][/green]")