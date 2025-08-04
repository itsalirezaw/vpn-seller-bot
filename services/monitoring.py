import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import os

from database.database import async_session
from database.models import Server, Account, ServerAccount, User, Order
from services.server_manager import ServerManager
from services.xui_api import XUIApi
from config.settings import settings, ADMIN_IDS
from sqlalchemy import select, func, and_

logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class ServerMetrics:
    """Server performance metrics"""
    server_id: int
    server_name: str
    is_online: bool
    response_time: float
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    disk_usage: Optional[float] = None
    active_clients: int = 0
    total_traffic: int = 0
    last_check: datetime = None
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.last_check is None:
            self.last_check = datetime.now()

@dataclass
class Alert:
    """Monitoring alert"""
    level: AlertLevel
    title: str
    message: str
    server_id: Optional[int] = None
    server_name: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class MonitoringService:
    """Server monitoring and alerting service"""
    
    def __init__(self):
        self.server_manager = ServerManager()
        self.monitoring_interval = 60  # Check every minute
        self.alert_cooldown = 300  # 5 minutes cooldown between same alerts
        self.last_alerts: Dict[str, datetime] = {}
        self.server_metrics: Dict[int, ServerMetrics] = {}
        self.is_running = False
        self.monitoring_task = None
        # Track last time usage sync ran
        self._last_usage_sync: datetime = datetime.utcnow()
        # Persisted reminder flags across restarts
        self._flags_file = os.path.join(os.getcwd(), "reminder_flags.json")
        self._reminder_flags = self._load_flags()

    def _load_flags(self):
        try:
            import json, os
            if os.path.exists(self._flags_file):
                with open(self._flags_file, "r", encoding="utf-8") as fp:
                    return json.load(fp)
        except Exception:
            pass
        return {}

    def _save_flags(self):
        try:
            import json
            with open(self._flags_file, "w", encoding="utf-8") as fp:
                json.dump(self._reminder_flags, fp)
        except Exception:
            pass
        
    async def start_monitoring(self):
        """Start the monitoring service"""
        if self.is_running:
            logger.warning("Monitoring service is already running")
            return
        
        self.is_running = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Monitoring service started")
        
    async def stop_monitoring(self):
        """Stop the monitoring service"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Monitoring service stopped")
        
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        # Track last cleanup timestamp
        if not hasattr(self, "_last_expired_cleanup"):
            self._last_expired_cleanup = datetime.utcnow()
        # Track reminder flags per account UUID
        if not hasattr(self, "_reminder_flags"):
            self._reminder_flags = {}

        while self.is_running:
            try:
                await self._check_all_servers()
                await self._check_system_health()

                # Periodic usage sync (quota enforcement) - configurable via settings
                if datetime.utcnow() - self._last_usage_sync > timedelta(seconds=settings.usage_sync_interval):
                    await self._sync_account_usages()
                    self._last_usage_sync = datetime.utcnow()
                await self._cleanup_old_metrics()

                # Periodic expired account cleanup (every 24h)
                if datetime.utcnow() - self._last_expired_cleanup > timedelta(hours=24):
                    await self._cleanup_expired_accounts()
                    self._last_expired_cleanup = datetime.utcnow()

                # Send test account reminders (time + usage)
                await self._handle_test_account_reminders()

                # Send paid account reminders (time + usage)
                await self._handle_paid_account_reminders()
                await asyncio.sleep(self.monitoring_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(30)  # Wait before retrying
    
    async def _check_all_servers(self):
        """Check health of all servers"""
        servers = await self.server_manager.get_all_servers()
        
        for server in servers:
            if not server.is_active:
                continue
                
            try:
                metrics = await self._check_server_health(server)
                self.server_metrics[server.id] = metrics
                
                # Check for alerts
                await self._check_server_alerts(server, metrics)
                
            except Exception as e:
                logger.error(f"Error checking server {server.name}: {e}")
                
                # Create error metrics
                error_metrics = ServerMetrics(
                    server_id=server.id,
                    server_name=server.name,
                    is_online=False,
                    response_time=0,
                    errors=[str(e)]
                )
                self.server_metrics[server.id] = error_metrics
                
                # Send critical alert
                await self._send_alert(Alert(
                    level=AlertLevel.CRITICAL,
                    title=f"Server {server.name} Check Failed",
                    message=f"Failed to check server {server.name}: {e}",
                    server_id=server.id,
                    server_name=server.name
                ))
    
    async def _check_server_health(self, server: Server) -> ServerMetrics:
        """Check individual server health"""
        start_time = datetime.now()
        
        try:
            # Create server config from database data
            # Fetch the original config (to get the correct scheme) from loaded settings
            from config.settings import ServerConfig, settings
            _scheme = 'http'
            for _cfg in settings.servers:
                if _cfg.name == server.name:
                    _scheme = _cfg.scheme
                    break

            server_config = ServerConfig(
                name=server.name,
                host=server.host,
                port=server.port,
                web_base_path=server.web_base_path,
                username=server.username,
                password=server.password,
                is_active=server.is_active,
                scheme=_scheme
            )
            
            # Use XUI API with context manager
            async with XUIApi(server_config) as xui_api:
                # Test login
                login_success = await xui_api.login()
                if not login_success:
                    return ServerMetrics(
                        server_id=server.id,
                        server_name=server.name,
                        is_online=False,
                        response_time=0,
                        errors=["Login failed"]
                    )
                
                # Get server stats
                stats = await xui_api.get_server_stats()
                
                # Get client count
                clients = await xui_api.get_clients()
                active_clients = len([c for c in clients if c.get('enable', True)])
                
                # Calculate response time
                response_time = (datetime.now() - start_time).total_seconds()
                
                # Calculate total traffic
                total_traffic = 0
                for client in clients:
                    total_traffic += client.get('up', 0) + client.get('down', 0)
                
                # Update database
                async with async_session() as session:
                    server.last_health_check = datetime.now()
                    await session.commit()
                
                metrics = ServerMetrics(
                    server_id=server.id,
                    server_name=server.name,
                    is_online=True,
                    response_time=response_time,
                    cpu_usage=stats.get('cpu_usage'),
                    memory_usage=stats.get('memory_usage'),
                    disk_usage=stats.get('disk_usage'),
                    active_clients=active_clients,
                    total_traffic=total_traffic
                )
                
                return metrics
            
        except Exception as e:
            logger.error(f"Health check failed for {server.name}: {e}")
            return ServerMetrics(
                server_id=server.id,
                server_name=server.name,
                is_online=False,
                response_time=0,
                errors=[str(e)]
            )
    
    async def _check_server_alerts(self, server: Server, metrics: ServerMetrics):
        """Check for server alerts based on metrics"""
        alerts = []
        
        # Check if server is offline
        if not metrics.is_online:
            alerts.append(Alert(
                level=AlertLevel.CRITICAL,
                title=f"Server {server.name} is Offline",
                message=f"Server {server.name} is not responding. Errors: {', '.join(metrics.errors)}",
                server_id=server.id,
                server_name=server.name
            ))
        
        # Check response time
        if metrics.response_time > 10:  # 10 seconds threshold
            alerts.append(Alert(
                level=AlertLevel.WARNING,
                title=f"High Response Time - {server.name}",
                message=f"Server {server.name} response time is {metrics.response_time:.2f}s",
                server_id=server.id,
                server_name=server.name
            ))
        
        # Check CPU usage
        if metrics.cpu_usage and metrics.cpu_usage > 90:
            alerts.append(Alert(
                level=AlertLevel.WARNING,
                title=f"High CPU Usage - {server.name}",
                message=f"Server {server.name} CPU usage is {metrics.cpu_usage:.1f}%",
                server_id=server.id,
                server_name=server.name
            ))
        
        # Check memory usage
        if metrics.memory_usage and metrics.memory_usage > 90:
            alerts.append(Alert(
                level=AlertLevel.WARNING,
                title=f"High Memory Usage - {server.name}",
                message=f"Server {server.name} memory usage is {metrics.memory_usage:.1f}%",
                server_id=server.id,
                server_name=server.name
            ))
        
        # Check disk usage
        if metrics.disk_usage and metrics.disk_usage > 85:
            alerts.append(Alert(
                level=AlertLevel.WARNING,
                title=f"High Disk Usage - {server.name}",
                message=f"Server {server.name} disk usage is {metrics.disk_usage:.1f}%",
                server_id=server.id,
                server_name=server.name
            ))
        
        # Check if server is overloaded (using a default limit of 2000 users)
        max_users = 2000  # Default limit, can be made configurable later
        if metrics.active_clients > max_users:
            alerts.append(Alert(
                level=AlertLevel.ERROR,
                title=f"Server Overloaded - {server.name}",
                message=f"Server {server.name} has {metrics.active_clients} clients but max is {max_users}",
                server_id=server.id,
                server_name=server.name
            ))
        
        # Send alerts
        for alert in alerts:
            await self._send_alert(alert)
    
    async def _check_system_health(self):
        """Check overall system health"""
        try:
            async with async_session() as session:
                # Check for stuck orders
                stuck_orders = await session.scalar(
                    select(func.count())
                    .select_from(
                        select(1)
                        .where(
                            and_(
                                Order.status == 'pending',
                                Order.created_at < datetime.now() - timedelta(hours=24)
                            )
                        )
                        .subquery()
                    )
                )
                
                if stuck_orders > 0:
                    await self._send_alert(Alert(
                        level=AlertLevel.WARNING,
                        title="Stuck Orders Detected",
                        message=f"Found {stuck_orders} orders pending for more than 24 hours"
                    ))
                
                # Check for inactive accounts that should be active
                inactive_accounts = await session.scalar(
                    select(func.count())
                    .select_from(
                        select(1)
                        .where(
                            and_(
                                Account.is_active == False,
                                Account.expire_time > datetime.now(),
                                Account.total_used_data < Account.total_data_limit
                            )
                        )
                        .subquery()
                    )
                )
                
                if inactive_accounts > 10:
                    await self._send_alert(Alert(
                        level=AlertLevel.INFO,
                        title="Inactive Accounts Alert",
                        message=f"Found {inactive_accounts} accounts that should be active"
                    ))
                
        except Exception as e:
            logger.error(f"System health check failed: {e}")
    
    async def _send_alert(self, alert: Alert):
        """Send alert to administrators"""
        # Check alert cooldown
        alert_key = f"{alert.server_id}_{alert.title}"
        if alert_key in self.last_alerts:
            if datetime.now() - self.last_alerts[alert_key] < timedelta(seconds=self.alert_cooldown):
                return
        
        self.last_alerts[alert_key] = datetime.now()
        
        # Format alert message
        level_emoji = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.ERROR: "❌",
            AlertLevel.CRITICAL: "🚨"
        }
        
        message = f"""
{level_emoji[alert.level]} **{alert.title}**

