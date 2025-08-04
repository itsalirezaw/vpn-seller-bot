from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, unique=True, index=True)
    username = Column(String, nullable=True)
    wallet_balance = Column(Float, default=0.0)
    invite_code = Column(String, unique=True, index=True)
    gift_data = Column(Integer, default=0)  # bytes
    gift_days = Column(Integer, default=0)
    test_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    accounts = relationship("Account", back_populates="user")
    orders = relationship("Order", back_populates="user")
    
    def __init__(self, chat_id, username=None):
        self.chat_id = chat_id
        self.username = username
        self.invite_code = str(chat_id)  # Use chat_id as invite code
    
    def __repr__(self):
        return f"<User(chat_id={self.chat_id}, username={self.username})>"

class Server(Base):
    __tablename__ = 'servers'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    host = Column(String)
    port = Column(Integer)
    web_base_path = Column(String)
    username = Column(String)
    password = Column(String)
    is_active = Column(Boolean, default=True)
    last_health_check = Column(DateTime, nullable=True)
    config = Column(JSON, nullable=True)  # Protocol configurations
    
    # Relationships
    server_accounts = relationship("ServerAccount", back_populates="server")
    
    @property
    def base_url(self):
        return f"http://{self.host}:{self.port}{self.web_base_path}"
    
    def __repr__(self):
        return f"<Server(name={self.name}, host={self.host})>"

class Account(Base):
    __tablename__ = 'accounts'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    uuid = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    total_data_limit = Column(Integer)  # bytes
    expire_time = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="accounts")
    server_accounts = relationship("ServerAccount", back_populates="account")
    
    def __init__(self, user_id, total_data_limit, expire_days):
        self.user_id = user_id
        self.uuid = str(uuid.uuid4())
        self.email = f"user_{user_id}_{self.uuid[:8]}"
        self.total_data_limit = total_data_limit
        self.expire_time = datetime.utcnow() + timedelta(days=expire_days)
    
    @property
    def is_expired(self):
        return datetime.utcnow() > self.expire_time
    
    @property
    def total_used_data(self):
        return sum(sa.data_used for sa in self.server_accounts)
    
    @property
    def remaining_data(self):
        if self.total_data_limit == 0:  # Unlimited
            return float('inf')
        return max(0, self.total_data_limit - self.total_used_data)
    
    @property
    def is_active(self):
        if self.is_expired:
            return False
        if self.total_data_limit > 0 and self.total_used_data >= self.total_data_limit:
            return False
        return True
    
    def __repr__(self):
        return f"<Account(uuid={self.uuid}, email={self.email})>"

class ServerAccount(Base):
    __tablename__ = 'server_accounts'
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey('accounts.id'))
    server_id = Column(Integer, ForeignKey('servers.id'))
    inbound_id = Column(Integer)
    data_used = Column(Integer, default=0)  # bytes
    last_sync = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    account = relationship("Account", back_populates="server_accounts")
    server = relationship("Server", back_populates="server_accounts")
    
    def __repr__(self):
        return f"<ServerAccount(account_id={self.account_id}, server_id={self.server_id})>"

class Order(Base):
    __tablename__ = 'orders'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    type = Column(String)  # 'purchase', 'wallet_charge', 'renewal'
    amount = Column(Float)
    plan_id = Column(String, nullable=True)  # Service plan ID
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=True)
    status = Column(String, default='pending')  # 'pending', 'approved', 'rejected'
    receipt_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="orders")
    
    def __repr__(self):
        return f"<Order(id={self.id}, user_id={self.user_id}, type={self.type}, status={self.status})>"

class ConfigTemplate(Base):
    __tablename__ = 'config_templates'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    protocol = Column(String)
    description = Column(String, nullable=True)
    template_data = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<ConfigTemplate(name={self.name}, protocol={self.protocol})>"

class UserSession(Base):
    __tablename__ = 'user_sessions'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    session_type = Column(String)  # 'purchase', 'wallet_charge', 'renewal'
    session_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    
    def __init__(self, user_id, session_type, session_data=None, expire_minutes=30):
        self.user_id = user_id
        self.session_type = session_type
        self.session_data = session_data or {}
        self.expires_at = datetime.utcnow() + timedelta(minutes=expire_minutes)
    
    @property
    def is_expired(self):
        return datetime.utcnow() > self.expires_at
    
    def __repr__(self):
        return f"<UserSession(user_id={self.user_id}, type={self.session_type})>"

class Invitation(Base):
    __tablename__ = 'invitations'
    
    id = Column(Integer, primary_key=True, index=True)
    inviter_id = Column(Integer, ForeignKey('users.id'))
    invited_id = Column(Integer, ForeignKey('users.id'))
    reward_claimed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Invitation(inviter_id={self.inviter_id}, invited_id={self.invited_id})>"

# ------------------------------------------------------------
# New model: Subscription
# ------------------------------------------------------------

class Subscription(Base):
    """Subscription link storage (token → base64 content)"""

    __tablename__ = 'subscriptions'

    token = Column(String, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey('accounts.id'))
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expire_at = Column(DateTime, nullable=True)

    # Relationship for convenience (optional)
    account = relationship("Account")

    def __repr__(self):
        return f"<Subscription(token={self.token}, account_id={self.account_id})>" 