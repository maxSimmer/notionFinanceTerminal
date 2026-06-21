from datetime import datetime
from rich.table import Table
from rich import box as rich_box

from terminalSplit.config import TRANSACTIONS_DB_ID
from terminalSplit.api import create_page, query_database
from terminalSplit.properties import (
    get_title, get_select, get_number, get_date,
    make_title, make_number, make_select, make_date,
    make_checkbox, make_relation,
)
from terminalSplit.helpers import (
    get_categories, get_types, get_all_accounts,
    get_active_month, adjust_account_balance,
)
from terminalSplit.ui import console, prompt, confirm, pick, prompt_amount, prompt_date, UserCancelled

_last_account_idx = 0  # session-level default for account selection

_payment_method_map = {
    "Checking": "Debit Card",
    "Savings": "Bank Transfer",
    "Credit Card": "Credit Card",
    "Cash": "Cash",
}


def _format_account(a):
    return f"{get_title(a)} [dim]({get_select(a, 'Type')})[/dim]"


def _build_tx_props(desc, amount, date_str, category, tx_type, account, account_id):
    """Build the Notion properties dict for a transaction."""
    account_type = get_select(account, "Type")
    payment = _payment_method_map.get(account_type, "Debit Card")

    props = {
        "Description": make_title(desc),
        "Amount": make_number(amount),
        "Date": make_date(date_str),
        "Category": make_select(category),
        "Type": make_select(tx_type),
        "Payment Method": make_select(payment),
        "Verified": make_checkbox(False),
        "Is Recurring": make_checkbox(False),
    }
    if account_id:
        props["Account"] = make_relation([account_id])

    active_month = get_active_month()
    if active_month:
        props["Monthly Budget"] = make_relation([active_month["id"]])

    return props


def cmd_add(dry_run=False, tx_type_override=None):
    """Add a new transaction interactively."""
    global _last_account_idx

    tx_type = tx_type_override or "Expense"
    label = "Income" if tx_type == "Income" else "Transaction"

    console.print(f"\n  [bold cyan]➕ Add {label}[/bold cyan]")
    console.print("  [dim]" + "─" * 40 + "[/dim]")
    if dry_run:
        console.print("  [yellow bold]⚠ DRY RUN — nothing will be saved[/yellow bold]")
    console.print("  [dim]Type 'back' at any prompt to return to menu.[/dim]\n")

    try:
        desc = prompt("  Description: ")
        if not desc:
            console.print("  [red]❌ Description required.[/red]")
            return

        amount = prompt_amount()
        date_str = prompt_date()
        category = pick("Category", get_categories())

        accounts = get_all_accounts()
        default_idx = min(_last_account_idx + 1, len(accounts))
        account = pick("Account", accounts, format_item=_format_account, default=default_idx)
        account_id = account["id"]
        account_name = get_title(account)
        _last_account_idx = accounts.index(account)

        summary = [
            f"[bold]{desc}[/bold]  [green]${amount:.2f}[/green]  [dim]{date_str}[/dim]",
            f"Category: {category}   Type: {tx_type}",
            f"Account: {account_name}",
        ]
        if not confirm(summary):
            return

        props = _build_tx_props(desc, amount, date_str, category, tx_type, account, account_id)

        if dry_run:
            console.print(f"\n  [yellow]🔍 Would create transaction: {desc} — [bold]${amount:.2f}[/bold] on {account_name}[/yellow]")
            console.print(f"  [yellow]   Would adjust {account_name} balance by {'−' if tx_type != 'Income' else '+'}${amount:.2f}[/yellow]")
        else:
            result = create_page(TRANSACTIONS_DB_ID, props)
            if result:
                console.print(f"\n  [green]✅ Transaction added: {desc} — [bold]${amount:.2f}[/bold][/green]")
                adjust_account_balance(account_id, amount, tx_type)

    except UserCancelled:
        console.print("  [dim]Returning to menu.[/dim]")


def cmd_add_batch(dry_run=False):
    """Add multiple transactions for a single day."""
    global _last_account_idx

    console.print("\n  [bold cyan]➕ Batch Add[/bold cyan]")
    console.print("  [dim]" + "─" * 40 + "[/dim]")
    if dry_run:
        console.print("  [yellow bold]⚠ DRY RUN — nothing will be saved[/yellow bold]")
    console.print("  [dim]Type 'back' to cancel. 'done' when finished entering.[/dim]\n")

    try:
        date_str = prompt_date()

        accounts = get_all_accounts()
        default_idx = min(_last_account_idx + 1, len(accounts))
        account = pick("Account", accounts, format_item=_format_account, default=default_idx)
        account_id = account["id"]
        account_name = get_title(account)
        _last_account_idx = accounts.index(account)

        categories = get_categories()
        batch = []

        while True:
            console.print(f"\n  [dim]— Transaction #{len(batch) + 1} (enter 'done' to finish) —[/dim]")
            desc = prompt("  Description: ")
            if desc.lower() in ("done", "d"):
                break
            if not desc:
                break

            amount = prompt_amount()
            category = pick("Category", categories)
            batch.append({"desc": desc, "amount": amount, "category": category})

        if not batch:
            console.print("  [dim]No transactions entered.[/dim]")
            return

        # Summary table
        table = Table(box=rich_box.SIMPLE_HEAVY, padding=(0, 1))
        table.add_column("#", style="dim", justify="right")
        table.add_column("Description")
        table.add_column("Amount", justify="right", style="green")
        table.add_column("Category", style="cyan")

        total = 0.0
        for i, entry in enumerate(batch, 1):
            table.add_row(str(i), entry["desc"], f"${entry['amount']:.2f}", entry["category"])
            total += entry["amount"]

        console.print()
        console.print(f"  [bold]Date:[/bold] {date_str}    [bold]Account:[/bold] {account_name}")
        console.print(table)
        console.print(f"  [bold]Total: [green]${total:.2f}[/green]  ({len(batch)} items)[/bold]")

        if not confirm([f"Create {len(batch)} transactions on {account_name}?"]):
            return

        if dry_run:
            console.print(f"\n  [yellow]🔍 Would create {len(batch)} transactions totalling ${total:.2f} on {account_name}[/yellow]")
        else:
            created = 0
            for entry in batch:
                props = _build_tx_props(
                    entry["desc"], entry["amount"], date_str,
                    entry["category"], "Expense", account, account_id,
                )
                result = create_page(TRANSACTIONS_DB_ID, props)
                if result:
                    adjust_account_balance(account_id, entry["amount"], "Expense")
                    created += 1
            console.print(f"\n  [green]✅ Created {created}/{len(batch)} transactions — [bold]${total:.2f}[/bold][/green]")

    except UserCancelled:
        console.print("  [dim]Returning to menu.[/dim]")


