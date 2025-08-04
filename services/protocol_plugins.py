from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import json
import base64
import logging
from urllib.parse import quote
from datetime import datetime

logger = logging.getLogger(__name__)

class ProtocolPlugin(ABC):
    """Abstract base class for protocol plugins"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @abstractmethod
    async def generate_inbound_config(self, account_data: Dict, server_config: Dict) -> Dict:
        """Generate inbound configuration for X-UI panel"""
        pass
    
    @abstractmethod
    async def generate_client_config(self, account_data: Dict, server_config: Dict) -> str:
        """Generate client configuration URL"""
        pass
    
    @abstractmethod
    async def generate_qr_config(self, account_data: Dict, server_config: Dict) -> str:
        """Generate QR code configuration"""
        pass
    
    @abstractmethod
    def get_default_settings(self) -> Dict:
        """Get default settings for this protocol"""
        pass
    
    def validate_config(self, config: Dict) -> bool:
        """Validate configuration"""
        return True

class VMessWSPlugin(ProtocolPlugin):
    """VMess WebSocket protocol plugin"""
    
    def __init__(self):
        super().__init__("vmess_ws", "VMess over WebSocket")
    
    async def generate_inbound_config(self, account_data: Dict, server_config: Dict) -> Dict:
        """Generate VMess WS inbound configuration"""
        return {
            "listen": server_config.get("listen", "0.0.0.0"),
            "port": server_config.get("port", 443),
            "protocol": "vmess",
            "settings": {
                "clients": [{
                    "id": account_data["uuid"],
                    "alterId": 0,
                    "email": account_data["email"],
                    "limitIp": account_data.get("limit_ip", 2),
                    "totalGB": account_data.get("total_bytes", 0),
                    "expiryTime": account_data.get("expiry_time", 0),
                    "enable": True,
                    "tgId": "",
                    "subId": "",
                    "flow": ""
                }],
                "decryption": "none",
                "fallbacks": []
            },
            "streamSettings": {
                "network": "ws",
                "security": "none",
                "wsSettings": {
                    "path": server_config.get("ws_path", "/"),
                    "headers": server_config.get("ws_headers", {})
                }
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls"]
            }
        }
    
    async def generate_client_config(self, account_data: Dict, server_config: Dict) -> str:
        """Generate VMess client configuration URL"""
        config = {
            "v": "2",
            "ps": f"{server_config.get('name', 'Server')} - VMess WS",
            "add": server_config["host"],
            "port": str(server_config.get("port", 443)),
            "id": account_data["uuid"],
            "aid": "0",
            "net": "ws",
            "type": "none",
            "host": server_config.get("host", ""),
            "path": server_config.get("ws_path", "/"),
            "tls": "none"
        }
        
        # Encode to base64
        config_json = json.dumps(config)
        config_b64 = base64.b64encode(config_json.encode()).decode()
        return f"vmess://{config_b64}"
    
    async def generate_qr_config(self, account_data: Dict, server_config: Dict) -> str:
        """Generate QR code configuration (same as client config for VMess)"""
        return await self.generate_client_config(account_data, server_config)
    
    def get_default_settings(self) -> Dict:
        """Get default settings for VMess WS"""
        return {
            "port": 443,
            "ws_path": "/",
            "ws_headers": {},
            "security": "none"
        }

class VMessTCPPlugin(ProtocolPlugin):
    """VMess TCP protocol plugin"""
    
    def __init__(self):
        super().__init__("vmess_tcp", "VMess over TCP")
    
    async def generate_inbound_config(self, account_data: Dict, server_config: Dict) -> Dict:
        """Generate VMess TCP inbound configuration"""
        return {
            "listen": server_config.get("listen", "0.0.0.0"),
            "port": server_config.get("port", 10086),
            "protocol": "vmess",
            "settings": {
                "clients": [{
                    "id": account_data["uuid"],
                    "alterId": 0,
                    "email": account_data["email"],
                    "limitIp": account_data.get("limit_ip", 2),
                    "totalGB": account_data.get("total_bytes", 0),
                    "expiryTime": account_data.get("expiry_time", 0),
                    "enable": True,
                    "tgId": "",
                    "subId": "",
                    "flow": ""
                }],
                "decryption": "none",
                "fallbacks": []
            },
            "streamSettings": {
                "network": "tcp",
                "security": "none",
                "tcpSettings": {
                    "header": {
                        "type": "none"
                    }
                }
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls"]
            }
        }
    
    async def generate_client_config(self, account_data: Dict, server_config: Dict) -> str:
        """Generate VMess TCP client configuration URL"""
        config = {
            "v": "2",
            "ps": f"{server_config.get('name', 'Server')} - VMess TCP",
            "add": server_config["host"],
            "port": str(server_config.get("port", 10086)),
            "id": account_data["uuid"],
            "aid": "0",
            "net": "tcp",
            "type": "none",
            "host": "",
            "path": "",
            "tls": "none"
        }
        
        # Encode to base64
        config_json = json.dumps(config)
        config_b64 = base64.b64encode(config_json.encode()).decode()
        return f"vmess://{config_b64}"
    
    async def generate_qr_config(self, account_data: Dict, server_config: Dict) -> str:
        """Generate QR code configuration"""
        return await self.generate_client_config(account_data, server_config)
    
    def get_default_settings(self) -> Dict:
        """Get default settings for VMess TCP"""
        return {
            "port": 10086,
            "security": "none"
        }

class VLESSWSPlugin(ProtocolPlugin):
    """VLESS WebSocket protocol plugin"""
    
    def __init__(self):
        super().__init__("vless_ws", "VLESS over WebSocket")
    
    async def generate_inbound_config(self, account_data: Dict, server_config: Dict) -> Dict:
        """Generate VLESS WS inbound configuration"""
        return {
            "listen": server_config.get("listen", "0.0.0.0"),
            "port": server_config.get("port", 443),
            "protocol": "vless",
            "settings": {
                "clients": [{
                    "id": account_data["uuid"],
                    "email": account_data["email"],
                    "limitIp": account_data.get("limit_ip", 2),
                    "totalGB": account_data.get("total_bytes", 0),
                    "expiryTime": account_data.get("expiry_time", 0),
                    "enable": True,
                    "tgId": "",
                    "subId": "",
                    "flow": ""
                }],
                "decryption": "none",
                "fallbacks": []
            },
            "streamSettings": {
                "network": "ws",
                "security": "none",
                "wsSettings": {
                    "path": server_config.get("ws_path", "/"),
                    "headers": server_config.get("ws_headers", {})
                }
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls"]
            }
        }
    
    async def generate_client_config(self, account_data: Dict, server_config: Dict) -> str:
        """Generate VLESS client configuration URL"""
        query_params = []
        query_params.append("type=ws")
        query_params.append("security=none")
        
        ws_path = server_config.get("ws_path", "/")
        query_params.append(f"path={quote(ws_path)}")
        
        if server_config.get("ws_headers"):
            for key, value in server_config["ws_headers"].items():
                query_params.append(f"header={quote(f'{key}:{value}')}")
        
        query_string = "&".join(query_params)
        server_name = quote(f"{server_config.get('name', 'Server')} - VLESS WS")
        
        return f"vless://{account_data['uuid']}@{server_config['host']}:{server_config.get('port', 443)}?{query_string}#{server_name}"
    
    async def generate_qr_config(self, account_data: Dict, server_config: Dict) -> str:
        """Generate QR code configuration"""
        return await self.generate_client_config(account_data, server_config)
    
    def get_default_settings(self) -> Dict:
        """Get default settings for VLESS WS"""
        return {
            "port": 443,
            "ws_path": "/",
            "ws_headers": {},
            "security": "none"
        }

class VLESSTCPPlugin(ProtocolPlugin):
    """VLESS TCP protocol plugin"""
    
    def __init__(self):
        super().__init__("vless_tcp", "VLESS over TCP")
    
    async def generate_inbound_config(self, account_data: Dict, server_config: Dict) -> Dict:
        """Generate VLESS TCP inbound configuration"""
        return {
            "listen": server_config.get("listen", "0.0.0.0"),
            "port": server_config.get("port", 10087),
            "protocol": "vless",
            "settings": {
                "clients": [{
                    "id": account_data["uuid"],
                    "email": account_data["email"],
                    "limitIp": account_data.get("limit_ip", 2),
                    "totalGB": account_data.get("total_bytes", 0),
                    "expiryTime": account_data.get("expiry_time", 0),
                    "enable": True,
                    "tgId": "",
                    "subId": "",
                    "flow": ""
                }],
                "decryption": "none",
                "fallbacks": []
            },
            "streamSettings": {
                "network": "tcp",
                "security": "none",
                "tcpSettings": {
                    "header": {
                        "type": "none"
                    }
                }
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls"]
            }
        }
    
    async def generate_client_config(self, account_data: Dict, server_config: Dict) -> str:
        """Generate VLESS TCP client configuration URL"""
        query_params = []
        query_params.append("type=tcp")
        query_params.append("security=none")
        
        query_string = "&".join(query_params)
        server_name = quote(f"{server_config.get('name', 'Server')} - VLESS TCP")
        
        return f"vless://{account_data['uuid']}@{server_config['host']}:{server_config.get('port', 10087)}?{query_string}#{server_name}"
    
    async def generate_qr_config(self, account_data: Dict, server_config: Dict) -> str:
        """Generate QR code configuration"""
        return await self.generate_client_config(account_data, server_config)
    
    def get_default_settings(self) -> Dict:
        """Get default settings for VLESS TCP"""
        return {
            "port": 10087,
            "security": "none"
        }

class TrojanWSPlugin(ProtocolPlugin):
    """Trojan WebSocket protocol plugin"""
    
    def __init__(self):
        super().__init__("trojan_ws", "Trojan over WebSocket")
    
    async def generate_inbound_config(self, account_data: Dict, server_config: Dict) -> Dict:
        """Generate Trojan WS inbound configuration"""
        return {
            "listen": server_config.get("listen", "0.0.0.0"),
            "port": server_config.get("port", 443),
            "protocol": "trojan",
            "settings": {
                "clients": [{
                    "password": account_data["uuid"],
                    "email": account_data["email"],
                    "limitIp": account_data.get("limit_ip", 2),
                    "totalGB": account_data.get("total_bytes", 0),
                    "expiryTime": account_data.get("expiry_time", 0),
                    "enable": True,
                    "tgId": "",
                    "subId": "",
                    "flow": ""
                }],
                "fallbacks": []
            },
            "streamSettings": {
                "network": "ws",
                "security": "tls",
                "wsSettings": {
                    "path": server_config.get("ws_path", "/"),
                    "headers": server_config.get("ws_headers", {})
                },
                "tlsSettings": {
                    "serverName": server_config.get("server_name", ""),
                    "certificates": []
                }
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls"]
            }
        }
    
    async def generate_client_config(self, account_data: Dict, server_config: Dict) -> str:
        """Generate Trojan client configuration URL"""
        query_params = []
        query_params.append("type=ws")
        query_params.append("security=tls")
        
        ws_path = server_config.get("ws_path", "/")
        query_params.append(f"path={quote(ws_path)}")
        
        if server_config.get("server_name"):
            query_params.append(f"sni={quote(server_config['server_name'])}")
        
        query_string = "&".join(query_params)
        server_name = quote(f"{server_config.get('name', 'Server')} - Trojan WS")
        
        return f"trojan://{account_data['uuid']}@{server_config['host']}:{server_config.get('port', 443)}?{query_string}#{server_name}"
    
    async def generate_qr_config(self, account_data: Dict, server_config: Dict) -> str:
        """Generate QR code configuration"""
        return await self.generate_client_config(account_data, server_config)
    
    def get_default_settings(self) -> Dict:
        """Get default settings for Trojan WS"""
        return {
            "port": 443,
            "ws_path": "/",
            "ws_headers": {},
            "security": "tls",
            "server_name": ""
        }

class ProtocolManager:
    """Manager for protocol plugins"""
    
    def __init__(self):
        self.plugins: Dict[str, ProtocolPlugin] = {}
        self._register_default_plugins()
    
    def _register_default_plugins(self):
        """Register default protocol plugins"""
        self.register_plugin(VMessWSPlugin())
        self.register_plugin(VMessTCPPlugin())
        self.register_plugin(VLESSWSPlugin())
        self.register_plugin(VLESSTCPPlugin())
        self.register_plugin(TrojanWSPlugin())
    
    def register_plugin(self, plugin: ProtocolPlugin):
        """Register a new protocol plugin"""
        self.plugins[plugin.name] = plugin
        logger.info(f"Registered protocol plugin: {plugin.name}")
    
    def get_plugin(self, name: str) -> Optional[ProtocolPlugin]:
        """Get plugin by name"""
        return self.plugins.get(name)
    
    def get_all_plugins(self) -> Dict[str, ProtocolPlugin]:
        """Get all registered plugins"""
        return self.plugins.copy()
    
    def get_plugin_names(self) -> List[str]:
        """Get all plugin names"""
        return list(self.plugins.keys())
    
    async def generate_configs_for_account(self, account_data: Dict, server_config: Dict, 
                                         protocols: List[str] = None) -> Dict[str, str]:
        """Generate configurations for account using specified protocols"""
        configs = {}
        
        if protocols is None:
            protocols = list(self.plugins.keys())
        
        for protocol in protocols:
            plugin = self.get_plugin(protocol)
            if plugin:
                try:
                    config_url = await plugin.generate_client_config(account_data, server_config)
                    configs[protocol] = config_url
                except Exception as e:
                    logger.error(f"Error generating config for {protocol}: {e}")
        
        return configs
    
    async def generate_inbound_configs(self, account_data: Dict, server_config: Dict, 
                                     protocols: List[str] = None) -> Dict[str, Dict]:
        """Generate inbound configurations for X-UI panel"""
        configs = {}
        
        if protocols is None:
            protocols = list(self.plugins.keys())
        
        for protocol in protocols:
            plugin = self.get_plugin(protocol)
            if plugin:
                try:
                    inbound_config = await plugin.generate_inbound_config(account_data, server_config)
                    configs[protocol] = inbound_config
                except Exception as e:
                    logger.error(f"Error generating inbound config for {protocol}: {e}")
        
        return configs
    
    def validate_plugin_config(self, plugin_name: str, config: Dict) -> bool:
        """Validate configuration for a plugin"""
        plugin = self.get_plugin(plugin_name)
        if plugin:
            return plugin.validate_config(config)
        return False
    
    def add_custom_plugin(self, plugin_class: type, **kwargs):
        """Add custom plugin from class"""
        try:
            plugin = plugin_class(**kwargs)
            if isinstance(plugin, ProtocolPlugin):
                self.register_plugin(plugin)
                return True
            else:
                logger.error(f"Plugin {plugin_class.__name__} is not a ProtocolPlugin")
                return False
        except Exception as e:
            logger.error(f"Error adding custom plugin: {e}")
            return False

# Global protocol manager instance
protocol_manager = ProtocolManager()

# Export for easy access
__all__ = [
    'ProtocolPlugin',
    'VMessWSPlugin',
    'VMessTCPPlugin', 
    'VLESSWSPlugin',
    'VLESSTCPPlugin',
    'TrojanWSPlugin',
    'ProtocolManager',
    'protocol_manager'
] 