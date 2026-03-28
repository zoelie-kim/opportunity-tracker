import os
import httpx
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["NOTION_TOKEN"]
JOBS_DB = os.environ["NOTION_DATABASE_ID"]
PROGRAMS_DB = os.environ["NOTION_PROGRAMS_DB_ID"]
EVENTS_DB = os.environ["NOTION_EVENTS_DB_ID"]

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

DB_OPTIONS = {
    "1": ("Jobs", JOBS_DB),
    "2": ("Programs & Fellowships", PROGRAMS_DB),
    "3": ("Events", EVENTS_DB),
}

SOURCE_OPTIONS = {
    "1": "YC Work at a Startup",
    "2": "SimplifyJobs",
    "3": "Career Page",
    "4": "LinkedIn",
    "5": "Manual",
}

print("\n🗑️  Database Cleanup Tool\n" + "="*30)

print("\nWhich database?")
for k, (name, _) in DB_OPTIONS.items():
    print(f"  {k}. {name}")
db_choice = input("\nPick a number: ").strip()

if db_choice not in DB_OPTIONS:
    print("Invalid choice")
    exit()

db_name, db_id = DB_OPTIONS[db_choice]

print(f"\nWhat do you want to delete from {db_name}?")
print("  1. Everything (full wipe)")
print("  2. By source (e.g. only SimplifyJobs entries)")
print("  3. By status (e.g. only Rejected entries)")
mode = input("\nPick a number: ").strip()

filter_payload = {}

if mode == "1":
    confirm = input(f"\n⚠️  This will delete ALL entries in {db_name}. Type 'yes' to confirm: ").strip()
    if confirm.lower() != "yes":
        print("Cancelled.")
        exit()

elif mode == "2":
    print("\nWhich source?")
    for k, v in SOURCE_OPTIONS.items():
        print(f"  {k}. {v}")
    print("  6. Other (type your own)")
    src_choice = input("\nPick a number: ").strip()

    if src_choice == "6":
        source_filter = input("Type source name to delete: ").strip()
    elif src_choice in SOURCE_OPTIONS:
        source_filter = SOURCE_OPTIONS[src_choice]
    else:
        print("Invalid choice")
        exit()

    print(f"\n⚠️  Will delete all '{source_filter}' entries from {db_name}.")
    confirm = input("Type 'yes' to confirm: ").strip()
    if confirm.lower() != "yes":
        print("Cancelled.")
        exit()

elif mode == "3":
    print("\nWhich status?")
    statuses = ["Preparing", "Applied", "In Contact", "Accepted", "Rejected"]
    for i, s in enumerate(statuses, 1):
        print(f"  {i}. {s}")
    status_choice = input("\nPick a number: ").strip()
    if not status_choice.isdigit() or int(status_choice) > len(statuses):
        print("Invalid choice")
        exit()
    status_filter = statuses[int(status_choice) - 1]

    print(f"\n⚠️  Will delete all '{status_filter}' entries from {db_name}.")
    confirm = input("Type 'yes' to confirm: ").strip()
    if confirm.lower() != "yes":
        print("Cancelled.")
        exit()
else:
    print("Invalid choice")
    exit()

# Query and delete
print(f"\nFetching entries from {db_name}...")
has_more = True
cursor = None
deleted = 0
kept = 0

while has_more:
    payload = {"page_size": 100}
    if cursor:
        payload["start_cursor"] = cursor

    r = httpx.post(
        f"https://api.notion.com/v1/databases/{db_id}/query",
        headers=headers,
        json=payload,
        timeout=30.0
    )
    data = r.json()
    pages = data.get("results", [])

    for page in pages:
        should_delete = False

        if mode == "1":
            should_delete = True

        elif mode == "2":
            source = page.get("properties", {}).get("Source", {}).get("rich_text", [])
            source_text = source[0].get("text", {}).get("content", "") if source else ""
            should_delete = source_filter.lower() in source_text.lower()

        elif mode == "3":
            status = page.get("properties", {}).get("Status", {}).get("select", {})
            status_text = status.get("name", "") if status else ""
            should_delete = status_text == status_filter

        if should_delete:
            httpx.patch(
                f"https://api.notion.com/v1/pages/{page['id']}",
                headers=headers,
                json={"archived": True},
                timeout=30.0
            )
            deleted += 1
        else:
            kept += 1

    has_more = data.get("has_more", False)
    cursor = data.get("next_cursor")

print(f"\n✅ Done! Deleted {deleted} entries, kept {kept} entries in {db_name}")
