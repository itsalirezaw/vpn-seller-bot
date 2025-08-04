import os
from typing import List, Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv
import logging

load_dotenv()

@dataclass
class ServerConfig:
    """Configuration for X-UI server"""
    name: str
    host: str
    port: int
    web_base_path: str
    username: str  # X-UI panel username
    password: str  # X-UI panel password
    ssh_username: str = "root"
    ssh_password: str = ""
    is_active: bool = True
    scheme: str = "http"  # Add scheme field for HTTP/HTTPS support
    
    @property
    def base_url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}{self.web_base_path}"

@dataclass
class PaymentCard:
    """Payment card configuration"""
    number: str
    owner: str
    bank: str = ""

@dataclass
class BotConfig:
    """Telegram bot configuration"""
    token: str
    ADMIN_IDS: List[int]
    payment_cards: List[PaymentCard]
    
@dataclass
class DatabaseConfig:
    """Database configuration"""
    url: str = "sqlite:///./vpn_bot.db"
    echo: bool = False

@dataclass
class Settings:
    """Main application settings"""
    bot: BotConfig
    database: DatabaseConfig
    servers: List[ServerConfig]
    
    # Test account settings
    test_account_data_limit: int = 1024 * 1024 * 1024  # 1GB in bytes
    test_account_expire_hours: int = 24
    
    # Invite system settings
    invite_reward_data: int = 5 * 1024 * 1024 * 1024  # 5GB in bytes
    invite_reward_days: int = 5
    
    # Payment settings
    min_wallet_charge: float = 10000.0  # تومان
    max_wallet_charge: float = 1000000.0  # تومان
    
    # Usage sync settings
    usage_sync_interval: int = 300  # seconds (5 minutes)
    health_check_interval: int = 300  # seconds (5 minutes)

def load_settings() -> Settings:
    """Load settings from environment variables"""
    
    # Payment cards configuration
    payment_cards = [
        # Card 1 - Bank Mellat
        PaymentCard(
            number=os.getenv("PAYMENT_CARD_NUMBER", "6104338670998711"),
            owner=os.getenv("PAYMENT_CARD_OWNER", "علیرضا افشار"),
            bank=os.getenv("PAYMENT_CARD_BANK", "بانک ملت")
        ),
        # Card 2 - Bank Saman  
        PaymentCard(
            number=os.getenv("PAYMENT_CARD_NUMBER_2", "6219861960758638"),
            owner=os.getenv("PAYMENT_CARD_OWNER_2", "علیرضا افشار"),
            bank=os.getenv("PAYMENT_CARD_BANK_2", "بانک سامان")
        )
    ]

    # Bot configuration
    bot_config = BotConfig(
        token=os.getenv("BOT_TOKEN", ""),
        ADMIN_IDS=[int(x) for x in os.getenv("ADMIN_IDS").split(",") if x],
        payment_cards=payment_cards
    )
    
    # Database configuration
    db_config = DatabaseConfig(
        url=os.getenv("DATABASE_URL", "sqlite:///./vpn_bot.db"),
        echo=os.getenv("DATABASE_ECHO", "false").lower() == "true"
    )
    
    # Server configurations
    servers = []
    server_count = int(os.getenv("SERVER_COUNT", "0"))
    for i in range(server_count):
        server = ServerConfig(
            name=os.getenv(f"SERVER_{i}_NAME", f"Server {i+1}"),
            host=os.getenv(f"SERVER_{i}_HOST", ""),
            port=int(os.getenv(f"SERVER_{i}_PORT", "54321")),
            web_base_path=os.getenv(f"SERVER_{i}_WEB_BASE_PATH", "/"),
            username=os.getenv(f"SERVER_{i}_USERNAME", "admin"),
            password=os.getenv(f"SERVER_{i}_PASSWORD", ""),
            is_active=os.getenv(f"SERVER_{i}_ACTIVE", "true").lower() == "true",
            scheme=os.getenv(f"SERVER_{i}_SCHEME", "http"),  # Add scheme support
            ssh_username=os.getenv(f"SERVER_{i}_SSH_USERNAME", os.getenv("DEFAULT_SSH_USERNAME", "root")),
            ssh_password=os.getenv(f"SERVER_{i}_SSH_PASSWORD", os.getenv("DEFAULT_SSH_PASSWORD", ""))
        )
        servers.append(server)
    
    return Settings(
        bot=bot_config,
        database=db_config,
        servers=servers
    )

# Global settings instance
settings = load_settings()

