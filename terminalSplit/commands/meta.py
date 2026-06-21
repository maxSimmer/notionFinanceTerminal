import os
from rich.panel import Panel

from terminalSplit.ui import console, prompt, UserCancelled
from terminalSplit.helpers import prefetch_startup_data
from terminalSplit.commands.accounts import cmd_balance, _new_account, _update_account
from terminalSplit.commands.goals import cmd_goals, _new_goal, _update_goal
from terminalSplit.commands.recurring import cmd_bills, _new_recurring, _update_recurring
from terminalSplit.commands.monthly import cmd_startup_panel, _update_monthly_budget


def cmd_help():
    """Show help."""
    content = (
        " [cyan] 1.[/cyan] [bold]add[/bold]        Log an expense or income\n"
        "                [dim]add --batch / -b (multiple transactions, same day)[/dim]\n"
        "                [dim]add --income / -i (log as income)[/dim]\n"
        "                [dim]add --dry-run (preview only)[/dim]\n"
        " [cyan] 2.[/cyan] [bold]transfer[/bold]   Move money between accounts\n"
        "                [dim]transfer --dry-run (preview only)[/dim]\n"
        " [cyan] 3.[/cyan] [bold]update[/bold]     Update account balances, goal amounts, monthly budgets, or recurring transactions\n"
        "                [dim]update --dry-run (preview only)[/dim]\n"
        " [cyan] 4.[/cyan] [bold]new[/bold]        Create a new account, goal, or recurring transaction\n"
        "                [dim]new --dry-run (preview only)[/dim]\n"
        " [cyan] 5.[/cyan] [bold]balance[/bold]    Show all account balances\n"
        " [cyan] 6.[/cyan] [bold]month[/bold]      Show current month summary\n"
        " [cyan] 7.[/cyan] [bold]recent[/bold]     Show last 10 transactions\n"
        " [cyan] 8.[/cyan] [bold]bills[/bold]      Show upcoming bills (30 days)\n"
        " [cyan] 9.[/cyan] [bold]goals[/bold]      Show goal progress\n"
        " [cyan]10.[/cyan] [bold]rollover[/bold]   Close month & create next\n"
        "                [dim]rollover --dry-run (preview only)[/dim]\n"
        " [cyan]11.[/cyan] [bold]recurring[/bold]  Generate recurring transactions\n"
        "                [dim]recurring --dry-run (preview only)[/dim]\n"
        " [cyan]12.[/cyan] [bold]clear[/bold]      Clear terminal and refresh startup info\n"
        " [cyan]13.[/cyan] [bold]help[/bold]       Show this help\n"
        " [cyan]14.[/cyan] [bold]quit[/bold]       Exit"
    )
    console.print(Panel(content, title="[bold yellow]💰 Budget CLI[/bold yellow]", border_style="blue", padding=(0, 1)))


def cmd_clear():
    """Clear the terminal and redisplay startup info."""
    os.system('clear')
    console.print("  [bold]💰 Budget CLI[/bold]  [dim]Type [bold]help[/bold] for commands[/dim]")
    console.rule(style="dim")
    accounts, month, expense_txs = prefetch_startup_data()
    cmd_startup_panel(accounts, month, expense_txs)


def cmd_new(dry_run=False):
    """Create a new account, goal, or recurring transaction."""
    console.print("\n  [bold]What would you like to create?[/bold]")
    if dry_run:
        console.print("  [yellow bold]⚠ DRY RUN — nothing will be saved[/yellow bold]")
    console.print("    [cyan]1.[/cyan] Account")
    console.print("    [cyan]2.[/cyan] Goal")
    console.print("    [cyan]3.[/cyan] Recurring transaction")

    try:
        choice = prompt("  Choice: ").strip()
        if choice == "2":
            _new_goal(dry_run=dry_run)
        elif choice == "3":
            _new_recurring(dry_run=dry_run)
        else:
            _new_account(dry_run=dry_run)
    except UserCancelled:
        console.print("  [dim]Returning to menu.[/dim]")


def cmd_update(dry_run=False):
    """Update an account balance, goal amounts, monthly budget, or recurring transaction."""
    console.print("\n  [bold]What would you like to update?[/bold]")
    if dry_run:
        console.print("  [yellow bold]⚠ DRY RUN — nothing will be saved[/yellow bold]")
    console.print("    [cyan]1.[/cyan] Account balance")
    console.print("    [cyan]2.[/cyan] Goal amounts")
    console.print("    [cyan]3.[/cyan] Monthly budget")
    console.print("    [cyan]4.[/cyan] Recurring transaction")

    try:
        choice = prompt("  Choice: ").strip()
        if choice == "2":
            _update_goal(dry_run=dry_run)
        elif choice == "3":
            _update_monthly_budget(dry_run=dry_run)
        elif choice == "4":
            _update_recurring(dry_run=dry_run)
        else:
            _update_account(dry_run=dry_run)
    except UserCancelled:
        console.print("  [dim]Returning to menu.[/dim]")
