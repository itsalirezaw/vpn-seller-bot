#!/usr/bin/env python3
"""
Check pending orders script
Shows all pending orders with their details
"""

import os
import sys
import logging
from datetime import datetime

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import db_manager, init_db
from database.models import Order
from sqlalchemy import text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def check_pending_orders():
    """Check all pending orders"""
    try:
        logger.info("Checking pending orders...")
        
        # Initialize database
        init_db()
        db = db_manager.get_session()
        try:
            # Get all pending orders
            pending_orders = db.query(Order).filter(Order.status == 'pending').all()
            
            logger.info(f"Found {len(pending_orders)} pending orders:")
            
            for order in pending_orders:
                age_minutes = (datetime.utcnow() - order.created_at).total_seconds() / 60
                logger.info(f"""
Order ID: {order.id}
  User ID: {order.user_id}
  Type: {order.type}
  Amount: {order.amount}
  Plan ID: {order.plan_id}
  Account ID: {order.account_id}
  Status: {order.status}
  Receipt Path: '{order.receipt_path}'
  Created: {order.created_at}
  Age: {age_minutes:.1f} minutes
  Processed: {order.processed_at}
""")
            
            # Also check all orders by status
            result = db.execute(text("SELECT status, COUNT(*) FROM orders GROUP BY status"))
            status_counts = result.fetchall()
            logger.info("\nAll orders by status:")
            for status, count in status_counts:
                logger.info(f"  {status}: {count}")
            
            return len(pending_orders)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error checking pending orders: {e}")
        raise

if __name__ == "__main__":
    try:
        count = check_pending_orders()
        logger.info(f"\nCheck completed. Found {count} pending orders.")
    except Exception as e:
        logger.error(f"Check failed: {e}")
        sys.exit(1) 