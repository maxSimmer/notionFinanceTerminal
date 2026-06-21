from rich.console import Group
from rich.text import Text

from terminalSplit.config import GOALS_DB_ID, ACCOUNTS_DB_ID
from terminalSplit.api import create_page, update_page, query_database
from terminalSplit.properties import (
    get_title, get_number, get_select,
    make_title, make_number, make_select, make_relation,
)
from terminalSplit.ui import console, prompt, confirm


def _calc_progress(current, target, starting_debt):
    """Calculate progress % for a goal.

    Savings goals:  current / target  (target > 0)
    Debt goals:     amount paid off / starting_debt  (target == 0, starting_debt > 0)
                    current is negative (account balance), so paid = starting_debt - abs(current)
    """
    is_debt_goal = target == 0 and starting_debt > 0
    if is_debt_goal:
        paid_off = starting_debt - abs(current)
        return int(max(0, min(100, paid_off / starting_debt * 100))), True
    elif target > 0:
        return int(max(0, min(100, current / target * 100))), False
    else:
        return 0, False


def _build_goal_rows(pages):
    """Return list of (prefix, name, bar, amount_str, priority) tuples."""
    bar_len = 16
    rows = []
    for p in pages:
        name = get_title(p)
        target = get_number(p, "Target Amount")
        current = get_number(p, "Current Amount")
        starting_debt = get_number(p, "Starting Debt")
        priority = get_select(p, "Priority") or ""

        pct, is_debt = _calc_progress(current, target, starting_debt)

        filled = int(bar_len * pct / 100)
        if pct >= 75:
            bar_color = "green"
        elif pct >= 40:
            bar_color = "yellow"
        else:
            bar_color = "red"
        bar = f"[{bar_color}]{'█' * filled}[/{bar_color}][dim]{'░' * (bar_len - filled)}[/dim]"

        prefix = "[bold red]![/bold red]" if priority in ("Critical", "High") else "[dim]·[/dim]"

        if is_debt:
            paid = starting_debt - abs(current)
            amount_str = f"[green]${paid:,.0f}[/green] paid / ${starting_debt:,.0f} ({pct}%)"
        else:
            amount_str = f"${current:,.0f} / ${target:,.0f} ({pct}%)"

        rows.append((prefix, name, bar, amount_str, priority))
    return rows


def _build_goals_renderable(pages=None):
    """Return a Group renderable of goal rows (for embedding in a Columns layout)."""
    if pages is None:
        pages = query_database(
            GOALS_DB_ID,
            filter_obj={"property": "Status", "select": {"equals": "In Progress"}},
        )
    if not pages:
        return Text("")

    rows = _build_goal_rows(pages)
    name_w = max(len(r[1]) for r in rows) if rows else 20
    lines = [Text.from_markup("  [dim]GOALS[/dim]")]
    for prefix, name, bar, amount_str, priority in rows:
        pri_tag = f"[dim]{priority}[/dim]" if priority else ""
        lines.append(Text.from_markup(
            f"  {prefix} [bold]{name:<{name_w}}[/bold]  {bar}  {amount_str}  {pri_tag}"
        ))
    return Group(*lines)


def cmd_goals():
    """Show goal progress."""
    pages = query_database(
        GOALS_DB_ID,
        filter_obj={"property": "Status", "select": {"equals": "In Progress"}},
    )
    if not pages:
        console.print("  No active goals found.")
        return

    rows = _build_goal_rows(pages)
    name_w = max(len(r[1]) for r in rows) if rows else 20

    console.print("  [dim]GOALS[/dim]")
    for prefix, name, bar, amount_str, priority in rows:
        pri_tag = f"[dim]{priority}[/dim]" if priority else ""
        console.print(f"  {prefix} [bold]{name:<{name_w}}[/bold]  {bar}  {amount_str}  {pri_tag}")

    console.rule(style="dim")


