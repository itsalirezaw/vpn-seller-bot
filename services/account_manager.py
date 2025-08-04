import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import uuid as uuid_lib
import json
import base64
from secrets import token_urlsafe
from urllib.parse import quote

from database.database import db_manager
from database.models import Account, ServerAccount, Server, User, ConfigTemplate
from services.server_manager import server_manager
from services.xui_api import create_client_config
from config.settings import settings, SERVICE_PLANS, PROTOCOL_TEMPLATES

logger = logging.getLogger(__name__)

def generate_config_from_template(template_name, user_uuid, server_host, server_name):
    template = PROTOCOL_TEMPLATES[template_name]
    config = template["config_template"].copy()
    for k, v in config.items():
        if isinstance(v, str):
            config[k] = v.replace("{user_uuid}", user_uuid).replace("{server_host}", server_host).replace("{server_name}", server_name)
    config_json = json.dumps(config, ensure_ascii=False)
    config_b64 = base64.b64encode(config_json.encode()).decode()
    return f"vmess://{config_b64}"

class AccountManager:
    """Manager for VPN accounts across multiple servers"""
    
    def __init__(self):
        self.server_manager = server_manager
        
    async def create_account(self, user_id: int, plan_id: str, servers: List[str] = None) -> Optional[Account]:
        """Create new VPN account across multiple servers"""
        try:
            # Check if any servers are configured
            if not settings.servers:
                logger.error("No servers configured in settings")
                return None
            
            # Get service plan
            if plan_id not in SERVICE_PLANS:
                logger.error(f"Invalid plan ID: {plan_id}")
                return None
            
            plan = SERVICE_PLANS[plan_id]
            
            # Create account in database
            db = db_manager.get_session()
            try:
                # ------------------------------------------------------------------
                # Create Account instance and customise email format
                # Email pattern: VPN + first 5 digits of user chat_id + first 5 chars of UUID
                # ------------------------------------------------------------------
                from database.models import User  # local import to avoid circular
                db_user = db.query(User).filter_by(id=user_id).first()
                chat_id_part = str(db_user.chat_id)[:5] if db_user and db_user.chat_id else "00000"

                account = Account(
                    user_id=user_id,
                    total_data_limit=plan['data_limit'],
                    expire_days=plan['expire_days']
                )
                # Override the default email generated inside Account.__init__
                uuid_part = account.uuid.replace("-", "")[:5]
                account.email = f"VPN{chat_id_part}{uuid_part}"

                db.add(account)
                db.commit()
                db.refresh(account)
                
                # Get target servers
                if not servers:
                    servers = await self.server_manager.get_best_servers(count=2)
                    server_names = [s.name for s in servers]
                    logger.info(f"Selected best servers for account creation: {server_names}")
                else:
                    server_names = servers
                    logger.info(f"Using provided servers for account creation: {server_names}")
                
                if not server_names:
                    logger.error("No servers available for account creation")
                    db.delete(account)
                    db.commit()
                    return None
                
                # Create client config
                client_config = create_client_config(
                    user_uuid=account.uuid,
                    email=account.email,
                    total_bytes=plan['data_limit'],  # data_limit is already in bytes
                    expire_days=plan['expire_days']
                )
                
                # Create account on servers
                success_servers = await self._create_account_on_servers(
                    account, server_names, client_config
                )
                
                if not success_servers:
                    # Failed to create on any server, but keep account for manual assignment
                    logger.warning(f"Failed to create account on any server for user {user_id}, but keeping account for manual assignment")
                    # Don't delete the account - allow manual server assignment later
                
                if success_servers:
                    logger.info(f"Account created successfully for user {user_id} on servers: {success_servers}")
                else:
                    logger.info(f"Account created in database for user {user_id}, but no servers assigned yet")
                    
                return account
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error creating account: {e}")
                return None
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error in create_account: {e}")
            return None
    
    async def assign_account_to_servers(self, account_uuid: str, server_names: List[str] = None) -> bool:
        """Manually assign existing account to servers"""
        try:
            account = await self.get_account_by_uuid(account_uuid)
            if not account:
                logger.error(f"Account with UUID {account_uuid} not found")
                return False
            
            # Check if account already has servers
            existing_servers = await self.get_account_servers(account.id)
            if existing_servers:
                logger.warning(f"Account {account_uuid} already has servers assigned")
                return False
            
            # Get target servers
            if not server_names:
                servers = await self.server_manager.get_best_servers(count=2)
                server_names = [s.name for s in servers]
            
            if not server_names:
                logger.error("No servers available for assignment")
                return False
            
            # Create client config (recalculate based on account data)
            from config.settings import SERVICE_PLANS
            
            # Find matching plan (approximate based on data limit)
            plan_id = "basic"  # Default fallback
            for pid, plan_data in SERVICE_PLANS.items():
                if plan_data.get('data_limit') == account.total_data_limit:
                    plan_id = pid
                    break
            
            plan = SERVICE_PLANS[plan_id]
            client_config = create_client_config(
                user_uuid=account.uuid,
                email=account.email,
                total_bytes=account.total_data_limit,  # total_data_limit is already in bytes
                expire_days=(account.expire_time - datetime.utcnow()).days
            )
            
            # Create account on servers
            success_servers = await self._create_account_on_servers(
                account, server_names, client_config
            )
            
            if success_servers:
                logger.info(f"Account {account_uuid} successfully assigned to servers: {success_servers}")
                return True
            else:
                logger.error(f"Failed to assign account {account_uuid} to any server")
                return False
            
        except Exception as e:
            logger.error(f"Error assigning account to servers: {e}")
            return False
    
    async def _create_account_on_servers(self, account: Account, server_names: List[str], client_config: Dict) -> List[str]:
        """Create account on specified servers (only on allowed servers for each template)"""
        success_servers = []
        logger.info(f"Attempting to create account on servers: {server_names}")
        
        # Get active servers
        active_servers = await self.server_manager.get_active_servers()
        logger.info(f"Active servers from database: {[s.name for s in active_servers]}")
        server_dict = {s.name: s for s in active_servers}
        
        # --- NEW: Load all active templates from DB ---
        db = db_manager.get_session()
        try:
            templates = db.query(ConfigTemplate).filter_by(is_active=True).all()
        finally:
            db.close()
        # ---------------------------------------------

        for server_name in server_names:
            if server_name not in server_dict:
                logger.warning(f"Server {server_name} not found or inactive")
                continue
            server = server_dict[server_name]
            logger.info(f"Processing server: {server_name} (ID: {server.id})")

            # --- NEW: Check if at least one template allows this server ---
            allowed = False
            for template in templates:
                allowed_servers = template.template_data.get("allowed_servers")
                if not allowed_servers or server_name in allowed_servers:
                    allowed = True
                    break
            if not allowed:
                logger.info(f"No template allows creation on server {server_name}, skipping.")
                continue
            # -------------------------------------------------------------
            
            try:
                # Create client on server using XUI API
                server_config = None
                for config in settings.servers:
                    if config.name == server_name:
                        server_config = config
                        break
                if not server_config:
                    logger.error(f"No configuration found for server {server_name}")
                    logger.error(f"Available server configs: {[c.name for c in settings.servers]}")
                    continue
                logger.info(f"Found server config for {server_name}: {server_config.host}:{server_config.port}")
                logger.info(f"Creating client on {server_name} with config: {client_config}")
                results = await self.server_manager.xui_manager.create_client_on_servers(
                    [server_name], client_config, inbound_id=4
                )
                logger.info(f"XUI manager results for {server_name}: {results}")
                if results.get(server_name, False):
                    db = db_manager.get_session()
                    try:
                        server_account = ServerAccount(
                            account_id=account.id,
                            server_id=server.id,
                            inbound_id=4,
                            data_used=0
                        )
                        db.add(server_account)
                        db.commit()
                        success_servers.append(server_name)
                        logger.info(f"Account created on server {server_name}")
                    except Exception as e:
                        db.rollback()
                        logger.error(f"Error creating server account record: {e}")
                    finally:
                        db.close()
                else:
                    logger.error(f"Failed to create account on server {server_name}")
            except Exception as e:
                logger.error(f"Error creating account on server {server_name}: {e}")
        return success_servers
    
    async def get_account_by_uuid(self, account_uuid: str) -> Optional[Account]:
        """Get account by UUID"""
        from sqlalchemy.orm import joinedload
        db = db_manager.get_session()
        try:
            return (
                db.query(Account)
                .options(joinedload(Account.server_accounts))
                .filter_by(uuid=account_uuid)
                .first()
            )
        finally:
            db.close()
    
    async def get_user_accounts(self, user_id: int) -> List[Account]:
        """Get all accounts for a user"""
        from sqlalchemy.orm import joinedload
        db = db_manager.get_session()
        try:
            # Eager-load server_accounts so that is_active/total_used_data can be
            # evaluated safely after the session is closed (avoids lazy-load error)
            return (
                db.query(Account)
                .options(joinedload(Account.server_accounts))
                .filter_by(user_id=user_id)
                .all()
            )
        finally:
            db.close()
    
    async def get_account_servers(self, account_id: int) -> List[Tuple[Server, ServerAccount]]:
        """Get all servers for an account"""
        db = db_manager.get_session()
        try:
            return db.query(Server, ServerAccount).join(
                ServerAccount, Server.id == ServerAccount.server_id
            ).filter(ServerAccount.account_id == account_id).all()
        finally:
            db.close()
    
    async def sync_account_usage(self, account_uuid: str) -> Dict[str, int]:
        """Sync account usage from all servers"""
        try:
            account = await self.get_account_by_uuid(account_uuid)
            if not account:
                return {}
            
            # Get usage from all servers
            usage_data = await self.server_manager.xui_manager.get_client_traffic_from_all_servers(
                account_uuid
            )

            # Update database with usage data
            db = db_manager.get_session()
            try:
                total_usage = {}
                # Prepare cache of Server objects by name for quick lookup
                servers_in_db = {s.name: s for s in db.query(Server).all()}

                # Iterate over usage_data returned from X-UI per server
                for srv_name, srv_usage in usage_data.items():
                    # Normalise list/dict format
                    if isinstance(srv_usage, list):
                        srv_usage = srv_usage[0] if srv_usage else {}

                    down_val = srv_usage.get('down', 0)
                    up_val = srv_usage.get('up', 0)
                    bytes_used = down_val + up_val

                    # Ensure Server exists
                    db_server = servers_in_db.get(srv_name)
                    if not db_server:
                        logger.warning(f"Server {srv_name} not found in DB when syncing usage")
                        continue

                    # Fetch or create ServerAccount within *this* session
                    sa = db.query(ServerAccount).filter_by(
                        account_id=account.id,
                        server_id=db_server.id
                    ).first()

                    if not sa:
                        inbound_id = srv_usage.get('inboundId') or srv_usage.get('inbound_id') or 0
                        sa = ServerAccount(
                            account_id=account.id,
                            server_id=db_server.id,
                            inbound_id=inbound_id,
                            data_used=bytes_used,
                            last_sync=datetime.utcnow()
                        )
                        db.add(sa)
                    else:
                        sa.data_used = bytes_used
                        sa.last_sync = datetime.utcnow()

                    total_usage[srv_name] = bytes_used
                
                db.commit()
                logger.info(f"Usage synced for account {account_uuid}")
                return total_usage
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error updating usage data: {e}")
                return {}
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error syncing account usage: {e}")
            return {}
    
    async def get_account_total_usage(self, account_uuid: str) -> int:
        """Get total usage across all servers"""
        account = await self.get_account_by_uuid(account_uuid)
        if not account:
            return 0
        
        db = db_manager.get_session()
        try:
            server_accounts = db.query(ServerAccount).filter_by(account_id=account.id).all()
            return sum(sa.data_used for sa in server_accounts)
        finally:
            db.close()
    
    async def check_account_limits(self, account_uuid: str) -> Dict[str, bool]:
        """Check if account has exceeded limits"""
        account = await self.get_account_by_uuid(account_uuid)
        if not account:
            return {'exists': False}
        
        total_usage = await self.get_account_total_usage(account_uuid)
        
        return {
            'exists': True,
            'expired': account.is_expired,
            'data_limit_exceeded': account.total_data_limit > 0 and total_usage >= account.total_data_limit,
            'is_active': account.is_active,
            'total_usage': total_usage,
            'remaining_data': account.remaining_data,
            'expire_time': account.expire_time
        }
    
    async def renew_account(self, account_uuid: str, additional_data: int, 
                          additional_days: int) -> bool:
        """Renew account with additional data and time"""
        try:
            db = db_manager.get_session()
            try:
                # Get account within the same session to avoid detached instance issues
                account = db.query(Account).filter_by(uuid=account_uuid).first()
                if not account:
                    return False
                # Update account limits
                # Update volume – if سرویس کاربر قبلاً نامحدود بوده، نامحدود باقی بماند
                old_data_limit = account.total_data_limit
                if additional_data > 0:
                    if account.total_data_limit == 0:
                        # Already unlimited – حجم اضافه نمی‌شود چون بی‌نهایت است
                        logger.info(f"Account {account_uuid} has unlimited data - not adding {additional_data} bytes")
                    else:
                        account.total_data_limit += additional_data
                        logger.info(f"Added {additional_data} bytes to account {account_uuid}: {old_data_limit} -> {account.total_data_limit}")
                else:
                    logger.info(f"No additional data to add for account {account_uuid} (additional_data: {additional_data})")
                
                old_expire_time = account.expire_time
                if additional_days > 0:
                    if account.is_expired:
                        account.expire_time = datetime.utcnow() + timedelta(days=additional_days)
                        logger.info(f"Account {account_uuid} was expired - set new expire time: {account.expire_time}")
                    else:
                        account.expire_time += timedelta(days=additional_days)
                        logger.info(f"Extended account {account_uuid} expiry: {old_expire_time} -> {account.expire_time} (+{additional_days} days)")
                else:
                    logger.info(f"No additional days to add for account {account_uuid} (additional_days: {additional_days})")
                
                # Update client config on all servers
                server_accounts = db.query(ServerAccount).filter_by(account_id=account.id).all()
                server_names = []
                for sa in server_accounts:
                    server = db.query(Server).filter_by(id=sa.server_id).first()
                    if server:
                        server_names.append(server.name)
                
                logger.info(f"Renewing account {account_uuid} on servers: {server_names}")
                if not server_names:
                    logger.warning(f"No servers found for account {account_uuid} during renewal")
                
                # Create updated client config
                expire_days = (account.expire_time - datetime.utcnow()).days
                logger.info(f"Creating client config for {account_uuid}:")
                logger.info(f"  total_bytes: {account.total_data_limit}")
                logger.info(f"  expire_days: {max(0, expire_days)}")
                logger.info(f"  email: {account.email}")
                
                client_config = create_client_config(
                    user_uuid=account.uuid,
                    email=account.email,
                    total_bytes=account.total_data_limit,  # total_data_limit is already in bytes
                    expire_days=max(0, expire_days)
                )
                # Ensure account is re-enabled after renewal
                client_config["enable"] = True
                logger.info(f"Generated client config: {client_config}")
                
                # Commit database changes first
                db.commit()
                logger.info(f"Database updated successfully for account {account_uuid}")
                
                # Then update on servers (if any servers found)
                if server_names:
                    await self.server_manager.xui_manager.update_client_on_servers(
                        server_names, 4, account.uuid, client_config
                    )
                    logger.info(f"Updated client config on servers {server_names} for account {account_uuid}")
                else:
                    logger.warning(f"Skipped server update for account {account_uuid} - no servers assigned")
                
                logger.info(f"Account {account_uuid} renewed successfully")
                return True
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error renewing account: {e}")
                return False
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error in renew_account: {e}")
            return False
    
    async def delete_account(self, account_uuid: str) -> bool:
        """Delete account from all servers"""
        try:
            account = await self.get_account_by_uuid(account_uuid)
            if not account:
                return False
            
            db = db_manager.get_session()
            try:
                # Get server accounts
                server_accounts = db.query(ServerAccount).filter_by(account_id=account.id).all()
                server_names = []
                
                for sa in server_accounts:
                    server = db.query(Server).filter_by(id=sa.server_id).first()
                    if server:
                        server_names.append(server.name)
                
                # Delete from servers
                await self.server_manager.xui_manager.delete_client_from_servers(
                    server_names, account.uuid, inbound_id=4
                )
                
                # Delete from database
                for sa in server_accounts:
                    db.delete(sa)
                
                db.delete(account)
                db.commit()
                
                logger.info(f"Account {account_uuid} deleted successfully")
                return True
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error deleting account: {e}")
                return False
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error in delete_account: {e}")
            return False
    
    async def generate_config_urls(self, account_uuid: str) -> Dict[str, Dict[str, str]]:
        """Generate configuration URLs for all servers using settings.py templates"""
        try:
            account = await self.get_account_by_uuid(account_uuid)
            if not account:
                return {}
            server_accounts = await self.get_account_servers(account.id)
            configs = {}
            for server, server_account in server_accounts:
                server_configs = {}
                for template_name, template in PROTOCOL_TEMPLATES.items():
                    allowed_servers = template.get("allowed_servers")
                    if allowed_servers and server.name not in allowed_servers:
                        continue
                    config_url = generate_config_from_template(
                        template_name,
                        user_uuid=account.uuid,
                        server_host=server.host,
                        server_name=server.name
                    )
                    if config_url:
                        server_configs[template_name] = config_url
                configs[server.name] = server_configs
            return configs
        except Exception as e:
            logger.error(f"Error generating config URLs: {e}")
            return {}
    
    async def generate_test_config_urls(self, account_uuid: str) -> Dict[str, Dict[str, str]]:
        """Generate configuration URLs for test accounts using specific template"""
        try:
            from config.settings import generate_config_from_template
            
            account = await self.get_account_by_uuid(account_uuid)
            if not account:
                return {}
            
            server_accounts = await self.get_account_servers(account.id)
            configs = {}
            
            for server, server_account in server_accounts:
                # Generate config using the specific template
                config_url = generate_config_from_template(
                    template_name="vmess_tcp",
                    user_uuid=account.uuid,
                    server_host=server.host,
                    server_name=server.name
                )
                
                if config_url:
                    configs[server.name] = {
                        "vmess_tcp": config_url
                    }
            
            return configs
            
        except Exception as e:
            logger.error(f"Error generating test config URLs: {e}")
            return {}
    
    async def _generate_config_url(self, server: Server, account: Account, 
                                 template: ConfigTemplate) -> Optional[str]:
        """Generate configuration URL for specific server and protocol"""
        try:
            template_data = template.template_data
            
            if template.protocol == "vmess":
                # Generate VMess URL
                config = {
                    "v": "2",
                    "ps": f"{server.name} - {template.name}",
                    "add": server.host,
                    "port": str(server.port),
                    "id": account.uuid,
                    "aid": "0",
                    "net": template_data.get("streamSettings", {}).get("network", "tcp"),
                    "type": "none",
                    "host": "",
                    "path": template_data.get("streamSettings", {}).get("wsSettings", {}).get("path", "/"),
                    "tls": "none"
                }
                
                # Encode to base64
                config_json = json.dumps(config)
                config_b64 = base64.b64encode(config_json.encode()).decode()
                return f"vmess://{config_b64}"
                
            elif template.protocol == "vless":
                # Generate VLESS URL
                query_params = []
                stream_settings = template_data.get("streamSettings", {})
                
                if stream_settings.get("network") == "ws":
                    query_params.append(f"type=ws")
                    ws_path = stream_settings.get("wsSettings", {}).get("path", "/")
                    query_params.append(f"path={quote(ws_path)}")
                
                query_string = "&".join(query_params)
                server_name = quote(f"{server.name} - {template.name}")
                
                return f"vless://{account.uuid}@{server.host}:{server.port}?{query_string}#{server_name}"
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating config URL: {e}")
            return None
    
    async def generate_subscription_link(self, account_uuid: str) -> Optional[str]:
        """Generate (or return existing) subscription URL for an account.

        • می‌سازد یک توکن یکتا
        • محتوا (لیست URLها) را Base64 می‌کند
        • در جدول Subscription ذخیره می‌کند
        • لینک کامل https://subs.prvprt.com/sub/{token} را برمی‌گرداند
        """
        try:
            from database.models import Subscription  # local import to avoid circular
            from database.database import db_manager

            # 1) ساخت توکن بر اساس الگوی جدید (همان نام اکانت/ایمیل)
            db = db_manager.get_session()
            from database.models import Account
            account = db.query(Account).filter_by(uuid=account_uuid).first()
            if not account:
                db.close()
                logger.error("Account not found when generating subscription link")
                return None

            token = account.email  # همان ساختار VPNxxxxx

            # 2) اگر قبلاً وجود دارد، از همان استفاده کن
            from sqlalchemy.exc import IntegrityError
            from database.models import Subscription
            existing = db.query(Subscription).filter_by(token=token).first()
            if not existing:
                try:
                    sub = Subscription(
                        token=token,
                        account_id=account.id,
                        content=""  # محتوا در لحظه تولید می‌شود؛ خالی ولی NOT NULL
                    )
                    db.add(sub)
                    db.commit()
                except IntegrityError:
                    db.rollback()
                    # احتمالاً در رقابت ایجاد شده – مشکلی نیست
                except Exception as e:
                    db.rollback()
                    logger.error(f"Error saving subscription: {e}")
                    db.close()
                    return None
            # اگر وجود داشت یا ساخته شد موفقیت‌آمیز، ادامه بده
            db.close()

            # 3) برگرداندن لینک کامل (دامنه را می‌توان از env خواند)
            import os
            base_url = os.getenv("SUBS_BASE_URL", "https://subs.prvprt.com")
            return f"{base_url}/sub/{token}"
        except Exception as e:
            logger.error(f"Error generating subscription link: {e}")
            return None
    
    async def create_test_account(self, user_id: int) -> Optional[Account]:
        """Create test account with limited resources"""
        try:
            # Check if user already used test account
            db = db_manager.get_session()
            try:
                user = db.query(User).filter_by(id=user_id).first()
                if not user or user.test_used:
                    return None
                
                # Create test account
                account = Account(
                    user_id=user_id,
                    total_data_limit=settings.test_account_data_limit,
                    expire_days=1  # 1 day for test account
                )
                
                db.add(account)
                
                # Mark user as having used test account
                user.test_used = True
                
                db.commit()
                db.refresh(account)
                
                # Create on the first configured server only (regardless of current load)
                # This addresses the requirement that test accounts must always be provisioned
                # on the very first server defined in settings.servers.
                first_server_name = settings.servers[0].name if settings.servers else None
                server_names = [first_server_name] if first_server_name else []
                if server_names:
                    
                    client_config = create_client_config(
                        user_uuid=account.uuid,
                        email=account.email,
                        total_bytes=settings.test_account_data_limit,  # Use bytes from settings
                        expire_days=1  # 1 day
                    )
                    
                    success_servers = await self._create_account_on_servers(
                        account, server_names, client_config
                    )
                    
                    if success_servers:
                        logger.info(f"Test account created for user {user_id}")
                        return account
                    else:
                        # Rollback if failed to create on servers
                        db.delete(account)
                        user.test_used = False
                        db.commit()
                        return None
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error creating test account: {e}")
                return None
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error in create_test_account: {e}")
            return None

    async def get_account_by_id(self, account_id: int) -> Optional[Account]:
        """Get account by integer ID with server_accounts eager loaded"""
        from sqlalchemy.orm import joinedload
        db = db_manager.get_session()
        try:
            return (
                db.query(Account)
                .options(joinedload(Account.server_accounts))
                .filter_by(id=account_id)
                .first()
            )
        finally:
            db.close()

    async def disable_account(self, account_uuid: str) -> bool:
        """Disable an account (set enable=False) on all servers when quota exceeded or expired"""
        try:
            account = await self.get_account_by_uuid(account_uuid)
            if not account:
                return False
            db = db_manager.get_session()
            try:
                # Get associated servers
                server_accounts = db.query(ServerAccount).filter_by(account_id=account.id).all()
                server_names = []
                for sa in server_accounts:
                    server = db.query(Server).filter_by(id=sa.server_id).first()
                    if server:
                        server_names.append(server.name)

                if not server_names:
                    logger.warning(f"No servers found for account {account_uuid} when disabling")
                    return False

                # Build updated client config with enable=False
                expire_days = max(0, (account.expire_time - datetime.utcnow()).days)
                client_config = create_client_config(
                    user_uuid=account.uuid,
                    email=account.email,
                    total_bytes=account.total_data_limit,
                    expire_days=expire_days
                )
                client_config["enable"] = False

                # Push update to all servers
                await self.server_manager.xui_manager.update_client_on_servers(
                    server_names, 4, account.uuid, client_config
                )

                db.commit()
                logger.info(f"Account {account_uuid} disabled on servers: {server_names}")
                return True
            except Exception as e:
                db.rollback()
                logger.error(f"Error disabling account {account_uuid}: {e}")
                return False
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error in disable_account: {e}")
            return False

# Global account manager instance
account_manager = AccountManager() 