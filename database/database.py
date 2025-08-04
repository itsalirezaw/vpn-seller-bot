from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from contextlib import asynccontextmanager
import asyncio
import logging
from sqlalchemy import inspect, text
from .models import Base
from config.settings import settings

logger = logging.getLogger(__name__)

# Synchronous database engine
engine = create_engine(
    settings.database.url,
    echo=settings.database.echo,
    pool_pre_ping=True,
    pool_recycle=300
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Async database engine (for monitoring and other async operations)
async_engine = create_async_engine(
    settings.database.url.replace('sqlite:///', 'sqlite+aiosqlite:///'),
    echo=settings.database.echo,
    pool_pre_ping=True,
    pool_recycle=300
)

# Async session factory
async_session = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@asynccontextmanager
async def get_async_db():
    """Async database session context manager"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables"""
    try:
        Base.metadata.create_all(bind=engine)

        # ------------------------------------------------------------------
        # Lightweight, one-off migrations for legacy SQLite databases
        # ------------------------------------------------------------------
        # 1) Ensure all columns exist in "orders" table (for legacy databases)
        try:
            with engine.connect() as conn:
                inspector = inspect(conn)
                order_cols = [col["name"] for col in inspector.get_columns("orders")]
                
                # Check and add missing columns
                missing_columns = []
                
                if "plan_id" not in order_cols:
                    conn.execute(text("ALTER TABLE orders ADD COLUMN plan_id VARCHAR"))
                    missing_columns.append("plan_id")
                
                if "receipt_path" not in order_cols:
                    conn.execute(text("ALTER TABLE orders ADD COLUMN receipt_path VARCHAR"))
                    missing_columns.append("receipt_path")
                
                if "account_id" not in order_cols:
                    conn.execute(text("ALTER TABLE orders ADD COLUMN account_id INTEGER"))
                    missing_columns.append("account_id")
                
                if "processed_at" not in order_cols:
                    conn.execute(text("ALTER TABLE orders ADD COLUMN processed_at DATETIME"))
                    missing_columns.append("processed_at")
                
                if missing_columns:
                    logger.info(f"Added missing columns to 'orders' table: {', '.join(missing_columns)}")
                    
        except Exception as mig_err:
            logger.error(f"Failed to run DB migration: {mig_err}")

        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise

def drop_db():
    """Drop all database tables"""
    try:
        Base.metadata.drop_all(bind=engine)
        logger.info("Database tables dropped successfully")
    except Exception as e:
        logger.error(f"Error dropping database tables: {e}")
        raise

async def init_default_data():
    """Initialize default data"""
    from .models import Server, ConfigTemplate
    from config.settings import PROTOCOL_TEMPLATES
    
    db = SessionLocal()
    try:
        # Initialize servers from config
        for server_config in settings.servers:
            existing_server = db.query(Server).filter_by(
                host=server_config.host,
                port=server_config.port
            ).first()
            
            if not existing_server:
                server = Server(
                    name=server_config.name,
                    host=server_config.host,
                    port=server_config.port,
                    web_base_path=server_config.web_base_path,
                    username=server_config.username,
                    password=server_config.password,
                    is_active=server_config.is_active
                )
                db.add(server)
                logger.info(f"Added server: {server_config.name}")
        
        # Initialize protocol templates
        for template_name, template_data in PROTOCOL_TEMPLATES.items():
            existing_template = db.query(ConfigTemplate).filter_by(
                name=template_name
            ).first()
            
            if not existing_template:
                config_template = ConfigTemplate(
                    name=template_name,
                    protocol=template_data["protocol"],
                    description=template_data["name"],
                    template_data=template_data
                )
                db.add(config_template)
                logger.info(f"Added protocol template: {template_name}")
        
        db.commit()
        logger.info("Default data initialized successfully")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error initializing default data: {e}")
        raise
    finally:
        db.close()

class DatabaseManager:
    """Database manager for common operations"""
    
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
    
    def get_session(self):
        """Get database session"""
        return self.SessionLocal()
    
    async def get_user_by_chat_id(self, chat_id: int):
        """Get user by chat ID"""
        from .models import User
        
        db = self.get_session()
        try:
            return db.query(User).filter_by(chat_id=chat_id).first()
        finally:
            db.close()
    
    async def create_user(self, chat_id: int, username: str = None):
        """Create new user"""
        from .models import User
        
        db = self.get_session()
        try:
            user = User(chat_id=chat_id, username=username)
            db.add(user)
            db.commit()
            db.refresh(user)
            return user
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating user: {e}")
            raise
        finally:
            db.close()
    
    async def get_or_create_user(self, chat_id: int, username: str = None):
        """Get existing user or create new one"""
        user = await self.get_user_by_chat_id(chat_id)
        if not user:
            user = await self.create_user(chat_id, username)
        return user
    
    async def get_active_servers(self):
        """Get all active servers"""
        from .models import Server
        
        db = self.get_session()
        try:
            return db.query(Server).filter_by(is_active=True).all()
        finally:
            db.close()
    
    async def get_user_accounts(self, user_id: int):
        """Get all accounts for a user"""
        from .models import Account
        
        db = self.get_session()
        try:
            return db.query(Account).filter_by(user_id=user_id).all()
        finally:
            db.close()
    
    async def get_pending_orders(self, user_id: int):
        """Get pending orders for a user"""
        from .models import Order
        
        db = self.get_session()
        try:
            return db.query(Order).filter_by(
                user_id=user_id,
                status='pending'
            ).all()
        finally:
            db.close()
    
    async def create_order(self, user_id: int, order_type: str, amount: float, 
                          plan_id: str = None, account_id: int = None):
        """Create new order"""
        from .models import Order
        
        db = self.get_session()
        try:
            order = Order(
                user_id=user_id,
                type=order_type,
                amount=amount,
                plan_id=plan_id,
                account_id=account_id
            )
            db.add(order)
            db.commit()
            db.refresh(order)
            return order
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating order: {e}")
            raise
        finally:
            db.close()
    
    async def delete_order(self, order_id: int):
        """Delete order by ID"""
        from .models import Order
        
        db = self.get_session()
        try:
            order = db.query(Order).filter_by(id=order_id).first()
            if order:
                db.delete(order)
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting order: {e}")
            raise
        finally:
            db.close()
    
    async def update_user_wallet(self, user_id: int, amount: float):
        """Update user wallet balance"""
        from .models import User
        
        db = self.get_session()
        try:
            user = db.query(User).filter_by(id=user_id).first()
            if user:
                user.wallet_balance += amount
                db.commit()
                return user
            return None
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating user wallet: {e}")
            raise
        finally:
            db.close()

    async def update_user(self, user):
        """Update user information"""
        from .models import User
        
        db = self.get_session()
        try:
            # Merge the user object with the database session
            db.merge(user)
            db.commit()
            return user
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating user: {e}")
            raise
        finally:
            db.close()

# Global database manager instance
db_manager = DatabaseManager() 