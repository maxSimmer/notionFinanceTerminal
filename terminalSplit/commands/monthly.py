import calendar
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from rich.console import Group
from rich.table import Table
from rich.columns import Columns
from rich.text import Text
from rich import box as rich_box

from terminalSplit.config import TRANSACTIONS_DB_ID, MONTHLY_DB_ID
from terminalSplit.api import create_page, update_page, query_database, get_page
from terminalSplit.properties import (
    get_title, get_number, get_select,
    make_title, make_number, make_select,
)
from terminalSplit.helpers import get_active_month
from terminalSplit.ui import console, prompt, confirm


def _get_expense_categories(month_name, expense_txs):
    """Build sorted category totals from expense transactions."""
    if expense_txs is None:
        try:
            month_dt = datetime.strptime(month_name, "%Y-%m")
        except ValueError:
            return []
        start_date = month_dt.strftime("%Y-%m-01")
        end_date = (month_dt + relativedelta(months=1) - timedelta(days=1)).strftime("%Y-%m-%d")
        expense_txs = query_database(TRANSACTIONS_DB_ID, {
            "and": [
                {"property": "Date", "date": {"on_or_after": start_date}},
                {"property": "Date", "date": {"on_or_before": end_date}},
                {"property": "Type", "select": {"equals": "Expense"}}
            ]
        })

    category_totals = {}
    for tx in expense_txs:
        cat = get_select(tx, "Category") or "Uncategorized"
        tx_type = get_select(tx, "Type")
        if cat == "Transfer":
            if tx_type == "Transfer":
                continue
            cat = "Debt Payments"
        category_totals[cat] = category_totals.get(cat, 0) + get_number(tx, "Amount")

    return sorted(category_totals.items(), key=lambda x: x[1], reverse=True)


def _build_monthly_table(month, expense_txs=None):
    """Build and return the monthly summary Rich Table."""
    month_name = get_title(month)
    planned_inc = get_number(month, "Planned Income")
    actual_inc = get_number(month, "Actual Income (Rollup)")
    planned_exp = get_number(month, "Planned Expenses")
    actual_exp = get_number(month, "Actual Expenses (Rollup)")
    rollover = get_number(month, "Rollover From Previous")
    net = get_number(month, "Net")

    try:
        month_dt = datetime.strptime(month_name, "%Y-%m")
    except ValueError:
        return None

    days_in_month = calendar.monthrange(month_dt.year, month_dt.month)[1]
    day_of_month = datetime.now().day
    month_label = month_dt.strftime("%B %Y").upper()
    prev_month_name = (month_dt - relativedelta(months=1)).strftime("%B")

    inc_color = "green" if actual_inc >= planned_inc else ("yellow" if actual_inc >= planned_inc * 0.9 else "red")
    exp_color = "green" if actual_exp <= planned_exp else "red"
    net_color = "green" if net >= 0 else "red"

    inc_pct = int(actual_inc / planned_inc * 100) if planned_inc else 0
    exp_pct = int(actual_exp / planned_exp * 100) if planned_exp else 0
    savings_rate = int(net / actual_inc * 100) if actual_inc else 0

    def var_str(actual, planned):
        diff = actual - planned
        color = "green" if diff >= 0 else "red"
        sign = "+" if diff >= 0 else "-"
        return f"[{color}]{sign}${abs(diff):,.2f}[/{color}]"

    table = Table(
        title=f"[bold]{month_label}[/bold] [dim]· DAY {day_of_month} OF {days_in_month}[/dim]",
        box=rich_box.SIMPLE_HEAD,
        padding=(0, 1),
        title_justify="left",
    )
    table.add_column("", style="bold")
    table.add_column("planned", justify="right", style="dim")
    table.add_column("actual", justify="right")
    table.add_column("variance", justify="right")
    table.add_column("", style="dim")

    table.add_row(
        "Income",
        f"${planned_inc:,.2f}",
        f"[{inc_color}]${actual_inc:,.2f}[/{inc_color}]",
        var_str(actual_inc, planned_inc),
        f"{inc_pct}% of planned",
    )
    table.add_row(
        "Expenses",
        f"${planned_exp:,.2f}",
        f"[{exp_color}]${actual_exp:,.2f}[/{exp_color}]",
        var_str(planned_exp, actual_exp),
        f"{exp_pct}% of budget used",
    )
    if rollover:
        table.add_row(
            "Rollover",
            "",
            f"[green]+${rollover:,.2f}[/green]",
            "",
            f"from {prev_month_name}",
        )
    table.add_row(
        "[bold]Net[/bold]",
        "",
        f"[{net_color}]${net:,.2f}[/{net_color}]",
        "",
        f"savings rate: {savings_rate}%",
    )

    return table


