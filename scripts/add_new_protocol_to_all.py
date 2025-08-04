#!/usr/bin/env python3
"""Add new protocol configuration to all existing accounts.

This script allows you to add a new protocol (like Reality) to all existing 
user accounts, so they get the new config in their subscription links.

HOW IT WORKS:
1. You define the new protocol template in PROTOCOL_TEMPLATES
2. This script creates new inbound clients for all existing accounts
3. All subscription links automatically include the new protocol

USAGE:
1. First add your new protocol to config/settings.py PROTOCOL_TEMPLATES
2. Make sure the target inbound exists on target servers in X-UI panel
3. Run: python scripts/add_new_protocol_to_all.py

Example for Reality protocol:
- Add Reality template to PROTOCOL_TEMPLATES in settings.py
- Create Reality inbound (e.g., ID 5) on all target servers
- Update NEW_PROTOCOL_NAME and INBOUND_ID below
- Run this script
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from typing import List, Dict, Any

# Add parent directory to Python path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import db_manager
from database.models import Account, Server, ServerAccount
from services.account_manager import AccountManager
from services.xui_api import create_client_config
from config.settings import settings, PROTOCOL_TEMPLATES

# Configure these for your new protocol
NEW_PROTOCOL_NAME = "vmess_ws_france"  # Must exist in PROTOCOL_TEMPLATES
TARGET_SERVERS = ["France Server"]  # Add to these servers (empty = all active)
INBOUND_ID = 18  # The inbound ID that has your new protocol config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ProtocolAdder:
    def __init__(self):
        self.account_manager = AccountManager()
        self.success_count = 0
        self.total_count = 0
        self.errors = []

    async def add_protocol_to_all_accounts(self):
        """Add new protocol to all existing accounts"""
        
        # Validate protocol exists
        if NEW_PROTOCOL_NAME not in PROTOCOL_TEMPLATES:
            logger.error(f"Protocol '{NEW_PROTOCOL_NAME}' not found in PROTOCOL_TEMPLATES")
            return False
            
        logger.info(f"🚀 Adding protocol '{NEW_PROTOCOL_NAME}' to all accounts...")
        logger.info(f"📋 Target servers: {TARGET_SERVERS or 'All active servers'}")
        logger.info(f"🔗 Target inbound ID: {INBOUND_ID}")
        
        # Get target servers
        target_server_configs = await self._get_target_servers()
        if not target_server_configs:
            logger.error("No target servers found!")
            return False
            
        logger.info(f"✅ Found {len(target_server_configs)} target servers")
        
        # Get all accounts
        accounts = await self._get_all_accounts()
        self.total_count = len(accounts)
        
        if not accounts:
            logger.warning("No accounts found!")
            return True
            
        logger.info(f"📊 Processing {self.total_count} accounts...")
        
        # Process each account
        for i, account in enumerate(accounts, 1):
            logger.info(f"[{i}/{self.total_count}] Processing account: {account.email}")
            
            try:
                success = await self._add_protocol_to_account(account, target_server_configs)
                if success:
                    self.success_count += 1
                    logger.info(f"✅ Account {account.email} updated successfully")
                else:
                    logger.error(f"❌ Failed to update account {account.email}")
                    
            except Exception as e:
                error_msg = f"Error processing account {account.email}: {e}"
                logger.error(error_msg)
                self.errors.append(error_msg)
                
        # Summary
        logger.info(f"""
🎉 Process completed!
📊 Summary:
   - Total accounts: {self.total_count}
   - Successfully updated: {self.success_count}
   - Failed: {self.total_count - self.success_count}
   - Errors: {len(self.errors)}