def _new_goal(dry_run=False):
    """Create a new savings or debt payoff goal."""
    console.print("\n  [bold cyan]➕ New Goal[/bold cyan]")
    console.print("  [dim]Type 'back' at any prompt to return to menu.[/dim]\n")

    name = prompt("  Goal name: ").strip()
    if not name:
        console.print("  [red]❌ Name required.[/red]")
        return

    # --- Linked account (optional) ---
    accounts = query_database(
        ACCOUNTS_DB_ID,
        filter_obj={"property": "Is Active", "checkbox": {"equals": True}},
    )
    accounts.sort(key=lambda a: get_title(a).lower())

    linked_account_id = None
    linked_account_name = None
    is_credit_card = False

    if accounts:
        console.print("  [bold]Link an account?[/bold] [dim](Enter to skip)[/dim]")
        for i, a in enumerate(accounts, 1):
            acct_name = get_title(a)
            acct_type = get_select(a, "Type") or "Unknown"
            balance = get_number(a, "Current Balance")
            balance_str = f"[red]${balance:,.2f}[/red]" if balance < 0 else f"[green]${balance:,.2f}[/green]"
            console.print(f"    [cyan]{i}.[/cyan] {acct_name} [dim]({acct_type})[/dim] {balance_str}")

        raw = prompt("  Account # (or Enter to skip): ").strip()
        if raw:
            try:
                idx = int(raw) - 1
                acct = accounts[idx]
                linked_account_id = acct["id"]
                linked_account_name = get_title(acct)
                acct_type = get_select(acct, "Type") or ""
                is_credit_card = acct_type == "Credit Card"
                console.print(f"  [dim]Linked: {linked_account_name}[/dim]")
            except (ValueError, IndexError):
                console.print("  [yellow]⚠ Invalid selection — skipping account link.[/yellow]")

    # --- Goal type branching ---
    if is_credit_card:
        # Debt payoff: target is always $0, progress tracked via Starting Debt
        console.print("\n  [dim]Credit card detected — configuring as a debt payoff goal.[/dim]")
        target = 0.0
        starting_debt = 0.0
        default_category = "Debt Payoff"

        raw = prompt("  Starting debt (what you owed when you started tracking): $").strip()
        try:
            starting_debt = float(raw) if raw else 0.0
        except ValueError:
            console.print("  [red]❌ Invalid amount.[/red]")
            return
    else:
        # Savings goal: needs a target amount, no starting debt
        target = 0.0
        starting_debt = 0.0
        default_category = "Other"

        try:
            target = float(prompt("  Target amount: $"))
        except ValueError:
            console.print("  [red]❌ Invalid amount.[/red]")
            return

    # --- Monthly contribution ---
    raw = prompt("  Monthly contribution [$0.00]: $").strip()
    try:
        monthly = float(raw) if raw else 0.0
    except ValueError:
        console.print("  [red]❌ Invalid amount.[/red]")
        return

    # --- Confirm ---
    summary_lines = [f"Name:                 [bold]{name}[/bold]"]
    if is_credit_card:
        summary_lines.append("Type:                 [red]Debt Payoff[/red]")
        summary_lines.append(f"Starting Debt:        [bold]${starting_debt:,.2f}[/bold]")
        summary_lines.append("Target:               $0.00 (paid off)")
    else:
        summary_lines.append("Type:                 [green]Savings[/green]")
        summary_lines.append(f"Target:               [bold]${target:,.2f}[/bold]")
    summary_lines.append(f"Monthly contribution: ${monthly:,.2f}")
    if linked_account_name:
        summary_lines.append(f"Linked account:       {linked_account_name}")

    if not confirm(summary_lines):
        return

    # --- Build and save ---
    props = {
        "Goal Name": make_title(name),
        "Target Amount": make_number(target),
        "Monthly Contribution": make_number(monthly),
        "Status": make_select("In Progress"),
        "Category": make_select(default_category),
    }
    if starting_debt > 0:
        props["Starting Debt"] = make_number(starting_debt)
    if linked_account_id:
        props["Linked Account"] = make_relation([linked_account_id])

    if dry_run:
        console.print(f"  [yellow]🔍 Would create goal: [bold]{name}[/bold][/yellow]")
        for line in summary_lines:
            console.print(f"    [yellow dim]{line}[/yellow dim]")
    else:
        result = create_page(GOALS_DB_ID, props)
        if result:
            console.print(f"  [green]✅ Goal [bold]{name}[/bold] created.[/green]")


