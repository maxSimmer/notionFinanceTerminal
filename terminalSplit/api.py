import requests
from terminalSplit.config import NOTION_API_KEY, NOTION_VERSION, BASE_URL, _sanitize


def headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def query_database(db_id, filter_obj=None, sorts=None, page_size=100):
    """Query a Notion database and return all pages."""
    url = f"{BASE_URL}/databases/{db_id}/query"
    payload = {}
    if filter_obj:
        payload["filter"] = filter_obj
    if sorts:
        payload["sorts"] = sorts
    if page_size:
        payload["page_size"] = page_size

    resp = requests.post(url, headers=headers(), json=payload, timeout=15)
    if resp.status_code != 200:
        print(f"  ❌ API error: {resp.status_code} — {_sanitize(resp.text[:200])}")
        return []
    return resp.json().get("results", [])


def create_page(db_id, properties):
    """Create a page in a database."""
    url = f"{BASE_URL}/pages"
    payload = {
        "parent": {"database_id": db_id},
        "properties": properties,
    }
    resp = requests.post(url, headers=headers(), json=payload, timeout=15)
    if resp.status_code != 200:
        print(f"  ❌ API error: {resp.status_code} — {_sanitize(resp.text[:200])}")
        return None
    return resp.json()


def update_page(page_id, properties):
    """Update a page's properties."""
    url = f"{BASE_URL}/pages/{page_id}"
    payload = {"properties": properties}
    resp = requests.patch(url, headers=headers(), json=payload, timeout=15)
    if resp.status_code != 200:
        print(f"  ❌ API error: {resp.status_code} — {_sanitize(resp.text[:200])}")
        return None
    return resp.json()


def get_page(page_id):
    """Fetch a single page by ID."""
    url = f"{BASE_URL}/pages/{page_id}"
    resp = requests.get(url, headers=headers())
    if resp.status_code != 200:
        return None
    return resp.json()


def get_database_select_options(db_id, property_name):
    """Fetch the available select options for a property from a Notion database schema."""
    url = f"{BASE_URL}/databases/{db_id}"
    resp = requests.get(url, headers=headers())
    if resp.status_code != 200:
        return []
    prop = resp.json().get("properties", {}).get(property_name, {})
    return [o["name"] for o in prop.get("select", {}).get("options", [])]
