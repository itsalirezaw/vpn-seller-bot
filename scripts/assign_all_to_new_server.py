#!/usr/bin/env python3
"""Assign **all existing accounts** to a new X-UI server.

HOW IT WORKS
------------
1. Reads NEW_SERVER_NAME and INBOUND_ID constants below.
2. Looks the server up in the `servers` table (created via .env + sync_templates.py).
3. Iterates over every row in `accounts` and calls
   `AccountManager.assign_account_to_servers()` – this method:
   • Creates the client on the X-UI panel via API
   • Inserts a row in `server_accounts` so that usage-sync & traffic-reset work
     exactly like other servers.
4. Prints one line per account →  UUID  Success/Failed.

USAGE
-----
$ python scripts/assign_all_to_new_server.py

Make sure before running:
• The new server exists in .env (SERVER_N_*) and you ran `python sync_templates.py`.
• In X-UI the target inbound (e.g. id 4) already exists with the protocol that
  your PROTOCOL_TEMPLATES expect (vmess/vless …).
• BOT / subs-api do **not** need to be stopped – but after finishing, restart
  `subs-api` so that new configs appear in subscriptions:

  $ systemctl restart subs-api
"""

import sys
import os
# Add the parent directory to the Python path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from database.database import db_manager
from database.models import Server, Account
from services.account_manager import AccountManager
from datetime import datetime

NEW_SERVER_NAME = "France Server"   # ← change to exactly the `name` column value
INBOUND_ID = 4                    # ← inbound id that exists on the new server


aSYNC = AccountManager()

async def _process_account(acc, server_name):
    ok = await aSYNC.assign_account_to_servers(acc.uuid, [server_name])
    status = "✓" if ok else "✗"
    print(f"{datetime.now():%H:%M:%S}  {acc.uuid}  {status}")
    return ok

async def main():
    db = db_manager.get_session()
    try:
        srv = db.query(Server).filter_by(name=NEW_SERVER_NAME).first()
        if not srv:
            print(f"❌ Server '{NEW_SERVER_NAME}' not found in DB. Run sync_templates.py first.")
            return

        # Assign all accounts sequentially (can be changed to gather for concurrency)
        total = 0
        success = 0
        for acc in db.query(Account).all():
            total += 1
            if await _process_account(acc, NEW_SERVER_NAME):
                success += 1
        print(f"\nSummary: {success}/{total} accounts assigned to {NEW_SERVER_NAME}.")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