def _update_goal(dry_run=False):
    """Update a goal — adapts prompts based on whether it's a debt or savings goal."""
    goals = query_database(GOALS_DB_ID)
    goals.sort(key=lambda g: get_title(g).lower())
    if not goals:
        console.print("  [red]No goals found.[/red]")
        return

    console.print("\n  [bold]Select goal to update:[/bold]")
    console.print("  [dim]Type 'back' at any prompt to return to menu.[/dim]")
    for i, g in enumerate(goals, 1):
        name = get_title(g)
        current = get_number(g, "Current Amount")
        target = get_number(g, "Target Amount")
        starting_debt = get_number(g, "Starting Debt")
        pct, is_debt = _calc_progress(current, target, starting_debt)
        if is_debt:
            remaining = abs(current)
            console.print(f"    [cyan]{i}.[/cyan] {name} ([green]${starting_debt - remaining:,.2f}[/green] paid / ${starting_debt:,.2f}  {pct:.0f}%)")
        else:
            console.print(f"    [cyan]{i}.[/cyan] {name} ([green]${current:,.2f}[/green] / ${target:,.2f}  {pct:.0f}%)")

    try:
        idx = int(prompt("  Goal #: ")) - 1
        goal = goals[idx]
    except (ValueError, IndexError):
        console.print("  [red]❌ Invalid selection.[/red]")
        return

    goal_name = get_title(goal)
    old_current = get_number(goal, "Current Amount")
    old_target = get_number(goal, "Target Amount")
    old_starting_debt = get_number(goal, "Starting Debt")
    _, is_debt = _calc_progress(old_current, old_target, old_starting_debt)

    props = {}
    summary_lines = [f"Goal: [bold]{goal_name}[/bold]"]

    if is_debt:
        # Current balance comes from the linked account rollup — not user-editable here.
        console.print(f"  [dim]Debt goal — current balance is pulled from the linked account.[/dim]")

        raw = prompt(f"  New starting debt (Enter to keep ${old_starting_debt:,.2f}): $").strip()
        if not raw:
            console.print("  [dim]No changes made.[/dim]")
            return
        try:
            new_starting_debt = float(raw)
        except ValueError:
            console.print("  [red]❌ Invalid amount.[/red]")
            return

        diff = new_starting_debt - old_starting_debt
        sign = "+" if diff >= 0 else ""
        diff_color = "green" if diff >= 0 else "red"
        summary_lines.append(
            f"Starting Debt: ${old_starting_debt:,.2f} → [bold]${new_starting_debt:,.2f}[/bold]"
            f"  ([{diff_color}]{sign}${diff:,.2f}[/{diff_color}])"
        )
        props["Starting Debt"] = make_number(new_starting_debt)

    else:
        raw = prompt(f"  New current amount (Enter to keep ${old_current:,.2f}): $").strip()
        if raw:
            try:
                new_current = float(raw)
                diff = new_current - old_current
                sign = "+" if diff >= 0 else ""
                diff_color = "green" if diff >= 0 else "red"
                summary_lines.append(
                    f"Current: ${old_current:,.2f} → [bold]${new_current:,.2f}[/bold]"
                    f"  ([{diff_color}]{sign}${diff:,.2f}[/{diff_color}])"
                )
                props["Current Amount"] = make_number(new_current)
            except ValueError:
                console.print("  [red]❌ Invalid amount.[/red]")
                return

        raw = prompt(f"  New target amount (Enter to keep ${old_target:,.2f}): $").strip()
        if raw:
            try:
                new_target = float(raw)
                diff = new_target - old_target
                sign = "+" if diff >= 0 else ""
                diff_color = "green" if diff >= 0 else "red"
                summary_lines.append(
                    f"Target:  ${old_target:,.2f} → [bold]${new_target:,.2f}[/bold]"
                    f"  ([{diff_color}]{sign}${diff:,.2f}[/{diff_color}])"
                )
                props["Target Amount"] = make_number(new_target)
            except ValueError:
                console.print("  [red]❌ Invalid amount.[/red]")
                return

        if not props:
            console.print("  [dim]No changes made.[/dim]")
            return

    if not confirm(summary_lines):
        return

    if dry_run:
        console.print(f"  [yellow]🔍 Would update goal: [bold]{goal_name}[/bold][/yellow]")
    else:
        result = update_page(goal["id"], props)
        if result:
            console.print(f"  [green]✅ {goal_name} updated.[/green]")