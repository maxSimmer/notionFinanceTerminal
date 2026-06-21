from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from rich.console import Group
from rich.text import Text
from terminalSplit.config import RECURRING_DB_ID, TRANSACTIONS_DB_ID
from terminalSplit.api import create_page, update_page, query_database, get_page
from terminalSplit.properties import (
    get_title, get_number, get_select, get_date, get_checkbox, get_relation_ids,
    make_title, make_number, make_select, make_date, make_checkbox, make_relation,
)
from terminalSplit.helpers import (
    get_categories, get_types, get_all_accounts,
    get_active_month, adjust_account_balance,
)
from terminalSplit.ui import console, prompt, confirm, pick, prompt_date, UserCancelled

FREQ_MAP = {
    "Weekly": relativedelta(weeks=1),
    "Bi-Weekly": relativedelta(weeks=2),
    "Monthly": relativedelta(months=1),
    "Quarterly": relativedelta(months=3),
    "Semi-Annual": relativedelta(months=6),
    "Annual": relativedelta(years=1),
}


def _build_bills_renderable():
    """Return a Group renderable of upcoming bills (for embedding in a Columns layout)."""
    today = datetime.now()
    cutoff = today + timedelta(days=30)
    pages = query_database(
        RECURRING_DB_ID,
        filter_obj={
            "and": [
                {"property": "Is Active", "checkbox": {"equals": True}},
                {"property": "Next Due Date", "date": {"on_or_before": cutoff.strftime("%Y-%m-%d")}},
            ]
        },
        sorts=[{"property": "Next Due Date", "direction": "ascending"}],
    )
    if not pages:
        return Text("")

    lines = [Text.from_markup("  [dim]UPCOMING BILLS[/dim]")]
    for p in pages:
        due_str = get_date(p, "Next Due Date") or ""
        name = get_title(p)
        amount = get_number(p, "Amount")
        auto_pay = get_checkbox(p, "Auto Pay")
        try:
            due_dt = datetime.strptime(due_str, "%Y-%m-%d")
            short_date = due_dt.strftime("%b ") + str(due_dt.day)
        except ValueError:
            short_date = due_str
        if auto_pay:
            lines.append(Text.from_markup(f"  [dim]  {name} autopays {short_date} (${amount:,.2f})[/dim]"))
        else:
            lines.append(Text.from_markup(
                f"  [bold red]↑[/bold red] [bold]{name:<22}[/bold]"
                f"  [dim]{short_date} · manual[/dim]"
                f"  [red]${amount:,.2f}[/red]"
            ))
    return Group(*lines)


def cmd_bills():
    """Show upcoming recurring bills."""
    today = datetime.now()
    cutoff = today + timedelta(days=30)

    pages = query_database(
        RECURRING_DB_ID,
        filter_obj={
            "and": [
                {"property": "Is Active", "checkbox": {"equals": True}},
                {"property": "Next Due Date", "date": {"on_or_before": cutoff.strftime("%Y-%m-%d")}},
            ]
        },
        sorts=[{"property": "Next Due Date", "direction": "ascending"}],
    )
    if not pages:
        console.print("  No upcoming bills in the next 30 days.")
        console.rule(style="dim")
        return

    console.print("  [dim]UPCOMING BILLS[/dim]")

    for p in pages:
        due_str = get_date(p, "Next Due Date") or ""
        name = get_title(p)
        amount = get_number(p, "Amount")
        auto_pay = get_checkbox(p, "Auto Pay")

        try:
            due_dt = datetime.strptime(due_str, "%Y-%m-%d")
            # "Apr 17" — strip leading zero cross-platform
            short_date = due_dt.strftime("%b ") + str(due_dt.day)
        except ValueError:
            short_date = due_str

        if auto_pay:
            console.print(f"  [dim]  {name} autopays {short_date} (${amount:,.2f})[/dim]")
        else:
            console.print(
                f"  [bold red]↑[/bold red] [bold]{name:<22}[/bold]"
                f"  [dim]{short_date} · manual[/dim]"
                f"  [red]${amount:,.2f}[/red]"
            )

    console.rule(style="dim")


