#!/usr/bin/env python3
"""
VPN Telegram Bot - Main Application Entry Point
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from database.database import init_db, init_default_data
from services.server_manager import server_manager
from services.config_templates import config_template_manager
from services.monitoring import monitoring_service
from bot.bot import VPNBot

# Create logs directory first
Path("logs").mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def initialize_services():
    """Initialize all services"""
    logger.info("Initializing services...")
    
    try:
        # Initialize database
        logger.info("Initializing database...")
        init_db()
        await init_default_data()
        
        # Initialize server manager
        logger.info("Initializing server manager...")
        await server_manager.initialize()
        
        # Load configuration templates
        logger.info("Loading configuration templates...")
        await config_template_manager.load_templates_from_db()
        
        # Start monitoring service
        logger.info("Starting monitoring service...")
        await monitoring_service.start_monitoring()
        
        logger.info("All services initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        return False



def main():
    """Main function"""
    logger.info("Starting VPN Telegram Bot...")
    
    # Check if bot token is provided
    if not settings.bot.token:
        logger.error("Bot token not provided. Please set BOT_TOKEN in .env file")
        sys.exit(1)
    
    # Check if servers are configured
    if not settings.servers:
        logger.error("No servers configured. Please add server configurations in .env file")
        sys.exit(1)
    
    # Prepare a fresh event loop for the rest of the application. Using
    # ``asyncio.run`` here would create *and* close a temporary event loop
    # which in turn breaks python-telegram-bot's internal call to
    # ``asyncio.get_event_loop`` (``There is no current event loop in thread
    # 'MainThread'``).

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Initialize services inside this long-lived loop so it stays available
    # for the bot afterwards.
    try:
        if not loop.run_until_complete(initialize_services()):
            logger.error("Failed to initialize services. Exiting...")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        sys.exit(1)
    
    # Create and start bot
    try:
        bot = VPNBot()
        bot.start()  # This will run indefinitely until interrupted
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
        
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        sys.exit(1)
    
    finally:
        # Cleanup
        logger.info("Shutting down services...")
        try:
            loop.run_until_complete(server_manager.stop_health_monitoring())
            loop.run_until_complete(monitoring_service.stop_monitoring())
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        finally:
            # Close the loop explicitly to free resources
            try:
                loop.close()
            except Exception:
                pass

        logger.info("Bot stopped")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1) 