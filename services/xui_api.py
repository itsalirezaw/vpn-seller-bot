import aiohttp
import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import uuid

from config.settings import ServerConfig

logger = logging.getLogger(__name__)

@dataclass
class XUIClient:
    """X-UI Panel client data structure"""
    id: str
    alterId: int
    email: str
    limitIp: int
    totalGB: int
    expiryTime: int
    enable: bool
    tgId: str
    subId: str
    flow: str = ""

@dataclass
class XUIInbound:
    """X-UI Panel inbound data structure"""
    id: int
    up: int
    down: int
    total: int
    remark: str
    enable: bool
    expiryTime: int
    clientStats: List[Dict]
    listen: str
    port: int
    protocol: str
    settings: Dict
    streamSettings: Dict
    tag: str
    sniffing: Dict
    allocate: Dict = None  # New field for X-UI allocation settings

class XUIApi:
    """X-UI Panel API service"""
    
    def __init__(self, server_config: ServerConfig):
        self.server_config = server_config
        self.base_url = server_config.base_url
        # Some X-UI builds use a session cookie ("session=<uuid>") while
        # others return a JSON body with a JWT token to be sent in the
        # ``Authorization`` header. Support both.

        self.session_cookie: Optional[str] = None
        self.cookie_name: Optional[str] = None  # Track which cookie name to use
        self.auth_token: Optional[str] = None
        self.session = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(verify_ssl=False)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def login(self) -> bool:
        """Login to X-UI panel with up to 3 retries.

        اگر در اولین تلاش کوکی/توکن صادر نشود، دوباره تلاش می‌کنیم تا حداکثر 3 بار.
        فقط پس از شکست نهایی پیام ERROR ثبت می‌شود و مقدار False برمی‌گردد.
        """

        import asyncio

        login_data = {
            "username": self.server_config.username,
            "password": self.server_config.password,
        }

        cookie_names = ["session", "3x-ui", "xui-session", "auth"]

        for attempt in range(1, 4):
            try:
                async with self.session.post(
                    f"{self.base_url}/login",
                    data=login_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                ) as response:
                    if response.status != 200:
                        logger.warning(
                            f"Login attempt #{attempt} for {self.server_config.name}: HTTP {response.status}"
                        )
                        await asyncio.sleep(0.5)
                        continue

                    cookies = response.cookies
                    set_cookie = response.headers.get("Set-Cookie", "")

                    # 1) بررسی کوکی‌ها
                    for name in cookie_names:
                        if name in cookies:
                            self.session_cookie = cookies[name].value
                            self.cookie_name = name
                            logger.info(
                                f"Login {'retry ' if attempt>1 else ''}successful for {self.server_config.name} (cookie: {name})"
                            )
                            return True
                        if f"{name}=" in set_cookie:
                            self.session_cookie = set_cookie.split(f"{name}=")[1].split(";")[0]
                            self.cookie_name = name
                            logger.info(
                                f"Login {'retry ' if attempt>1 else ''}successful for {self.server_config.name} (cookie/header: {name})"
                            )
                            return True

                    # 2) بررسی JSON برای توکن
                    try:
                        body = await response.json(content_type=None)
                    except Exception:
                        body = None

                    if not isinstance(body, dict):
                        body = {}

                    token = body.get("token") or body.get("access_token") or body.get("data")
                    if token:
                        self.auth_token = token if isinstance(token, str) else str(token)
                        logger.info(
                            f"Login {'retry ' if attempt>1 else ''}successful for {self.server_config.name} (token)"
                        )
                        return True

                    logger.warning(
                        f"Login attempt #{attempt} for {self.server_config.name}: no cookie/token found"
                    )

            except Exception as exc:
                logger.warning(
                    f"Login attempt #{attempt} error for {self.server_config.name}: {exc}"
                )

            await asyncio.sleep(0.5)  # small delay before next retry

        # تمام تلاش‌ها شکست خورد
        logger.error(f"Login failed for {self.server_config.name} after 3 attempts")
        return False
    
    async def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Optional[Dict]:
        """Make authenticated request to X-UI API"""
        if not self.session_cookie and not self.auth_token:
            if not await self.login():
                return None
        
        # Build headers depending on which auth mechanism is available.
        headers = {
            'Content-Type': 'application/json'
        }

        if self.session_cookie:
            cookie_name = self.cookie_name or 'session'  # Default to 'session' if not set
            headers['Cookie'] = f'{cookie_name}={self.session_cookie}'
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with self.session.request(
                method,
                url,
                headers=headers,
                json=data if data else None
            ) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    # Session expired, try to re-login
                    logger.warning(f"Session expired for {self.server_config.name}, re-logging in...")
                    self.session_cookie = None
                    self.cookie_name = None  # Clear cookie name
                    self.auth_token = None # Clear token on session expiration
                    if await self.login():
                        return await self._make_request(method, endpoint, data)
                    return None
                else:
                    logger.error(f"Request failed: {response.status} - {await response.text()}")
                    return None
                    
        except Exception as e:
            logger.error(f"Request error for {self.server_config.name}: {e}")
            return None
    
    async def get_inbounds(self) -> List[XUIInbound]:
        """Get all inbounds from X-UI panel"""
        result = await self._make_request('GET', '/panel/api/inbounds/list')
        if result and result.get('success'):
            inbounds = []
            for inbound_data in result.get('obj', []):
                try:
                    # Filter out any extra fields that are not in XUIInbound
                    expected_fields = {
                        'id', 'up', 'down', 'total', 'remark', 'enable', 'expiryTime',
                        'clientStats', 'listen', 'port', 'protocol', 'settings',
                        'streamSettings', 'tag', 'sniffing', 'allocate'
                    }
                    
                    # Only include fields that are expected
                    filtered_data = {k: v for k, v in inbound_data.items() if k in expected_fields}
                    
                    # Set default values for missing fields
                    if 'allocate' not in filtered_data:
                        filtered_data['allocate'] = None
                    if 'clientStats' not in filtered_data:
                        filtered_data['clientStats'] = []
                    
                    inbound = XUIInbound(**filtered_data)
                    inbounds.append(inbound)
                except Exception as e:
                    logger.error(f"Error parsing inbound data: {e}")
                    logger.error(f"Inbound data: {inbound_data}")
                    continue
            return inbounds
        return []
    
    async def get_inbound(self, inbound_id: int) -> Optional[XUIInbound]:
        """Get specific inbound by ID"""
        result = await self._make_request('GET', f'/panel/api/inbounds/get/{inbound_id}')
        if result and result.get('success'):
            try:
                return XUIInbound(**result['obj'])
            except Exception as e:
                logger.error(f"Error parsing inbound data: {e}")
        return None
    
    async def add_client(self, inbound_id: int, client_data: Dict) -> bool:
        """Add client to inbound"""
        data = {
            'id': inbound_id,
            'settings': json.dumps({
                'clients': [client_data]
            })
        }
        
        result = await self._make_request('POST', '/panel/api/inbounds/addClient', data)
        return result and result.get('success', False)
    
    async def update_client(self, inbound_id: int, client_uuid: str, client_data: Dict) -> bool:
        """Update a specific client on an inbound"""
        logger.info(f"Updating client {client_uuid} on server {self.server_config.name}")
        logger.info(f"  Inbound ID: {inbound_id}")
        logger.info(f"  Client data: {client_data}")
        
        data = {
            'id': inbound_id,
            'settings': json.dumps({
                'clients': [client_data]
            })
        }
        
        result = await self._make_request('POST', f'/panel/api/inbounds/updateClient/{client_uuid}', data)
        success = result and result.get('success', False)
        
        if success:
            logger.info(f"Successfully updated client {client_uuid} on {self.server_config.name}")
        else:
            logger.error(f"Failed to update client {client_uuid} on {self.server_config.name}: {result}")
            
        return success
    
    async def delete_client(self, inbound_id: int, client_uuid: str) -> bool:
        """Delete client from inbound"""
        result = await self._make_request('POST', f'/panel/api/inbounds/{inbound_id}/delClient/{client_uuid}')
        return result and result.get('success', False)
    
    async def get_client_traffic(self, client_uuid: str) -> Optional[Dict]:
        """Get client traffic statistics"""
        result = await self._make_request('GET', f'/panel/api/inbounds/getClientTrafficsById/{client_uuid}')
        if result and result.get('success'):
            return result.get('obj')
        return None
    
    async def reset_client_traffic(self, inbound_id: int, email: str) -> bool:
        """Reset client traffic"""
        result = await self._make_request('POST', f'/panel/api/inbounds/{inbound_id}/resetClientTraffic/{email}')
        return result and result.get('success', False)
    
    async def update_inbound(self, inbound_id: int, inbound_data: Dict) -> bool:
        """Update inbound configuration"""
        result = await self._make_request('POST', f'/panel/api/inbounds/update/{inbound_id}', inbound_data)
        return result and result.get('success', False)
    
    async def get_server_stats(self) -> Dict:
        """Get server statistics"""
        try:
            # X-UI doesn't have a direct server stats endpoint
            # So we'll return basic info from system status
            result = await self._make_request('GET', '/panel/api/inbounds/list')
            if result and result.get('success'):
                return {
                    'cpu_usage': None,  # Not available in X-UI API
                    'memory_usage': None,  # Not available in X-UI API
                    'disk_usage': None,  # Not available in X-UI API
                    'status': 'online'
                }
            return {'status': 'offline'}
        except Exception as e:
            logger.error(f"Error getting server stats for {self.server_config.name}: {e}")
            return {'status': 'error'}
    
    async def get_clients(self) -> List[Dict]:
        """Get all clients from all inbounds"""
        try:
            inbounds = await self.get_inbounds()
            all_clients = []
            
            for inbound in inbounds:
                if hasattr(inbound, 'clientStats'):
                    all_clients.extend(inbound.clientStats)
            
            return all_clients
        except Exception as e:
            logger.error(f"Error getting clients for {self.server_config.name}: {e}")
            return []
    
    async def health_check(self) -> bool:
        """Check if server is healthy"""
        try:
            result = await self._make_request('GET', '/panel/api/inbounds/list')
            return result is not None and result.get('success', False)
        except Exception as e:
            logger.error(f"Health check failed for {self.server_config.name}: {e}")
            return False

