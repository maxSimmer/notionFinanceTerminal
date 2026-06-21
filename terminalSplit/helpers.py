from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from dateutil.relativedelta import relativedelta
from terminalSplit.config import ACCOUNTS_DB_ID, TRANSACTIONS_DB_ID, MONTHLY_DB_ID
from terminalSplit.api import query_database, update_page, get_page, get_database_select_options
from terminalSplit.properties import get_number, get_title, make_number, make_date

_categories_cache = None
_types_cache = None


def get_categories():
    global _categories_cache
    if _categories_cache is None:
        _categories_cache = get_database_select_options(TRANSACTIONS_DB_ID, "Category")
    return _categories_cache


def get_types():
    global _types_cache
    if _types_cache is None:
        _types_cache = get_database_select_options(TRANSACTIONS_DB_ID, "Type")
    return _types_cache


def adjust_account_balance(account_id, amount, tx_type):
    """Adjust an account's balance based on transaction type.
    Expenses subtract, Income adds, Transfers subtract (from source)."""
    if not account_id:
        return
    account = get_page(account_id)
    if not account:
        print("  ⚠️  Could not fetch account to update balance.")
        return

    current_balance = get_number(account, "Current Balance")
    account_name = get_title(account)

    if tx_type == "Income":
        new_balance = current_balance + amount
    else:  # Expense or Transfer
        new_balance = current_balance - amount

    result = update_page(account_id, {
        "Current Balance": make_number(new_balance),
        "Last Updated": make_date(datetime.now().strftime("%Y-%m-%d")),
    })
    if result:
        diff = new_balance - current_balance
        sign = "+" if diff >= 0 else ""
        print(f"  💰 {account_name}: ${current_balance:,.2f} → ${new_balance:,.2f} ({sign}${diff:,.2f})")


def get_all_accounts():
    return query_database(ACCOUNTS_DB_ID, sorts=[{"property": "Account Name", "direction": "ascending"}])


def prefetch_startup_data():
    """Fetch accounts and active month in parallel, then fetch transactions."""
    with ThreadPoolExecutor(max_workers=2) as ex:
        accounts_f = ex.submit(get_all_accounts)
        month_f = ex.submit(get_active_month)
        accounts = accounts_f.result()
        month = month_f.result()

    expense_txs = []
    if month:
        month_name = get_title(month)
        try:
            month_dt = datetime.strptime(month_name, "%Y-%m")
            start_date = month_dt.strftime("%Y-%m-01")
            end_date = (month_dt + relativedelta(months=1) - timedelta(days=1)).strftime("%Y-%m-%d")
            expense_txs = query_database(TRANSACTIONS_DB_ID, {
                "and": [
                    {"property": "Date", "date": {"on_or_after": start_date}},
                    {"property": "Date", "date": {"on_or_before": end_date}},
                    {"property": "Type", "select": {"equals": "Expense"}}
                ]
            })
        except ValueError:
            pass

    return accounts, month, expense_txs


def get_active_month():
    pages = query_database(
        MONTHLY_DB_ID,
        filter_obj={"property": "Status", "select": {"equals": "Active"}},
    )
    return pages[0] if pages else None