def cmd_startup_panel(accounts, month=None, expense_txs=None):
    """Display accounts (left) and monthly summary (right) side by side, then pace/top-spend lines."""
    from terminalSplit.commands.accounts import _build_accounts_table

    if month is None:
        month = get_active_month()

    acct_table = _build_accounts_table(accounts) if accounts else None

    if not month:
        if acct_table:
            console.print(acct_table)
        console.rule(style="dim")
        return

    from terminalSplit.commands.goals import _build_goals_renderable
    from terminalSplit.commands.recurring import _build_bills_renderable

    month_name = get_title(month)
    monthly_table = _build_monthly_table(month, expense_txs)
    sorted_cats = _get_expense_categories(month_name, expense_txs)
    goals_renderable = _build_goals_renderable()
    bills_renderable = _build_bills_renderable()

    if acct_table and monthly_table:
        right_side = Group(monthly_table, goals_renderable, Text(""), bills_renderable)
        console.print(Columns([acct_table, right_side], padding=(0, 4)))
        console.print()
    elif acct_table:
        console.print(acct_table)
    elif monthly_table:
        console.print(monthly_table)

    # Spending pace + top spend below the side-by-side tables
    try:
        month_dt = datetime.strptime(month_name, "%Y-%m")
        days_in_month = calendar.monthrange(month_dt.year, month_dt.month)[1]
        day_of_month = datetime.now().day
        actual_exp = get_number(month, "Actual Expenses (Rollup)")
        planned_exp = get_number(month, "Planned Expenses")
        remaining = days_in_month - day_of_month
        if days_in_month > 0:
            daily_pace = actual_exp / days_in_month
            projected = actual_exp + remaining * daily_pace
            over_under = projected - planned_exp
            direction = "over" if over_under > 0 else "under"
            pace_color = "red" if over_under > 0 else "green"
            console.print(
                f"  [dim]spending pace:[/dim] [bold][{pace_color}]${daily_pace:,.2f}/day[/{pace_color}][/bold]"
                f" [dim]· at this rate[/dim] "
                f"[dim]${actual_exp:,.2f} + {remaining}x${daily_pace:,.2f} = ${projected:,.0f}/mo"
                f" vs ${planned_exp:,.0f} budget →[/dim] "
                f"[{pace_color}]{direction} by ~${abs(over_under):,.0f}[/{pace_color}]"
            )
    except (ValueError, ZeroDivisionError):
        pass

    if sorted_cats:
        top = "  ".join(
            f"[cyan]{c}[/cyan] [dim]${v:,.0f}[/dim]" for c, v in sorted_cats
        )
        grid = Table.grid(padding=0)
        grid.add_column(no_wrap=True)
        grid.add_column()
        grid.add_row("  [dim]top spend:[/dim] ", top)
        console.print(grid)

    console.rule(style="dim")


def cmd_startup_summary(month=None, expense_txs=None):
    """Display a compact monthly summary on client load (standalone fallback)."""
    if month is None:
        month = get_active_month()
    if not month:
        return
    table = _build_monthly_table(month, expense_txs)
    if table:
        console.print(table)


def cmd_month():
    """Show current month summary."""
    month = get_active_month()
    if not month:
        console.print("  No active monthly budget found.")
        return

    month = get_page(month["id"])

    month_name = get_title(month)
    planned_inc = get_number(month, "Planned Income")
    actual_inc = get_number(month, "Actual Income (Rollup)")
    planned_exp = get_number(month, "Planned Expenses")
    actual_exp = get_number(month, "Actual Expenses (Rollup)")
    rollover_from = get_number(month, "Rollover From Previous")
    net = get_number(month, "Net")

    inc_color = "green" if actual_inc >= planned_inc else ("yellow" if actual_inc >= planned_inc * 0.9 else "red")
    exp_color = "green" if actual_exp <= planned_exp else "red"
    net_color = "green" if net >= 0 else "red"

    table = Table(
        title=f"[bold cyan]📅 Monthly Budget: {month_name}[/bold cyan]",
        box=rich_box.SIMPLE_HEAVY,
        padding=(0, 1),
    )
    table.add_column("", style="bold")
    table.add_column("Planned", justify="right", style="dim")
    table.add_column("Actual", justify="right")

    table.add_row("Income", f"${planned_inc:,.2f}", f"[{inc_color}]${actual_inc:,.2f}[/{inc_color}]")
    table.add_row("Expenses", f"${planned_exp:,.2f}", f"[{exp_color}]${actual_exp:,.2f}[/{exp_color}]")
    table.add_section()
    table.add_row("[dim]Rollover From Previous[/dim]", "", f"${rollover_from:,.2f}")
    table.add_row("[bold]Net This Month[/bold]", "", f"[{net_color}]${net:,.2f}[/{net_color}]")

    console.print(table)