def cmd_recurring(dry_run=False):
    """Generate this month's recurring transactions."""
    today = datetime.now()
    month_start = today.replace(day=1).strftime("%Y-%m-%d")
    month_end = (today.replace(day=1) + relativedelta(months=1) - timedelta(days=1)).strftime("%Y-%m-%d")

    pages = query_database(
        RECURRING_DB_ID,
        filter_obj={
            "and": [
                {"property": "Is Active", "checkbox": {"equals": True}},
                {"property": "Next Due Date", "date": {"on_or_before": month_end}},
            ]
        },
    )

    if not pages:
        console.print("  [dim]No recurring transactions due this month.[/dim]")
        return

    if dry_run:
        console.print("  [dim][DRY RUN] No changes will be made.[/dim]\n")

    active_month = get_active_month()
    month_id = active_month["id"] if active_month else None
    created = 0

    for p in pages:
        name = get_title(p)
        amount = get_number(p, "Amount")
        category = get_select(p, "Category")
        tx_type = get_select(p, "Type")
        due_date = get_date(p, "Next Due Date")
        frequency = get_select(p, "Frequency")
        account_ids = get_relation_ids(p, "Account")
        dest_account_ids = get_relation_ids(p, "Destination Account")

        next_due_str = None
        if due_date:
            try:
                due = datetime.strptime(due_date, "%Y-%m-%d")
                delta = FREQ_MAP.get(frequency, relativedelta(months=1))
                next_due_str = (due + delta).strftime("%Y-%m-%d")
            except ValueError:
                pass

        if dry_run:
            console.print(f"  [dim][DRY RUN] Would create transaction: \"{name}\" — ${amount:.2f} ({tx_type}) on {due_date}[/dim]")
            if account_ids:
                account = get_page(account_ids[0])
                if account:
                    account_name = get_title(account)
                    current_balance = get_number(account, "Current Balance")
                    adj = amount if tx_type == "Income" else -amount
                    new_balance = current_balance + adj
                    sign = "+" if adj >= 0 else ""
                    console.print(f"  [dim][DRY RUN] Would adjust \"{account_name}\": ${current_balance:,.2f} → ${new_balance:,.2f} ({sign}${adj:,.2f})[/dim]")
            if tx_type == "Transfer" and dest_account_ids:
                dest_account = get_page(dest_account_ids[0])
                if dest_account:
                    dest_name = get_title(dest_account)
                    dest_balance = get_number(dest_account, "Current Balance")
                    console.print(f"  [dim][DRY RUN] Would adjust \"{dest_name}\": ${dest_balance:,.2f} → ${dest_balance + amount:,.2f} (+${amount:,.2f})[/dim]")
            if next_due_str:
                console.print(f"  [dim][DRY RUN] Would advance \"{name}\" next due date to {next_due_str}[/dim]")
            created += 1
            continue

        props = {
            "Description": make_title(name),
            "Amount": make_number(amount),
            "Date": make_date(due_date),
            "Category": make_select(category),
            "Type": make_select(tx_type),
            "Payment Method": make_select("Auto Pay"),
            "Is Recurring": make_checkbox(True),
            "Verified": make_checkbox(False),
            "Recurring Source": make_relation([p["id"]]),
        }
        if account_ids:
            props["Account"] = make_relation(account_ids)
        if month_id:
            props["Monthly Budget"] = make_relation([month_id])

        result = create_page(TRANSACTIONS_DB_ID, props)
        if result:
            created += 1
            console.print(f"  [green]✅ Created: {name} — [bold]${amount:.2f}[/bold] (due {due_date})[/green]")
            if account_ids:
                adjust_account_balance(account_ids[0], amount, tx_type)
            if tx_type == "Transfer" and dest_account_ids:
                dest_props = {
                    "Description": make_title(name),
                    "Amount": make_number(amount),
                    "Date": make_date(due_date),
                    "Category": make_select("Transfer"),
                    "Type": make_select("Transfer"),
                    "Payment Method": make_select("Bank Transfer"),
                    "Is Recurring": make_checkbox(True),
                    "Verified": make_checkbox(False),
                    "Recurring Source": make_relation([p["id"]]),
                    "Account": make_relation(dest_account_ids),
                }
                if month_id:
                    dest_props["Monthly Budget"] = make_relation([month_id])
                create_page(TRANSACTIONS_DB_ID, dest_props)
                adjust_account_balance(dest_account_ids[0], amount, "Income")

        if next_due_str:
            update_page(p["id"], {"Next Due Date": make_date(next_due_str)})

    if dry_run:
        console.print(f"\n  [dim][DRY RUN] Would create [bold]{created}[/bold] recurring transaction(s). No changes made.[/dim]")
    else:
        console.print(f"\n  [bold]📋 Created {created} recurring transaction(s).[/bold]")