class XUIManager:
    """Manager for multiple X-UI servers"""
    
    def __init__(self, server_configs: List[ServerConfig]):
        self.server_configs = {config.name: config for config in server_configs}
        self.active_servers = {}
        
    async def get_active_servers(self) -> List[str]:
        """Get list of active server names"""
        active = []
        for name, config in self.server_configs.items():
            if config.is_active:
                async with XUIApi(config) as api:
                    if await api.health_check():
                        active.append(name)
                        self.active_servers[name] = config
                    else:
                        logger.warning(f"Server {name} failed health check")
        return active
    
    async def create_client_on_servers(self, servers: List[str], client_data: Dict, 
                                     inbound_id: int = 4) -> Dict[str, bool]:
        """Create client on multiple servers"""
        results = {}
        
        tasks = []
        for server_name in servers:
            if server_name in self.server_configs:
                config = self.server_configs[server_name]
                task = self._create_client_on_server(config, client_data, inbound_id)
                tasks.append((server_name, task))
        
        # Execute all tasks concurrently
        for server_name, task in tasks:
            try:
                result = await task
                results[server_name] = result
                logger.info(f"Client creation on {server_name}: {'Success' if result else 'Failed'}")
            except Exception as e:
                logger.error(f"Error creating client on {server_name}: {e}")
                results[server_name] = False
        
        return results
    
    async def _create_client_on_server(self, config: ServerConfig, client_data: Dict, 
                                     inbound_id: int) -> bool:
        """Create client on a single server"""
        async with XUIApi(config) as api:
            return await api.add_client(inbound_id, client_data)
    
    async def get_client_traffic_from_all_servers(self, client_uuid: str) -> Dict[str, Dict]:
        """Get client traffic from all servers"""
        results = {}
        
        tasks = []
        for server_name, config in self.active_servers.items():
            task = self._get_client_traffic_from_server(config, client_uuid)
            tasks.append((server_name, task))
        
        # Execute all tasks concurrently
        for server_name, task in tasks:
            try:
                result = await task
                if result:
                    results[server_name] = result
            except Exception as e:
                logger.error(f"Error getting traffic from {server_name}: {e}")
        
        return results
    
    async def _get_client_traffic_from_server(self, config: ServerConfig, 
                                            client_uuid: str) -> Optional[Dict]:
        """Get client traffic from a single server"""
        async with XUIApi(config) as api:
            return await api.get_client_traffic(client_uuid)
    
    async def update_client_on_servers(self, servers: List[str], inbound_id: int, client_uuid: str,
                                     client_data: Dict) -> Dict[str, bool]:
        """Update client on multiple servers"""
        results = {}
        
        tasks = []
        for server_name in servers:
            if server_name in self.server_configs:
                config = self.server_configs[server_name]
                task = self._update_client_on_server(config, inbound_id, client_uuid, client_data)
                tasks.append((server_name, task))
        
        # Execute all tasks concurrently
        for server_name, task in tasks:
            try:
                result = await task
                results[server_name] = result
                logger.info(f"Client update on {server_name}: {'Success' if result else 'Failed'}")
            except Exception as e:
                logger.error(f"Error updating client on {server_name}: {e}")
                results[server_name] = False
        
        return results
    
    async def _update_client_on_server(self, config: ServerConfig, inbound_id: int, client_uuid: str,
                                     client_data: Dict) -> bool:
        """Update client on a single server"""
        async with XUIApi(config) as api:
            return await api.update_client(inbound_id, client_uuid, client_data)
    
    async def delete_client_from_servers(self, servers: List[str], client_uuid: str, 
                                       inbound_id: int = 4) -> Dict[str, bool]:
        """Delete client from multiple servers"""
        results = {}
        
        tasks = []
        for server_name in servers:
            if server_name in self.server_configs:
                config = self.server_configs[server_name]
                task = self._delete_client_from_server(config, client_uuid, inbound_id)
                tasks.append((server_name, task))
        
        # Execute all tasks concurrently
        for server_name, task in tasks:
            try:
                result = await task
                results[server_name] = result
                logger.info(f"Client deletion on {server_name}: {'Success' if result else 'Failed'}")
            except Exception as e:
                logger.error(f"Error deleting client on {server_name}: {e}")
                results[server_name] = False
        
        return results
    
    async def _delete_client_from_server(self, config: ServerConfig, client_uuid: str, 
                                       inbound_id: int) -> bool:
        """Delete client from a single server"""
        async with XUIApi(config) as api:
            return await api.delete_client(inbound_id, client_uuid)

def create_client_config(user_uuid: str, email: str, total_bytes: int, 
                        expire_days: int, limit_ip: int = 2) -> Dict:
    """Create client configuration dict"""
    import random
    import string
    
    # Convert expire_days to timestamp (milliseconds)
    expire_time = int((datetime.now().timestamp() + (expire_days * 24 * 3600)) * 1000)
    
    # Generate random subId
    subId = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    
    return {
        "id": user_uuid,
        "flow": "",
        "email": email,
        "limitIp": limit_ip,
        "totalGB": total_bytes,  # X-UI expects bytes; 0 means unlimited
        "expiryTime": expire_time,
        "enable": True,
        "tgId": "",
        "subId": subId,
        "reset": 0
    } 