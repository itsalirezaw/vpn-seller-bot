import asyncio
import os
from datetime import datetime
import logging

import paramiko

from config.settings import settings, ServerConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("xui_db_sync")

BACKUP_ROOT = os.path.join(os.getcwd(), "x-ui_dbs")

async def fetch_db(server: ServerConfig) -> bool:
    """Fetch /etc/x-ui/x-ui.db from server via SFTP."""
    try:
        transport = paramiko.Transport((server.host, 22))
        transport.connect(username=server.ssh_username, password=server.ssh_password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            remote_path = "/etc/x-ui/x-ui.db"
            with sftp.open(remote_path, "rb") as remote_file:
                data = remote_file.read()
        finally:
            sftp.close()
            transport.close()

        # Prepare local path
        server_dir = os.path.join(BACKUP_ROOT, server.name.replace(" ", "_"))
        os.makedirs(server_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        local_path = os.path.join(server_dir, f"{timestamp}.db")
        with open(local_path, "wb") as f:
            f.write(data)
        logger.info("Saved DB from %s -> %s", server.name, local_path)
        return True
    except Exception as exc:
        logger.error("Failed to fetch DB from %s: %s", server.name, exc)
        return False

async def main():
    tasks = [fetch_db(s) for s in settings.servers if s.is_active]
    results = await asyncio.gather(*tasks)
    for srv, ok in zip([s for s in settings.servers if s.is_active], results):
        status = "✅" if ok else "❌"
        print(f"{status} {srv.name}")

if __name__ == "__main__":
    asyncio.run(main()) 