import asyncio
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass

from database.database import db_manager
from database.models import Server, ServerAccount, Account
from services.xui_api import XUIManager, XUIApi
from config.settings import settings

logger = logging.getLogger(__name__)

@dataclass
class ServerStats:
    """Server statistics"""
    name: str
    is_healthy: bool
    last_check: datetime
    total_accounts: int
    active_accounts: int
    total_traffic: int
    response_time: float

class ServerManager:
    """Manager for X-UI servers with health monitoring"""
    
    def __init__(self):
        self.xui_manager = XUIManager(settings.servers)
        self.server_stats: Dict[str, ServerStats] = {}
        self.health_check_running = False
        
    async def initialize(self):
        """Initialize server manager"""
        await self.discover_servers()
        await self.start_health_monitoring()
        
    async def discover_servers(self) -> List[str]:
        """Discover and register active servers"""
        logger.info("Discovering servers...")
        
        active_servers = await self.xui_manager.get_active_servers()
        
        # Update database with server statuses
        db = db_manager.get_session()
        try:
            for server_config in settings.servers:
                db_server = db.query(Server).filter_by(
                    host=server_config.host,
                    port=server_config.port
                ).first()
                
                if not db_server:
                    # Create new server record
                    db_server = Server(
                        name=server_config.name,
                        host=server_config.host,
                        port=server_config.port,
                        web_base_path=server_config.web_base_path,
                        username=server_config.username,
                        password=server_config.password,
                        is_active=server_config.name in active_servers
                    )
                    db.add(db_server)
                else:
                    # Update existing server
                    db_server.is_active = server_config.name in active_servers
                    db_server.last_health_check = datetime.utcnow()
                
                logger.info(f"Server {server_config.name}: {'Active' if db_server.is_active else 'Inactive'}")
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating server statuses: {e}")
        finally:
            db.close()
        
        return active_servers
    
    async def get_active_servers(self) -> List[Server]:
        """Get all active servers from database"""
        db = db_manager.get_session()
        try:
            return db.query(Server).filter_by(is_active=True).all()
        finally:
            db.close()
    
    async def get_all_servers(self) -> List[Server]:
        """Get all servers from database (both active and inactive)"""
        db = db_manager.get_session()
        try:
            return db.query(Server).all()
        finally:
            db.close()
    
    async def get_server_by_name(self, name: str) -> Optional[Server]:
        """Get server by name"""
        db = db_manager.get_session()
        try:
            return db.query(Server).filter_by(name=name, is_active=True).first()
        finally:
            db.close()
    
    async def check_server_health(self, server: Server) -> bool:
        """Check health of a single server"""
        try:
            server_config = None
            for config in settings.servers:
                if config.name == server.name:
                    server_config = config
                    break
            
            if not server_config:
                return False
            
            start_time = datetime.utcnow()
            
            async with XUIApi(server_config) as api:
                is_healthy = await api.health_check()
                
            end_time = datetime.utcnow()
            response_time = (end_time - start_time).total_seconds()
            
            # Update server stats
            total_accounts = await self.get_server_account_count(server.id)
            active_accounts = await self.get_server_active_account_count(server.id)
            
            self.server_stats[server.name] = ServerStats(
                name=server.name,
                is_healthy=is_healthy,
                last_check=datetime.utcnow(),
                total_accounts=total_accounts,
                active_accounts=active_accounts,
                total_traffic=0,  # Will be updated by usage sync
                response_time=response_time
            )
            
            # Update database
            db = db_manager.get_session()
            try:
                db_server = db.query(Server).filter_by(id=server.id).first()
                if db_server:
                    db_server.is_active = is_healthy
                    db_server.last_health_check = datetime.utcnow()
                    db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"Error updating server health in database: {e}")
            finally:
                db.close()
            
            return is_healthy
            
        except Exception as e:
            logger.error(f"Health check failed for server {server.name}: {e}")
            return False
    
    async def get_server_account_count(self, server_id: int) -> int:
        """Get total account count for a server"""
        db = db_manager.get_session()
        try:
            return db.query(ServerAccount).filter_by(server_id=server_id).count()
        finally:
            db.close()
    
    async def get_server_active_account_count(self, server_id: int) -> int:
        """Get active account count for a server"""
        db = db_manager.get_session()
        try:
            # Join with accounts to check if they're active
            return db.query(ServerAccount).join(Account).filter(
                ServerAccount.server_id == server_id,
                Account.expire_time > datetime.utcnow()
            ).count()
        finally:
            db.close()
    
    async def start_health_monitoring(self):
        """Start background health monitoring"""
        if self.health_check_running:
            return
        
        self.health_check_running = True
        asyncio.create_task(self._health_check_loop())
        logger.info("Health monitoring started")
    
    async def _health_check_loop(self):
        """Background health check loop"""
        while self.health_check_running:
            try:
                await self.perform_health_checks()
                await asyncio.sleep(settings.health_check_interval)
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def perform_health_checks(self):
        """Perform health checks on all servers"""
        active_servers = await self.get_active_servers()
        
        tasks = []
        for server in active_servers:
            task = self.check_server_health(server)
            tasks.append(task)
        
        # Execute all health checks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        healthy_count = sum(1 for result in results if result is True)
        total_count = len(active_servers)
        
        logger.info(f"Health check completed: {healthy_count}/{total_count} servers healthy")
        
        # Send alerts if needed
        if healthy_count < total_count:
            await self.send_health_alerts()
    
    async def send_health_alerts(self):
        """Send alerts for unhealthy servers"""
        unhealthy_servers = []
        for name, stats in self.server_stats.items():
            if not stats.is_healthy:
                unhealthy_servers.append(name)
        
        if unhealthy_servers:
            logger.warning(f"Unhealthy servers detected: {', '.join(unhealthy_servers)}")
            # Here you can add notification logic (Telegram, email, etc.)
    
    async def get_best_servers(self, count: int = None) -> List[Server]:
        """Get best servers based on health and load"""
        active_servers = await self.get_active_servers()
        
        if not active_servers:
            logger.warning("No active servers found in database")
            return []
        
        # Filter healthy servers
        healthy_servers = []
        for server in active_servers:
            stats = self.server_stats.get(server.name)
            if stats and stats.is_healthy:
                healthy_servers.append(server)
        
        # If no healthy servers found in stats, use all active servers as fallback
        if not healthy_servers:
            logger.warning("No healthy servers found in stats, using all active servers as fallback")
            healthy_servers = active_servers
        
        # Sort by load (fewer accounts = better)
        healthy_servers.sort(key=lambda s: self.server_stats.get(s.name, type('obj', (object,), {'total_accounts': 0})).total_accounts)
        
        if count:
            return healthy_servers[:count]
        return healthy_servers
    
    async def get_server_stats(self, server_name: str) -> Optional[ServerStats]:
        """Get stats for a specific server"""
        return self.server_stats.get(server_name)
    
    async def get_all_server_stats(self) -> Dict[str, ServerStats]:
        """Get stats for all servers"""
        return self.server_stats.copy()
    
    async def stop_health_monitoring(self):
        """Stop health monitoring"""
        self.health_check_running = False
        logger.info("Health monitoring stopped")
    
    async def add_server(self, server_config) -> bool:
        """Add new server to the system"""
        try:
            # Test connectivity
            async with XUIApi(server_config) as api:
                is_healthy = await api.health_check()
            
            if not is_healthy:
                logger.error(f"Cannot add server {server_config.name}: health check failed")
                return False
            
            # Add to database
            db = db_manager.get_session()
            try:
                db_server = Server(
                    name=server_config.name,
                    host=server_config.host,
                    port=server_config.port,
                    web_base_path=server_config.web_base_path,
                    username=server_config.username,
                    password=server_config.password,
                    is_active=True
                )
                db.add(db_server)
                db.commit()
                
                # Add to XUI manager
                self.xui_manager.server_configs[server_config.name] = server_config
                
                logger.info(f"Server {server_config.name} added successfully")
                return True
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error adding server to database: {e}")
                return False
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error adding server {server_config.name}: {e}")
            return False
    
    async def remove_server(self, server_name: str) -> bool:
        """Remove server from the system"""
        try:
            db = db_manager.get_session()
            try:
                server = db.query(Server).filter_by(name=server_name).first()
                if server:
                    # Check if server has active accounts
                    account_count = db.query(ServerAccount).filter_by(server_id=server.id).count()
                    if account_count > 0:
                        logger.error(f"Cannot remove server {server_name}: has active accounts")
                        return False
                    
                    # Remove from database
                    db.delete(server)
                    db.commit()
                    
                    # Remove from XUI manager
                    if server_name in self.xui_manager.server_configs:
                        del self.xui_manager.server_configs[server_name]
                    
                    # Remove from stats
                    if server_name in self.server_stats:
                        del self.server_stats[server_name]
                    
                    logger.info(f"Server {server_name} removed successfully")
                    return True
                else:
                    logger.error(f"Server {server_name} not found")
                    return False
                    
            except Exception as e:
                db.rollback()
                logger.error(f"Error removing server from database: {e}")
                return False
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error removing server {server_name}: {e}")
            return False

# Global server manager instance
server_manager = ServerManager() 