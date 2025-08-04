#!/usr/bin/env python3
"""
Cleanup incomplete orders script
Removes orders without receipts that are older than 3 minutes
"""

import os
import sys
import logging
from datetime import datetime, timedelta
import asyncio

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import db_manager, init_db
from database.models import Order
from sqlalchemy import select, and_

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/vpn_bot/cleanup_orders.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def cleanup_incomplete_orders():
    """Clean up incomplete orders (without receipts) older than 3 minutes"""
    try:
        logger.info("Starting cleanup of incomplete orders...")
        
        # Initialize database to ensure tables exist
        init_db()
        logger.info("Database initialized successfully")
        
        # Calculate the cutoff time (3 minutes ago)
        cutoff_time = datetime.utcnow() - timedelta(minutes=3)
        
        # Get incomplete orders (pending orders without receipts older than 3 minutes)
        db = db_manager.get_session()
        try:
            # Find orders that are:
            # 1. Status is 'pending'
            # 2. No receipt_path (NULL or empty string)
            # 3. Created more than 3 minutes ago
            # 4. Type is not 'wallet' (wallet orders might not have receipts)
            incomplete_orders = db.query(Order).filter(
                and_(
                    Order.status == 'pending',
                    (Order.receipt_path.is_(None) | (Order.receipt_path == '')),
                    Order.created_at < cutoff_time,
                    Order.type.in_(['purchase', 'renewal'])  # Only cleanup purchase and renewal orders
                )
            ).all()
            
            if not incomplete_orders:
                logger.info("No incomplete orders found to clean up")
                return
            
            logger.info(f"Found {len(incomplete_orders)} incomplete orders to clean up")
            
            # Delete each incomplete order
            deleted_count = 0
            for order in incomplete_orders:
                try:
                    logger.info(f"Deleting incomplete order {order.id} (created: {order.created_at}, type: {order.type}, user_id: {order.user_id})")
                    
                    # Additional safety check: only delete if really old
                    if order.created_at < cutoff_time:
                        db.delete(order)
                        deleted_count += 1
                        logger.info(f"Successfully deleted order {order.id}")
                    else:
                        logger.warning(f"Order {order.id} is not old enough to delete (created: {order.created_at})")
                        
                except Exception as e:
                    logger.error(f"Error deleting order {order.id}: {e}")
            
            # Commit the changes
            db.commit()
            logger.info(f"Successfully deleted {deleted_count} incomplete orders")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Database error during cleanup: {e}")
            raise
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in cleanup_incomplete_orders: {e}")
        raise

async def test_database_connection():
    """Test database connection and tables"""
    try:
        logger.info("Testing database connection...")
        init_db()
        db = db_manager.get_session()
        try:
            # Check if orders table exists using SQLAlchemy
            from sqlalchemy import text
            result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'"))
            if result.fetchone():
                logger.info("✅ Orders table exists")
            else:
                logger.error("❌ Orders table does not exist")
                return False
            
            # Check table structure
            result = db.execute(text("PRAGMA table_info(orders)"))
            columns = result.fetchall()
            logger.info(f"Orders table has {len(columns)} columns")
            
            # Count orders by status
            result = db.execute(text("SELECT status, COUNT(*) FROM orders GROUP BY status"))
            status_counts = result.fetchall()
            logger.info("Orders by status:")
            for status, count in status_counts:
                logger.info(f"  {status}: {count}")
            
            # Count orders without receipts
            result = db.execute(text("""
                SELECT COUNT(*) FROM orders 
                WHERE status = 'pending' 
                AND (receipt_path IS NULL OR receipt_path = '')
            """))
            no_receipt_count = result.fetchone()[0]
            logger.info(f"Pending orders without receipts: {no_receipt_count}")
            
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Database test failed: {e}")
        return False

async def main():
    """Main function"""
    try:
        # Test database first
        if not await test_database_connection():
            logger.error("Database test failed, exiting...")
            sys.exit(1)
        
        await cleanup_incomplete_orders()
        logger.info("Cleanup completed successfully")
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 