def _new_recurring(dry_run=False):
    """Create a new recurring transaction."""
    console.print("\n  [bold cyan]➕ New Recurring Transaction[/bold cyan]")
    console.print("  [dim]Type 'back' at any prompt to return to menu.[/dim]\n")

    name = prompt("  Name: ").strip()
    if not name:
        console.print("  [red]❌ Name required.[/red]")
        return

    try:
        amount = float(prompt("  Amount: $"))
    except ValueError:
        console.print("  [red]❌ Invalid amount.[/red]")
        return

    category = pick("Category", get_categories())

    types = get_types()
    tx_type = pick("Type", types, default=1)

    freq_options = list(FREQ_MAP.keys())
    frequency = pick("Frequency", freq_options, default=1)

    due_date = prompt_date("Next due date")

    accounts = get_all_accounts()
    fmt_acct = lambda a: f"{get_title(a)} [dim]({get_select(a, 'Type')})[/dim]"
    account = pick("Account", accounts, format_item=fmt_acct, default=1)
    account_id = account["id"]

    dest_account_id = None
    if tx_type == "Transfer":
        console.print("  [dim](see account list above)[/dim]")
        try:
            dest_idx = int(prompt("  Destination Account #: ")) - 1
            dest = accounts[dest_idx]
            dest_account_id = dest["id"]
        except (ValueError, IndexError):
            console.print("  [red]❌ Invalid selection.[/red]")
            return

    raw = prompt("  Auto Pay? y/n [n]: ").strip().lower()
    auto_pay = raw == "y"

    summary = [
        f"Name:      [bold]{name}[/bold]",
        f"Amount:    [bold]${amount:,.2f}[/bold]",
        f"Category:  {category}   Type: {tx_type}",
        f"Frequency: {frequency}   Due: {due_date}",
        f"Account:   {get_title(account)}",
        f"Auto Pay:  {'yes' if auto_pay else 'no'}",
    ]
    if dest_account_id:
        dest_name = get_title(next(a for a in accounts if a["id"] == dest_account_id))
        summary.append(f"Dest Acct: {dest_name}")
    if not confirm(summary):
        return

    props = {
        "Name": make_title(name),
        "Amount": make_number(amount),
        "Category": make_select(category),
        "Type": make_select(tx_type),
        "Frequency": make_select(frequency),
        "Next Due Date": make_date(due_date),
        "Is Active": make_checkbox(True),
        "Auto Pay": make_checkbox(auto_pay),
        "Account": make_relation([account_id]),
    }
    if dest_account_id:
        props["Destination Account"] = make_relation([dest_account_id])

    if dry_run:
        console.print(f"  [yellow]🔍 Would create recurring transaction: [bold]{name}[/bold] (${amount:,.2f} {frequency}, next: {due_date})[/yellow]")
    else:
        result = create_page(RECURRING_DB_ID, props)
        if result:
            console.print(f"  [green]✅ Recurring transaction [bold]{name}[/bold] created.[/green]")


