# ══════════════════════════════════════════════════
# PROPERTY HELPERS — pure functions over Notion page dicts
# ══════════════════════════════════════════════════

def get_title(page):
    for prop in page["properties"].values():
        if prop["type"] == "title":
            return "".join(t.get("plain_text", "") for t in prop.get("title", []))
    return ""


def get_number(page, prop_name):
    prop = page["properties"].get(prop_name, {})
    if prop.get("type") == "number":
        return prop.get("number") or 0
    if prop.get("type") == "formula":
        return prop.get("formula", {}).get("number") or 0
    if prop.get("type") == "rollup":
        return prop.get("rollup", {}).get("number") or 0
    return 0


def get_select(page, prop_name):
    prop = page["properties"].get(prop_name, {})
    if prop.get("type") == "select" and prop.get("select"):
        return prop["select"]["name"]
    return ""


def get_checkbox(page, prop_name):
    prop = page["properties"].get(prop_name, {})
    if prop.get("type") == "checkbox":
        return prop.get("checkbox", False)
    return False


def get_date(page, prop_name):
    prop = page["properties"].get(prop_name, {})
    if prop.get("type") == "date" and prop.get("date"):
        return prop["date"].get("start", "")
    return ""


def get_rich_text(page, prop_name):
    prop = page["properties"].get(prop_name, {})
    if prop.get("type") == "rich_text":
        return "".join(t.get("plain_text", "") for t in prop.get("rich_text", []))
    return ""


def get_relation_ids(page, prop_name):
    prop = page["properties"].get(prop_name, {})
    if prop.get("type") == "relation":
        return [r["id"] for r in prop.get("relation", [])]
    return []


def make_title(text):
    return {"title": [{"text": {"content": str(text)}}]}


def make_number(n):
    return {"number": n}


def make_select(name):
    return {"select": {"name": name}}


def make_date(date_str):
    return {"date": {"start": date_str}}


def make_checkbox(val):
    return {"checkbox": val}


def make_rich_text(text):
    return {"rich_text": [{"text": {"content": str(text)}}]}


def make_relation(page_ids):
    return {"relation": [{"id": pid} for pid in page_ids]}