def cmd_transfer(dry_run=False):
    """Transfer money between two accounts."""
    console.print("\n  [bold cyan]🔁 Transfer[/bold cyan]")
    console.print("  [dim]" + "─" * 40 + "[/dim]")
    if dry_run:
        console.print("  [yellow bold]⚠ DRY RUN — nothing will be saved[/yellow bold]")
    console.print("  [dim]Type 'back' at any prompt to return to menu.[/dim]\n")

    try:
        accounts = get_all_accounts()

        # Show account list once, prompt for source and destination
        console.print("  [bold]Accounts:[/bold]")
        for i, a in enumerate(accounts, 1):
            console.print(f"    [cyan]{i}.[/cyan] {_format_account(a)}")

        try:
            src_idx = int(prompt("  Source #: ")) - 1
            src_account = accounts[src_idx]
            src_account_id = src_account["id"]
            src_account_name = get_title(src_account)
        except (ValueError, IndexError):
            console.print("  [red]❌ Invalid selection.[/red]")
            return

        try:
            dest_idx = int(prompt("  Destination #: ")) - 1
            dest_account = accounts[dest_idx]
            dest_account_id = dest_account["id"]
            dest_account_name = get_title(dest_account)
        except (ValueError, IndexError):
            console.print("  [red]❌ Invalid selection.[/red]")
            return

        if src_account_id == dest_account_id:
            console.print("  [red]❌ Source and destination must be different accounts.[/red]")
            return

        amount = prompt_amount()
        date_str = prompt_date()

        desc = prompt("  Description [Transfer]: ")
        if not desc:
            desc = "Transfer"

        summary = [
            f"[bold]{desc}[/bold]  [green]${amount:.2f}[/green]  [dim]{date_str}[/dim]",
            f"From: {src_account_name}  →  To: {dest_account_name}",
        ]
        if not confirm(summary):
            return

        active_month = get_active_month()
        base_props = {
            "Description": make_title(desc),
            "Amount": make_number(amount),
            "Date": make_date(date_str),
            "Category": make_select("Transfer"),
            "Type": make_select("Transfer"),
            "Payment Method": make_select("Bank Transfer"),
            "Verified": make_checkbox(False),
            "Is Recurring": make_checkbox(False),
        }
        if active_month:
            base_props["Monthly Budget"] = make_relation([active_month["id"]])

        src_props = {**base_props, "Account": make_relation([src_account_id])}
        dest_props = {**base_props, "Account": make_relation([dest_account_id])}

        if dry_run:
            console.print(f"\n  [yellow]🔍 Would create transfer transaction on {src_account_name} (−${amount:.2f})[/yellow]")
            console.print(f"  [yellow]   Would create transfer transaction on {dest_account_name} (+${amount:.2f})[/yellow]")
            console.print(f"  [yellow]   Would adjust balances: {src_account_name} −${amount:.2f}, {dest_account_name} +${amount:.2f}[/yellow]")
        else:
            src_result = create_page(TRANSACTIONS_DB_ID, src_props)
            if src_result:
                adjust_account_balance(src_account_id, amount, "Transfer")
                dest_result = create_page(TRANSACTIONS_DB_ID, dest_props)
                if dest_result:
                    adjust_account_balance(dest_account_id, amount, "Income")
                    console.print(f"\n  [green]✅ Transferred [bold]${amount:.2f}[/bold] from {src_account_name} to {dest_account_name}[/green]")

    except UserCancelled:
        console.print("  [dim]Returning to menu.[/dim]")


def cmd_recent():
    """Show last 10 transactions."""
    pages = query_database(
        TRANSACTIONS_DB_ID,
        sorts=[{"property": "Date", "direction": "descending"}],
        page_size=10,
    )
    if not pages:
        console.print("  No transactions found.")
        return

    table = Table(box=rich_box.SIMPLE_HEAVY, padding=(0, 1))
    table.add_column("Date", style="dim")
    table.add_column("Description")
    table.add_column("Amount", justify="right")
    table.add_column("Category", style="cyan")

    for p in pages:
        date = get_date(p, "Date") or "—"
        desc = get_title(p)[:24]
        amount = get_number(p, "Amount")
        cat = get_select(p, "Category")
        tx_type = get_select(p, "Type")
        if tx_type == "Income":
            amt_str = f"[bold green]+${amount:,.2f}[/bold green]"
        else:
            amt_str = f"[red]-${amount:,.2f}[/red]"
        table.add_row(date, desc, amt_str, cat)

    console.print(table)