def cmd_rollover(dry_run=False):
    """Close current month and create next month with rollover."""
    month = get_active_month()
    if not month:
        print("  No active monthly budget found.")
        return

    month_name = get_title(month)
    eom = get_number(month, "Net")

    eom_color = "green" if eom >= 0 else "red"
    console.print(f"\n  Closing month: [bold]{month_name}[/bold]")
    console.print(f"  End of Month Balance: [{eom_color}][bold]${eom:,.2f}[/bold][/{eom_color}]")

    if dry_run:
        console.print("  [dim][DRY RUN] No changes will be made.[/dim]\n")
    else:
        ans = input("  Proceed? (y/n): ").strip().lower()
        if ans != "y":
            console.print("  [yellow]Cancelled.[/yellow]")
            return

    try:
        current_date = datetime.strptime(month_name, "%Y-%m")
        next_date = current_date + relativedelta(months=1)
        next_month_str = next_date.strftime("%Y-%m")
    except ValueError:
        if dry_run:
            print("  [DRY RUN] Could not parse month name — skipping next month calculation.")
            return
        next_month_str = input("  Next month (YYYY-MM): ").strip()

    if dry_run:
        console.print(f"  [dim][DRY RUN] Would close month \"{month_name}\" (Status → Closed, Rollover To Next → ${eom:,.2f})[/dim]")
        console.print(f"  [dim][DRY RUN] Would create new month \"{next_month_str}\" (Rollover From Previous: ${eom:,.2f}, Status: Active)[/dim]")
        return

    update_page(month["id"], {
        "Status": make_select("Closed"),
        "Rollover To Next": make_number(eom),
    })

    props = {
        "Month": make_title(next_month_str),
        "Rollover From Previous": make_number(eom),
        "Planned Income": make_number(0),
        "Planned Expenses": make_number(0),
        "Status": make_select("Active"),
    }
    result = create_page(MONTHLY_DB_ID, props)
    if result:
        console.print(f"  [green]✅ Month [bold]{month_name}[/bold] closed. New month [bold]{next_month_str}[/bold] created with [bold]${eom:,.2f}[/bold] rollover.[/green]")


def _update_monthly_budget(dry_run=False):
    """Update planned income and/or planned expenses for any month."""
    months = query_database(MONTHLY_DB_ID, sorts=[{"property": "Month", "direction": "descending"}])
    if not months:
        console.print("  [red]No monthly budgets found.[/red]")
        return

    console.print("\n  [bold]Select a month to update:[/bold]")
    console.print("  [dim]Type 'back' at any prompt to return to menu.[/dim]")
    for i, m in enumerate(months, 1):
        name = get_title(m)
        status = get_select(m, "Status")
        planned_income = get_number(m, "Planned Income")
        planned_expenses = get_number(m, "Planned Expenses")
        status_tag = f" [dim]({status})[/dim]" if status else ""
        console.print(
            f"    [cyan]{i}.[/cyan] {name}{status_tag}  "
            f"Income: [green]${planned_income:,.2f}[/green]  "
            f"Expenses: [red]${planned_expenses:,.2f}[/red]"
        )

    try:
        idx = int(prompt("  Month #: ")) - 1
        month = months[idx]
    except (ValueError, IndexError):
        console.print("  [red]❌ Invalid selection.[/red]")
        return

    month_name = get_title(month)
    old_income = get_number(month, "Planned Income")
    old_expenses = get_number(month, "Planned Expenses")

    raw = prompt(f"  New planned income (Enter to keep ${old_income:,.2f}): $").strip()
    if raw:
        try:
            new_income = float(raw)
        except ValueError:
            console.print("  [red]❌ Invalid amount.[/red]")
            return
    else:
        new_income = None

    raw = prompt(f"  New planned expenses (Enter to keep ${old_expenses:,.2f}): $").strip()
    if raw:
        try:
            new_expenses = float(raw)
        except ValueError:
            console.print("  [red]❌ Invalid amount.[/red]")
            return
    else:
        new_expenses = None

    if new_income is None and new_expenses is None:
        console.print("  [dim]No changes made.[/dim]")
        return

    summary_lines = [f"Month: [bold]{month_name}[/bold]"]
    if new_income is not None:
        diff = new_income - old_income
        sign = "+" if diff >= 0 else ""
        diff_color = "green" if diff >= 0 else "red"
        summary_lines.append(
            f"Planned Income:    ${old_income:,.2f} → [bold]${new_income:,.2f}[/bold]  ([{diff_color}]{sign}${diff:,.2f}[/{diff_color}])"
        )
    if new_expenses is not None:
        diff = new_expenses - old_expenses
        sign = "+" if diff >= 0 else ""
        diff_color = "green" if diff >= 0 else "red"
        summary_lines.append(
            f"Planned Expenses:  ${old_expenses:,.2f} → [bold]${new_expenses:,.2f}[/bold]  ([{diff_color}]{sign}${diff:,.2f}[/{diff_color}])"
        )

    if not confirm(summary_lines):
        return

    props = {}
    if new_income is not None:
        props["Planned Income"] = make_number(new_income)
    if new_expenses is not None:
        props["Planned Expenses"] = make_number(new_expenses)

    if dry_run:
        console.print(f"  [yellow]🔍 Would update budget: [bold]{month_name}[/bold][/yellow]")
    else:
        result = update_page(month["id"], props)
        if result:
            console.print(f"  [green]✅ {month_name} budget updated.[/green]")