{alert.message}

🕐 زمان: {alert.timestamp.strftime('%Y/%m/%d %H:%M:%S')}
"""
        
        # Send to all admins
        from telegram import Bot
        bot = Bot(token=settings.bot.token)
        
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode='Markdown'
                )
                logger.info(f"Alert sent to admin {admin_id}: {alert.title}")
            except Exception as e:
                logger.error(f"Failed to send alert to admin {admin_id}: {e}")
    
    async def _cleanup_old_metrics(self):
        """Clean up old metrics to prevent memory leaks"""
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        for server_id, metrics in list(self.server_metrics.items()):
            if metrics.last_check < cutoff_time:
                del self.server_metrics[server_id]
    
    async def get_server_metrics(self, server_id: int) -> Optional[ServerMetrics]:
        """Get metrics for a specific server"""
        return self.server_metrics.get(server_id)
    
    async def get_all_metrics(self) -> Dict[int, ServerMetrics]:
        """Get all server metrics"""
        return self.server_metrics.copy()
    
    async def get_system_status(self) -> Dict[str, any]:
        """Get overall system status"""
        async with async_session() as session:
            # Get basic stats
            total_servers = await session.scalar(select(func.count(Server.id)))
            active_servers = await session.scalar(
                select(func.count(Server.id)).where(Server.is_active == True)
            )
            online_servers = len([m for m in self.server_metrics.values() if m.is_online])
            
            total_accounts = await session.scalar(select(func.count(Account.id)))
            active_accounts = await session.scalar(
                select(func.count(Account.id)).where(Account.is_active == True)
            )
            
            # Calculate total traffic
            total_traffic = sum(m.total_traffic for m in self.server_metrics.values())
            
            return {
                'servers': {
                    'total': total_servers,
                    'active': active_servers,
                    'online': online_servers,
                    'offline': active_servers - online_servers
                },
                'accounts': {
                    'total': total_accounts,
                    'active': active_accounts
                },
                'traffic': {
                    'total': total_traffic
                },
                'monitoring': {
                    'is_running': self.is_running,
                    'last_check': max([m.last_check for m in self.server_metrics.values()]) if self.server_metrics else None
                }
            }

    async def _sync_account_usages(self):
        """Synchronize traffic for all accounts and disable ones exceeding quota"""
        from services.account_manager import account_manager  # imported here to avoid circular deps
        async with async_session() as session:
            account_uuids = await session.scalars(select(Account.uuid))
            uuids_list = list(account_uuids)

        for acc_uuid in uuids_list:
            try:
                # Update usage from all servers
                await account_manager.sync_account_usage(acc_uuid)
                limits = await account_manager.check_account_limits(acc_uuid)

                # Disable account if quota exceeded or expired but still enabled on servers
                if not limits.get('expired', False) and limits.get('data_limit_exceeded', False):
                    await account_manager.disable_account(acc_uuid)
            except Exception as e:
                logger.error(f"Error syncing usage for account {acc_uuid}: {e}")

    async def _cleanup_expired_accounts(self):
        """Delete accounts that expired more than 60 days ago from both servers and DB"""
        from services.account_manager import account_manager  # late import to avoid circular
        cutoff = datetime.utcnow() - timedelta(days=60)
        logger.info("Running expired account cleanup. Cutoff date: %s", cutoff.strftime('%Y-%m-%d'))

        async with async_session() as session:
            # Accounts expired more than 60 days ago
            stmt_old = select(Account).where(Account.expire_time < cutoff)
            # Expired test accounts (expire_time passed AND data_limit == test_account_data_limit)
            stmt_test = select(Account).where(
                Account.expire_time < datetime.utcnow(),
                Account.total_data_limit == settings.test_account_data_limit
            )

            result_old = await session.execute(stmt_old)
            result_test = await session.execute(stmt_test)

            accounts_to_delete = list({*result_old.scalars().all(), *result_test.scalars().all()})

        for acc in accounts_to_delete:
            try:
                success = await account_manager.delete_account(acc.uuid)
                if success:
                    logger.info("Deleted old account %s (expired %s)", acc.uuid, acc.expire_time)
                else:
                    logger.warning("Failed to delete old account %s", acc.uuid)
            except Exception as e:
                logger.error("Error deleting old account %s: %s", acc.uuid, e)

    async def _handle_test_account_reminders(self):
        """Send friendly reminders to test account users based on time and usage thresholds"""
        from services.account_manager import account_manager  # late import
        from telegram import Bot

        bot = Bot(token=settings.bot.token)

        async with async_session() as session:
            from database.models import User
            stmt = (
                select(Account, User.chat_id)
                .join(User, Account.user_id == User.id)
                .where(
                    Account.total_data_limit == settings.test_account_data_limit,
                    Account.expire_time > datetime.utcnow()
                )
            )
            result = await session.execute(stmt)
            rows = result.all()

        for acc, chat_id in rows:
            uuid = acc.uuid
            now = datetime.utcnow()
            time_left = acc.expire_time - now

            # Ensure reminders dict exists
            flags = self._reminder_flags.setdefault(uuid, {
                "time_6h": False,
                "time_1h": False,
                "data_80": False,
                "data_100": False
            })

            # Time-based reminders
            if not flags["time_6h"] and time_left.total_seconds() <= 6 * 3600 and time_left.total_seconds() > 5.9 * 3600:
                await self._send_test_reminder(bot, chat_id, "6h", acc)
                flags["time_6h"] = True
            if not flags["time_1h"] and time_left.total_seconds() <= 1 * 3600 and time_left.total_seconds() > 0.9 * 3600:
                await self._send_test_reminder(bot, chat_id, "1h", acc)
                flags["time_1h"] = True

            # Data-based reminders
            usage_limits = await account_manager.check_account_limits(uuid)
            total_usage = usage_limits.get("total_usage", 0)
            if acc.total_data_limit > 0:
                usage_ratio = total_usage / acc.total_data_limit
                if not flags["data_80"] and usage_ratio >= 0.8 and usage_ratio < 0.85:
                    await self._send_test_reminder(bot, chat_id, "80p", acc)
                    flags["data_80"] = True
                if not flags["data_100"] and usage_ratio >= 1.0:
                    await self._send_test_reminder(bot, chat_id, "100p", acc)
                    flags["data_100"] = True

            # save flags after processing each account
            self._save_flags()

    async def _send_test_reminder(self, bot, chat_id: int, kind: str, account: Account):
        """Send the actual reminder message based on kind."""
        try:
            if kind == "6h":
                msg = (
                    "🌟 امیدواریم از تست اکانت راضی بوده باشی!\n"
                    "⏰ فقط ۶ ساعت تا تموم شدن زمان تستت باقی مونده. اگه دوست داشتی میتونی یه پلن کامل تهیه کنی 😊\n"
                    "🙏 ممنون که امتحان کردی!"
                )
            elif kind == "1h":
                msg = (
                    "🚀 فقط ۱ ساعت تا تموم شدن اکانت تستت باقی مونده!\n"
                    "اگه راضی بودی، همین الان یه پلن مناسب انتخاب کن تا قطع نشی 😉\n"
                    "✨ از اعتمادت ممنونیم!"
                )
            elif kind == "80p":
                msg = (
                    "📊 ۸۰٪ از حجم تستت تموم شده!\n"
                    "اگه کیفیت خوب بود، یه پلن کامل تهیه کن تا قطع نشی 🤗\n"
                    "🌟 ممنون که امتحان کردی!"
                )
            elif kind == "100p":
                msg = (
                    "✅ حجم اکانت تستت تموم شد!\n"
                    "امیدواریم تجربه خوبی داشته باشی. برای ادامه، یکی از پلن‌هامون رو تهیه کن 😊\n"
                    "💖 از همراهیت ممنونیم!"
                )
            else:
                return

            await bot.send_message(chat_id=chat_id, text=msg)
            logger.info("Sent %s reminder to user %s for account %s", kind, chat_id, account.uuid)
        except Exception as e:
            logger.error("Failed to send %s reminder to user %s: %s", kind, chat_id, e)

    async def _handle_paid_account_reminders(self):
        """Reminders for purchased (non-test) accounts"""
        from services.account_manager import account_manager
        from telegram import Bot

        bot = Bot(token=settings.bot.token)

        async with async_session() as session:
            from database.models import User
            stmt = (
                select(Account, User.chat_id)
                .join(User, Account.user_id == User.id)
                .where(
                    Account.total_data_limit != settings.test_account_data_limit,
                    Account.expire_time > datetime.utcnow()
                )
            )
            result = await session.execute(stmt)
            rows = result.all()

        for acc, chat_id in rows:
            uuid = acc.uuid
            now = datetime.utcnow()
            time_left = acc.expire_time - now

            # Ensure reminder flags exist for this account
            flags = self._reminder_flags.setdefault(uuid, {})
            for _k in ("time_3d", "time_1d", "data_80", "data_100"):
                flags.setdefault(_k, False)

            # Time-based (3 days, 1 day)
            if not flags["time_3d"] and 3*86400 >= time_left.total_seconds() > (3*86400 - 3600):
                await self._send_paid_reminder(bot, chat_id, "3d", acc)
                flags["time_3d"] = True

            if not flags["time_1d"] and 1*86400 >= time_left.total_seconds() > (1*86400 - 3600):
                await self._send_paid_reminder(bot, chat_id, "1d", acc)
                flags["time_1d"] = True

            # Data-based
            usage_limits = await account_manager.check_account_limits(uuid)
            total_usage = usage_limits.get("total_usage", 0)
            if acc.total_data_limit > 0:
                usage_ratio = total_usage / acc.total_data_limit
                if not flags["data_80"] and 0.8 <= usage_ratio < 0.85:
                    await self._send_paid_reminder(bot, chat_id, "80p", acc)
                    flags["data_80"] = True
                if not flags["data_100"] and usage_ratio >= 1.0:
                    await self._send_paid_reminder(bot, chat_id, "100p", acc)
                    flags["data_100"] = True

            self._save_flags()

    async def _send_paid_reminder(self, bot, chat_id: int, kind: str, account: Account):
        """Compose and send paid account reminders"""
        try:
            if kind == "3d":
                msg = (
                    "📅 ۳ روز تا تموم شدن سرویست باقی مونده!\n"
                    "برای اینکه قطع نشی، همین الان تمدیدش کن 😊\n"
                    "🙏 ممنون از اعتمادت!"
                )
            elif kind == "1d":
                msg = (
                    "⏰ فقط ۱ روز تا تموم شدن سرویست باقی مونده!\n"
                    "همین الان تمدیدش کن تا قطع نشی 🤗\n"
                    "💖 از همراهیت ممنونیم!"
                )
            elif kind == "80p":
                msg = (
                    "📊 ۸۰٪ از حجم سرویست تموم شده!\n"
                    "اگه نیاز به حجم بیشتر داری، یه پلن جدید بگیر یا همین رو تمدید کن 😉"
                )
            elif kind == "100p":
                msg = (
                    "✅ حجم سرویست تموم شد!\n"
                    "برای ادامه، تمدیدش کن یا یه پلن جدید بگیر 😊\n"
                    "🌟 از انتخابت ممنونیم!"
                )
            else:
                return

            await bot.send_message(chat_id=chat_id, text=msg)
            logger.info("Sent %s reminder to user %s for account %s", kind, chat_id, account.uuid)
        except Exception as e:
            logger.error("Failed to send %s reminder to user %s: %s", kind, chat_id, e)

# Global monitoring service instance
monitoring_service = MonitoringService() 