def _update_recurring(dry_run=False):
    """Update properties of an existing recurring transaction."""
    pages = query_database(RECURRING_DB_ID, sorts=[{"property": "Name", "direction": "ascending"}])
    if not pages:
        console.print("  [red]No recurring transactions found.[/red]")
        return

    console.print("\n  [bold]Select recurring transaction to update:[/bold]")
    console.print("  [dim]Type 'back' at any prompt to return to menu.[/dim]")
    for i, p in enumerate(pages, 1):
        name = get_title(p)
        amount = get_number(p, "Amount")
        due = get_date(p, "Next Due Date")
        active = get_checkbox(p, "Is Active")
        active_tag = "" if active else " [dim](inactive)[/dim]"
        console.print(f"    [cyan]{i}.[/cyan] {name}{active_tag}  [bold]${amount:,.2f}[/bold]  next: {due or '—'}")

    try:
        idx = int(prompt("  Recurring #: ")) - 1
        page = pages[idx]
    except (ValueError, IndexError):
        console.print("  [red]❌ Invalid selection.[/red]")
        return

    old_name     = get_title(page)
    old_amount   = get_number(page, "Amount")
    old_due      = get_date(page, "Next Due Date")
    old_active   = get_checkbox(page, "Is Active")
    old_autopay  = get_checkbox(page, "Auto Pay")
    old_acct_ids = get_relation_ids(page, "Account")
    old_dest_ids = get_relation_ids(page, "Destination Account")

    accounts = get_all_accounts()
    acct_by_id = {a["id"]: get_title(a) for a in accounts}

    old_acct_name = acct_by_id.get(old_acct_ids[0], old_acct_ids[0]) if old_acct_ids else "—"
    old_dest_name = acct_by_id.get(old_dest_ids[0], old_dest_ids[0]) if old_dest_ids else "—"

    console.print(f"\n  Editing: [bold]{old_name}[/bold]")
    console.print("  [dim](Press Enter to keep current value)[/dim]\n")

    raw = prompt(f"  Name (current: {old_name}): ").strip()
    new_name = raw if raw else None

    raw = prompt(f"  Amount (current: ${old_amount:,.2f}): $").strip()
    if raw:
        try:
            new_amount = float(raw)
        except ValueError:
            console.print("  [red]❌ Invalid amount.[/red]")
            return
    else:
        new_amount = None

    raw = prompt(f"  Next Due Date YYYY-MM-DD (current: {old_due or '—'}): ").strip()
    if raw:
        try:
            datetime.strptime(raw, "%Y-%m-%d")
            new_due = raw
        except ValueError:
            console.print("  [red]❌ Invalid date format. Use YYYY-MM-DD.[/red]")
            return
    else:
        new_due = None

    raw = prompt(f"  Is Active? y/n (current: {'y' if old_active else 'n'}): ").strip().lower()
    new_active = (raw == "y") if raw in ("y", "n") else None

    raw = prompt(f"  Auto Pay? y/n (current: {'y' if old_autopay else 'n'}): ").strip().lower()
    new_autopay = (raw == "y") if raw in ("y", "n") else None

    console.print("\n  [bold]Accounts:[/bold]")
    for i, a in enumerate(accounts, 1):
        console.print(f"    [cyan]{i}.[/cyan] {get_title(a)}")

    console.print(f"\n  Account (current: [bold]{old_acct_name}[/bold]):")
    raw = prompt("  New account # (Enter to keep): ").strip()
    if raw:
        try:
            new_acct_ids = [accounts[int(raw) - 1]["id"]]
        except (ValueError, IndexError):
            console.print("  [red]❌ Invalid selection.[/red]")
            return
    else:
        new_acct_ids = None

    console.print(f"\n  Destination Account (current: [bold]{old_dest_name}[/bold], 'none' to clear):")
    console.print("  [dim](see account list above)[/dim]")
    raw = prompt("  New destination # (Enter to keep): ").strip().lower()
    if raw == "none":
        new_dest_ids = []
    elif raw:
        try:
            new_dest_ids = [accounts[int(raw) - 1]["id"]]
        except (ValueError, IndexError):
            console.print("  [red]❌ Invalid selection.[/red]")
            return
    else:
        new_dest_ids = None

    if all(v is None for v in [new_name, new_amount, new_due, new_active, new_autopay, new_acct_ids, new_dest_ids]):
        console.print("  [dim]No changes made.[/dim]")
        return

    summary_lines = [f"Recurring: [bold]{old_name}[/bold]"]
    if new_name is not None:
        summary_lines.append(f"Name:     {old_name} → [bold]{new_name}[/bold]")
    if new_amount is not None:
        diff = new_amount - old_amount
        sign = "+" if diff >= 0 else ""
        diff_color = "green" if diff >= 0 else "red"
        summary_lines.append(f"Amount:   ${old_amount:,.2f} → [bold]${new_amount:,.2f}[/bold]  ([{diff_color}]{sign}${diff:,.2f}[/{diff_color}])")
    if new_due is not None:
        summary_lines.append(f"Due Date: {old_due or '—'} → [bold]{new_due}[/bold]")
    if new_active is not None:
        summary_lines.append(f"Is Active: {'y' if old_active else 'n'} → [bold]{'y' if new_active else 'n'}[/bold]")
    if new_autopay is not None:
        summary_lines.append(f"Auto Pay: {'y' if old_autopay else 'n'} → [bold]{'y' if new_autopay else 'n'}[/bold]")
    if new_acct_ids is not None:
        new_acct_name = acct_by_id.get(new_acct_ids[0], new_acct_ids[0]) if new_acct_ids else "—"
        summary_lines.append(f"Account:  {old_acct_name} → [bold]{new_acct_name}[/bold]")
    if new_dest_ids is not None:
        new_dest_name = acct_by_id.get(new_dest_ids[0], new_dest_ids[0]) if new_dest_ids else "[dim]cleared[/dim]"
        summary_lines.append(f"Dest Acct: {old_dest_name} → [bold]{new_dest_name}[/bold]")

    if not confirm(summary_lines):
        return

    props = {}
    if new_name is not None:
        props["Name"] = make_title(new_name)
    if new_amount is not None:
        props["Amount"] = make_number(new_amount)
    if new_due is not None:
        props["Next Due Date"] = make_date(new_due)
    if new_active is not None:
        props["Is Active"] = make_checkbox(new_active)
    if new_autopay is not None:
        props["Auto Pay"] = make_checkbox(new_autopay)
    if new_acct_ids is not None:
        props["Account"] = make_relation(new_acct_ids)
    if new_dest_ids is not None:
        props["Destination Account"] = make_relation(new_dest_ids)

    display_name = new_name or old_name
    if dry_run:
        console.print(f"  [yellow]🔍 Would update recurring: [bold]{display_name}[/bold][/yellow]")
    else:
        result = update_page(page["id"], props)
        if result:
            console.print(f"  [green]✅ {display_name} updated.[/green]")
