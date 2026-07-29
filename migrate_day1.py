import sqlite3
import httpx
import os
import sys
from dotenv import load_dotenv

def main():
    # Load variables from .env file
    load_dotenv()

    pancake_db_path = "services/pancake_dev.db"
    if not os.path.exists(pancake_db_path):
        print(f"Pancake DB not found at {pancake_db_path}")
        sys.exit(1)

    ar2_node_url = os.environ.get("AR2_NODE_URL", "http://localhost:8001")
    hub_jwt = os.environ.get("HUB_JWT")
    if not hub_jwt:
        print("ERROR: HUB_JWT environment variable is required to authenticate with AR2 /list-artifact.")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {hub_jwt}"}

    conn = sqlite3.connect(pancake_db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id, list_id FROM fieldlists")
        fieldlists = cursor.fetchall()
    except sqlite3.OperationalError:
        print("Could not query fieldlists table. Is this the right DB?")
        sys.exit(1)

    print(f"Found {len(fieldlists)} fieldlists. Backfilling to AR2...")

    success_count = 0
    
    for fl_id, list_id in fieldlists:
        cursor.execute("SELECT geoid FROM fieldlist_members WHERE fieldlist_id = ?", (fl_id,))
        members = [row[0] for row in cursor.fetchall()]
        
        if not members:
            continue
            
        print(f"Pushing ListID {list_id} with {len(members)} members...")
        
        try:
            resp = httpx.post(f"{ar2_node_url}/list-artifact", json={"members": members}, headers=headers, timeout=10)
            if resp.status_code in (200, 201):
                success_count += 1
            else:
                print(f"Failed to push {list_id}: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"Error connecting to AR2: {e}")
            sys.exit(1)

    print(f"Backfill complete. Successfully synced {success_count} field lists to AR2.")
    print("NOTE: script is idempotent. Re-running will cleanly skip existing ListIDs in AR2.")

if __name__ == "__main__":
    main()