# Service plans - New structure with time periods first
SERVICE_PLANS = {
    # 1 Month Plans
    "1m_30gb": {
        "name": "یک ماهه - 30 گیگ",
        "period": "1m",
        "period_name": "یک ماهه", 
        "data_limit": 30 * 1024 * 1024 * 1024,  # 30GB
        "expire_days": 30,
        "price": 87000
    },
    "1m_50gb": {
        "name": "یک ماهه - 50 گیگ",
        "period": "1m",
        "period_name": "یک ماهه",
        "data_limit": 50 * 1024 * 1024 * 1024,  # 50GB
        "expire_days": 30,
        "price": 145000
    },
    "1m_70gb": {
        "name": "یک ماهه - 70 گیگ",
        "period": "1m",
        "period_name": "یک ماهه",
        "data_limit": 70 * 1024 * 1024 * 1024,  # 70GB
        "expire_days": 30,
        "price": 200000
    },
    
    # 3 Month Plans
    "3m_120gb": {
        "name": "سه ماهه - 120 گیگ",
        "period": "3m",
        "period_name": "سه ماهه",
        "data_limit": 120 * 1024 * 1024 * 1024,  # 120GB
        "expire_days": 90,
        "price": 330000
    },
    "3m_150gb": {
        "name": "سه ماهه - 150 گیگ",
        "period": "3m", 
        "period_name": "سه ماهه",
        "data_limit": 150 * 1024 * 1024 * 1024,  # 150GB
        "expire_days": 90,
        "price": 410000
    },
    "3m_210gb": {
        "name": "سه ماهه - 210 گیگ",
        "period": "3m",
        "period_name": "سه ماهه", 
        "data_limit": 210 * 1024 * 1024 * 1024,  # 210GB
        "expire_days": 90,
        "price": 580000
    },
    
    # 6 Month Plans
    "6m_240gb": {
        "name": "شش ماهه - 240 گیگ",
        "period": "6m",
        "period_name": "شش ماهه",
        "data_limit": 240 * 1024 * 1024 * 1024,  # 240GB
        "expire_days": 180,
        "price": 499000
    },
    "6m_400gb": {
        "name": "شش ماهه - 400 گیگ", 
        "period": "6m",
        "period_name": "شش ماهه",
        "data_limit": 400 * 1024 * 1024 * 1024,  # 400GB
        "expire_days": 180,
        "price": 830000
    },
    "6m_560gb": {
        "name": "شش ماهه - 560 گیگ",
        "period": "6m",
        "period_name": "شش ماهه",
        "data_limit": 560 * 1024 * 1024 * 1024,  # 560GB
        "expire_days": 180,
        "price": 1160000
    }
}

# Protocol templates with complete config specifications
PROTOCOL_TEMPLATES = {
    "vmess_tcp": {
        "name": "🇫🇮 Finland |  فنلاند",
        "protocol": "vmess",
        "allowed_servers": ["Finland Server"],
        "port": 40179,
        "config_template": {
            "v": "2",
            "ps": "🇫🇮 Finland |  فنلاند ( SPEED 🚀⚡️)",
            "add": "world2.prvprt.com",
            "port": "40179",
            "id": "{user_uuid}",
            "aid": "0",
            "scy": "auto",
            "net": "tcp",
            "type": "none",
            "host": "",
            "path": "",
            "tls": "none",
            "sni": "",
            "alpn": ""
        }
    },
    "vmess_tcp_iran": {
        "name": "🇫🇮 Finland |  فنلاند",
        "protocol": "vmess",
        "allowed_servers": ["Iran Server"],
        "port": 40179,
        "config_template": {
            "v": "2",
            "ps": "🇫🇮 Finland |  فنلاند",
            "add": "tu1.prvprt.com",
            "port": "40179",
            "id": "{user_uuid}",
            "aid": "0",
            "scy": "auto",
            "net": "tcp",
            "type": "none",
            "host": "",
            "path": "",
            "tls": "none",
            "sni": "",
            "alpn": ""
        }
    },
    "vmess_ws_france": {
        "name": "🇫🇷 France  |  فرانسه",
        "protocol": "vmess",
        "allowed_servers": ["France Server"],
        "port": 40179,
        "config_template": {
            "v": "2",
            "ps": "🇫🇷 France  |  فرانسه",
            "add": "fr.prvprt.com",
            "port": "40179",
            "id": "{user_uuid}",
            "aid": "0",
            "scy": "auto",
            "net": "ws",
            "type": "none",
            "host": "",
            "path": "/",
            "tls": "none",
            "sni": "",
            "alpn": ""
        }
    }
}

# Additional convenience variables
ADMIN_IDS = settings.bot.ADMIN_IDS
service_plans = SERVICE_PLANS

# Persian numbers for display
persian_numbers = {
    '0': '۰', '1': '۱', '2': '۲', '3': '۳', '4': '۴',
    '5': '۵', '6': '۶', '7': '۷', '8': '۸', '9': '۹'
}

def to_persian_number(text: str) -> str:
    """Convert English numbers to Persian numbers"""
    for en, fa in persian_numbers.items():
        text = text.replace(en, fa)
    return text 

def generate_config_from_template(template_name: str, user_uuid: str, server_host: str, server_name: str) -> str:
    """Generate user config from template"""
    import json
    import base64
    
    if template_name not in PROTOCOL_TEMPLATES:
        return ""
    
    template = PROTOCOL_TEMPLATES[template_name]
    config_template = template["config_template"]
    
    # Replace placeholders
    if isinstance(config_template, dict):
        # VMess format - need to encode to base64
        config = config_template.copy()
        for key, value in config.items():
            if isinstance(value, str):
                config[key] = value.format(
                    user_uuid=user_uuid,
                    server_host=server_host,
                    server_name=server_name
                )
        
        # Encode VMess config to base64
        config_json = json.dumps(config)
        config_b64 = base64.b64encode(config_json.encode()).decode()
        return f"vmess://{config_b64}"
    
    else:
        # VLESS/Trojan format - direct URL
        return config_template.format(
            user_uuid=user_uuid,
            server_host=server_host,
            server_name=server_name
        )

def get_template_port(template_name: str) -> int:
    """Get port for specific template"""
    if template_name in PROTOCOL_TEMPLATES:
        return PROTOCOL_TEMPLATES[template_name]["port"]
    return 443  # Default port

def get_template_xui_config(template_name: str) -> dict:
    """Get X-UI inbound config for template"""
    if template_name in PROTOCOL_TEMPLATES:
        return PROTOCOL_TEMPLATES[template_name]["xui_inbound"]
    return {} 

# Debug: log loaded servers and their base URLs
logger = logging.getLogger(__name__)
for _srv in settings.servers:
    logger.warning(
        "Loaded server %s scheme=%s base_url=%s",
        _srv.name,
        _srv.scheme,
        _srv.base_url,
    ) 