""")
        
        if self.errors:
            logger.info("❌ Errors encountered:")
            for error in self.errors[:10]:  # Show first 10 errors
                logger.info(f"   - {error}")
                
        return True

    async def _get_target_servers(self) -> List[Dict]:
        """Get list of target server configurations"""
        db = db_manager.get_session()
        try:
            # Get servers from database
            if TARGET_SERVERS:
                servers = db.query(Server).filter(
                    Server.name.in_(TARGET_SERVERS),
                    Server.is_active == True
                ).all()
            else:
                servers = db.query(Server).filter(Server.is_active == True).all()
                
            # Match with settings configurations
            server_configs = []
            for server in servers:
                for config in settings.servers:
                    if config.name == server.name and config.is_active:
                        server_configs.append({
                            'server_db': server,
                            'server_config': config
                        })
                        break
                        
            return server_configs
            
        finally:
            db.close()

    async def _get_all_accounts(self) -> List[Account]:
        """Get all active accounts from database"""
        db = db_manager.get_session()
        try:
            # Only get accounts that haven't expired
            accounts = db.query(Account).filter(
                Account.expire_time > datetime.utcnow()
            ).all()
            return accounts
        finally:
            db.close()

    async def _add_protocol_to_account(self, account: Account, target_server_configs: List[Dict]) -> bool:
        """Add new protocol to a specific account on target servers"""
        
        # Check if protocol is allowed for target servers
        protocol_template = PROTOCOL_TEMPLATES[NEW_PROTOCOL_NAME]
        allowed_servers = protocol_template.get("allowed_servers")
        
        success_count = 0
        
        for server_info in target_server_configs:
            server_db = server_info['server_db']
            server_config = server_info['server_config']
            
            # Skip if protocol not allowed for this server
            if allowed_servers and server_db.name not in allowed_servers:
                logger.info(f"   🚫 Protocol not allowed for server {server_db.name}")
                continue
                
            # Check if account already exists on this server with this inbound
            if await self._account_exists_on_server_inbound(account.id, server_db.id, INBOUND_ID):
                logger.info(f"   ⚠️  Account already exists on {server_db.name} inbound {INBOUND_ID}")
                continue
                
            # Create client config
            client_config = create_client_config(
                user_uuid=account.uuid,
                email=account.email,
                total_bytes=account.total_data_limit,
                expire_days=max(1, (account.expire_time - datetime.utcnow()).days)
            )
            
            # Create client on server
            try:
                result = await self.account_manager.server_manager.xui_manager.create_client_on_servers(
                    [server_db.name], client_config, inbound_id=INBOUND_ID
                )
                
                if result.get(server_db.name, False):
                    # Record in database
                    await self._record_server_account(account.id, server_db.id, INBOUND_ID)
                    success_count += 1
                    logger.info(f"   ✅ Added to {server_db.name}")
                else:
                    logger.error(f"   ❌ Failed to create on {server_db.name}")
                    
            except Exception as e:
                logger.error(f"   ❌ Error creating on {server_db.name}: {e}")
                
        return success_count > 0

    async def _account_exists_on_server_inbound(self, account_id: int, server_id: int, inbound_id: int) -> bool:
        """Check if account already exists on server with specific inbound"""
        db = db_manager.get_session()
        try:
            existing = db.query(ServerAccount).filter(
                ServerAccount.account_id == account_id,
                ServerAccount.server_id == server_id,
                ServerAccount.inbound_id == inbound_id
            ).first()
            return existing is not None
        finally:
            db.close()

    async def _record_server_account(self, account_id: int, server_id: int, inbound_id: int):
        """Record server account relationship in database"""
        db = db_manager.get_session()
        try:
            server_account = ServerAccount(
                account_id=account_id,
                server_id=server_id,
                inbound_id=inbound_id,
                data_used=0
            )
            db.add(server_account)
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

async def main():
    """Main execution function"""
    print("🔄 Adding new protocol to all existing accounts...")
    print("⚠️  Make sure you have:")
    print("   1. Added your protocol to PROTOCOL_TEMPLATES in settings.py")
    print("   2. Created the target inbound on all servers")
    print("   3. Updated the configuration variables in this script")
    print()
    
    confirm = input("Continue? [y/N]: ").lower().strip()
    if confirm != 'y':
        print("Operation cancelled.")
        return
        
    adder = ProtocolAdder()
    await adder.add_protocol_to_all_accounts()
    
    print()
    print("🎉 Done! All subscription links will now include the new protocol.")
    print("💡 Users can refresh their subscription links to get the new configs.")

if __name__ == "__main__":
    asyncio.run(main())