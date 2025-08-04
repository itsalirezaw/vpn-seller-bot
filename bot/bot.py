import logging
from telegram import Update, BotCommand
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    ConversationHandler,
    filters
)

from config.settings import settings
from database.database import db_manager
from services.server_manager import server_manager
from services.account_manager import account_manager
from bot.handlers import (
    start_handler,
    main_menu_handler,
    services_handler,
    purchase_handler,
    renewal_handler,
    payment_handler,
    invite_handler,
    test_account_handler,
    admin_handler
)
from bot.keyboards import get_main_keyboard
from bot.states import ConversationStates
from bot.utils import is_admin
import asyncio
import telegram.error

logger = logging.getLogger(__name__)

class VPNBot:
    """Main VPN Telegram Bot class"""
    
    def __init__(self):
        self.application = None
        self.bot_token = settings.bot.token
        self.ADMIN_IDS = settings.bot.ADMIN_IDS
        
    def start(self):
        """Start the bot"""
        try:
            # Create application
            self.application = Application.builder().token(self.bot_token).build()
            
            # Setup handlers synchronously
            self.setup_handlers_sync()
            
            # Set bot commands (will be done after application starts)
            # self.set_bot_commands()  # Temporarily disabled
            
            # Start polling - this manages its own event loop
            logger.info("Bot started successfully")
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            raise
    
    def stop(self):
        """Stop the bot"""
        if self.application:
            logger.info("Stopping bot...")
            try:
                # Application will be stopped automatically by run_polling when interrupted
                logger.info("Bot stopped")
            except Exception as e:
                logger.error(f"Error stopping bot: {e}")
    
    def setup_handlers_sync(self):
        """Setup all message handlers"""
        app = self.application
        
        # Start command
        app.add_handler(CommandHandler("start", start_handler))
        
        # Main menu handlers
        app.add_handler(CallbackQueryHandler(main_menu_handler, pattern="^main_"))
        # Wallet info handler
        app.add_handler(CallbackQueryHandler(main_menu_handler, pattern="^wallet_info$"))
        
        # Services handlers
        app.add_handler(CallbackQueryHandler(services_handler, pattern="^services_"))
        # Add confirm delete handler for services
        app.add_handler(CallbackQueryHandler(services_handler, pattern="^confirm_delete_"))
        # Handle renew_service callback from main menu
        app.add_handler(CallbackQueryHandler(services_handler, pattern="^renew_service$"))
        # Handle config copy callbacks
        app.add_handler(CallbackQueryHandler(services_handler, pattern="^config_copy_all_"))
        # Handle gift account callbacks
        app.add_handler(CallbackQueryHandler(invite_handler, pattern="^gift_account_"))
        
        # Purchase conversation handler
        purchase_conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(purchase_handler, pattern="^purchase_"),
                # Catch direct clicks on plan_ buttons even if state lost
                CallbackQueryHandler(purchase_handler, pattern="^plan_")
            ],
            states={
                ConversationStates.PURCHASE_PLAN_SELECTION: [
                    CallbackQueryHandler(purchase_handler, pattern="^period_"),
                    CallbackQueryHandler(purchase_handler, pattern="^plan_")
                ],
                ConversationStates.PURCHASE_PAYMENT_METHOD: [
                    CallbackQueryHandler(purchase_handler, pattern="^payment_"),
                    CallbackQueryHandler(purchase_handler, pattern="^confirm_wallet_payment")
                ],
                ConversationStates.PURCHASE_RECEIPT_UPLOAD: [
                    MessageHandler(filters.PHOTO | filters.Document.ALL, payment_handler)
                ],
            },
            fallbacks=[
                CallbackQueryHandler(purchase_handler, pattern="^cancel_purchase"),
                CommandHandler("cancel", purchase_handler)
            ]
        )
        app.add_handler(purchase_conv_handler)
        
        # Handle stray purchase_new callbacks outside conversation (safety)
        app.add_handler(CallbackQueryHandler(purchase_handler, pattern="^purchase_new$"))
        
        # Invite system handlers
        app.add_handler(CallbackQueryHandler(invite_handler, pattern="^invite_"))
        
        # Test account handlers
        app.add_handler(CallbackQueryHandler(test_account_handler, pattern="^test_"))
        
        # Admin handlers (only for admin users)
        app.add_handler(CommandHandler("admin", admin_handler, filters=filters.User(self.ADMIN_IDS)))
        app.add_handler(CallbackQueryHandler(admin_handler, pattern="^admin_"))
        # Add missing admin callbacks
        # Admin-specific generic confirm/cancel (start with admin_)
        app.add_handler(CallbackQueryHandler(admin_handler, pattern="^admin_confirm_.*"))
        app.add_handler(CallbackQueryHandler(admin_handler, pattern="^admin_cancel_.*"))
        
        # Wallet charge conversation handler
        wallet_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(payment_handler, pattern="^wallet_charge")],
            states={
                ConversationStates.WALLET_AMOUNT_INPUT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, payment_handler)
                ],
                ConversationStates.WALLET_RECEIPT_UPLOAD: [
                    MessageHandler(filters.PHOTO | filters.Document.ALL, payment_handler)
                ],
            },
            fallbacks=[
                CallbackQueryHandler(payment_handler, pattern="^cancel_wallet"),
                CommandHandler("cancel", payment_handler)
            ]
        )
        app.add_handler(wallet_conv_handler)
        
        # # Renewal direct service callback (safety)
        # app.add_handler(CallbackQueryHandler(renewal_handler, pattern="^renew_service$"))
        # # Direct renew_<id> callback (safety)
        # app.add_handler(CallbackQueryHandler(renewal_handler, pattern="^renew_[0-9]+$"))
        # # Direct renewal_plan_<id>_<planId> callback (safety)
        # app.add_handler(CallbackQueryHandler(renewal_handler, pattern="^renewal_payment_")) # safety for payment step
        # app.add_handler(CallbackQueryHandler(renewal_handler, pattern="^renewal_"))

        # Renewal conversation handler
        renewal_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(services_handler, pattern="^renew_[0-9]+$")],
            states={
                ConversationStates.RENEWAL_PLAN_SELECTION: [
                    # Time period selection
                    CallbackQueryHandler(services_handler, pattern="^renewal_period_"),
                    # Plan selection must be checked first to avoid matching ^renew_
                    CallbackQueryHandler(services_handler, pattern="^renewal_plan_[0-9a-z_]+$") ,
                    # account selection (renew_<accountId> only digits)
                    CallbackQueryHandler(services_handler, pattern="^renew_[0-9]+$") ,
                ],
                ConversationStates.RENEWAL_PAYMENT_METHOD: [
                    CallbackQueryHandler(services_handler, pattern="^renewal_payment_"),
                    CallbackQueryHandler(services_handler, pattern="^confirm_services_renewal_")
                ],
                ConversationStates.RENEWAL_RECEIPT_UPLOAD: [
                    MessageHandler(filters.PHOTO | filters.Document.ALL, payment_handler)
                ],
            },
            fallbacks=[
                CallbackQueryHandler(services_handler, pattern="^cancel_renewal"),
                CommandHandler("cancel", services_handler)
            ]
        )
        app.add_handler(renewal_conv_handler)
        
        # Safety handlers for important callbacks that might be blocked by conversation handlers
        app.add_handler(CallbackQueryHandler(services_handler, pattern="^services_"))
        app.add_handler(CallbackQueryHandler(services_handler, pattern="^tutorial_"))
        app.add_handler(CallbackQueryHandler(main_menu_handler, pattern="^main_menu$"))
        app.add_handler(CallbackQueryHandler(purchase_handler, pattern="^purchase_"))
        app.add_handler(CallbackQueryHandler(purchase_handler, pattern="^period_"))
        app.add_handler(CallbackQueryHandler(purchase_handler, pattern="^plan_"))
        app.add_handler(CallbackQueryHandler(payment_handler, pattern="^wallet_"))
        app.add_handler(CallbackQueryHandler(invite_handler, pattern="^invite_"))
        app.add_handler(CallbackQueryHandler(test_account_handler, pattern="^test_"))
        
        # Generic callback handler for unhandled callbacks
        app.add_handler(CallbackQueryHandler(self.handle_unknown_callback))
        
        # Generic message handler for unhandled messages
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_unknown_message))
        
        logger.info("All handlers setup successfully")
    
    async def handle_renewal_receipt_direct(self, update: Update, context):
        """Direct handler for renewal receipt upload"""
        logger.info(f"=== handle_renewal_receipt_direct called ===")
        logger.info(f"Message type: {'photo' if update.message.photo else 'document' if update.message.document else 'other'}")
        logger.info(f"User data: {context.user_data}")
        from bot.handlers.payment import handle_renewal_receipt_upload
        return await handle_renewal_receipt_upload(update, context)
    
    async def set_bot_commands(self):
        """Set bot commands menu"""
        commands = [
            BotCommand("start", "شروع کار با ربات"),
            BotCommand("admin", "پنل مدیریت (فقط ادمین)")
        ]
        
        try:
            # Set commands with timeout
            await asyncio.wait_for(
                self.application.bot.set_my_commands(commands),
                timeout=5.0
            )
            logger.info("Bot commands set successfully")
        except asyncio.TimeoutError:
            logger.warning("Setting bot commands timed out, continuing...")
        except Exception as e:
            logger.error(f"Error setting bot commands: {e}")
            # Continue anyway, commands are not critical
    
    async def handle_unknown_callback(self, update: Update, context):
        """Handle unknown callback queries with better error reporting"""
        query = update.callback_query
        
        # More detailed logging
        logger.error(
            "UNHANDLED CALLBACK - User: %s, Username: %s, Callback: %s, Chat: %s",
            query.from_user.id if query.from_user else "unknown",
            query.from_user.username if query.from_user else "unknown", 
            query.data,
            update.effective_chat.id if update.effective_chat else "unknown"
        )
        
        # Check if it's a known pattern that might be missing
        callback_data = query.data
        suggested_handler = self._suggest_handler_for_callback(callback_data)
        if suggested_handler:
            logger.error(f"SUGGESTION: Callback '{callback_data}' might belong to {suggested_handler}")
        
        await query.answer("این دکمه در حال حاضر کار نمی‌کند. لطفاً دوباره تلاش کنید.")
        
        # Send main menu
        try:
            user = await db_manager.get_or_create_user(
                chat_id=update.effective_chat.id if update.effective_chat else None,
                username=update.effective_user.username if update.effective_user else None
            )
            
            keyboard = get_main_keyboard(user)
            
            # Try to edit message first
            try:
                await query.edit_message_text(
                    "🔄 به منوی اصلی بازگشتید:",
                    reply_markup=keyboard
                )
            except telegram.error.BadRequest as e:
                # If content is unchanged or message is too old, delete and send new
                if "Message is not modified" in str(e) or "message is not modified" in str(e).lower():
                    try:
                        await query.delete_message()
                    except Exception:
                        pass  # Silently ignore if we cannot delete
                    
                    # Send new message
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="🔄 به منوی اصلی بازگشتید:",
                        reply_markup=keyboard
                    )
                else:
                    # For other BadRequest errors, try to send new message
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="🔄 به منوی اصلی بازگشتید:",
                        reply_markup=keyboard
                    )
                    
        except Exception as e:
            logger.error(f"Critical error in handle_unknown_callback: {e}")
            # Final fallback - just answer the callback
            try:
                await query.answer("خطا در پردازش درخواست")
            except Exception:
                pass
    
    def _suggest_handler_for_callback(self, callback_data: str) -> str:
        """Suggest which handler might be missing for this callback"""
        if callback_data.startswith("admin_"):
            return "admin_handler"
        elif callback_data.startswith("services_"):
            return "services_handler"
        elif callback_data.startswith("purchase_") or callback_data.startswith("plan_") or callback_data.startswith("period_"):
            return "purchase_handler"
        elif callback_data.startswith("renewal_") or callback_data.startswith("renew_"):
            return "renewal_handler"
        elif callback_data.startswith("invite_") or callback_data.startswith("gift_"):
            return "invite_handler"
        elif callback_data.startswith("test_"):
            return "test_account_handler"
        elif callback_data.startswith("wallet_") or callback_data.startswith("payment_"):
            return "payment_handler"
        elif callback_data.startswith("main_"):
            return "main_menu_handler"
        else:
            return "unknown - new handler might be needed"
    
    async def handle_unknown_message(self, update: Update, context):
        """Handle unknown messages"""
        # Safely extract identifiers (may be None for some update types)
        chat_id = update.effective_chat.id if update.effective_chat else None
        username = update.effective_user.username if update.effective_user else None

        # If we don't even have a chat_id, we can't reply – just log and exit
        if chat_id is None:
            logger.warning("Received unknown message without chat_id – skipping handling.")
            return

        # Get or create user (username may be None)
        user = await db_manager.get_or_create_user(
            chat_id=chat_id,
            username=username
        )
        
        # Send main menu
        keyboard = get_main_keyboard(user)
        await update.message.reply_text(
            "برای استفاده از ربات، از منوی زیر استفاده کنید:",
            reply_markup=keyboard
        )
    
# Error handler
async def error_handler(update: Update, context):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    # Send error message to user if possible
    if update and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="خطایی رخ داده است. لطفاً دوباره تلاش کنید."
            )
        except Exception as e:
            logger.error(f"Error sending error message: {e}")

# Functions moved to bot.utils to avoid circular imports 