import logging
from telegram import Update
from telegram.ext import ContextTypes
import telegram

from database.database import db_manager
from bot.keyboards import get_main_keyboard

logger = logging.getLogger(__name__)

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu callbacks"""
    try:
        query = update.callback_query
        await query.answer()
        
        # Get user
        user = await db_manager.get_or_create_user(
            chat_id=update.effective_chat.id,
            username=update.effective_user.username
        )
        
        if query.data == "main_menu":
            # Show main menu
            welcome_text = f"""
🏠 منوی اصلی

💰 موجودی کیف پول: {user.wallet_balance:,.0f} تومان
🎁 هدایا: {user.gift_data // (1024**3) if user.gift_data > 0 else 0}GB - {user.gift_days} روز

گزینه مورد نظرت رو انتخاب کن: 😊
            """
            
            keyboard = get_main_keyboard(user)
            
            try:
                await query.edit_message_text(welcome_text, reply_markup=keyboard)
            except telegram.error.BadRequest as e:
                # If content is unchanged, delete and send new message
                if "Message is not modified" in str(e) or "message is not modified" in str(e).lower():
                    try:
                        await query.delete_message()
                    except Exception:
                        pass  # Silently ignore if we cannot delete
                    
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=welcome_text,
                        reply_markup=keyboard
                    )
                else:
                    # For other BadRequest errors, try to send new message
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=welcome_text,
                        reply_markup=keyboard
                    )
            except Exception as e:
                logger.error(f"Error in main_menu_handler: {e}")
                # If message is same, send new message
                try:
                    await query.delete_message()
                except Exception:
                    pass
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=welcome_text,
                    reply_markup=keyboard
                )
        
        elif query.data == "wallet_info":
            # Show wallet information
            wallet_text = f"""
💳 اطلاعات کیف پول

💰 موجودی فعلی: {user.wallet_balance:,.0f} تومان
🎁 حجم هدیه: {user.gift_data // (1024**3) if user.gift_data > 0 else 0} گیگابایت
🎁 روزهای هدیه: {user.gift_days} روز

برای شارژ کیف پول از گزینه "شارژ کیف پول" استفاده کنید.
            """
            
            keyboard = get_main_keyboard(user)
            await query.edit_message_text(wallet_text, reply_markup=keyboard)
        
        else:
            # Unknown main menu action
            await query.answer("عملیات نامعتبر!")
    
    except Exception as e:
        logger.error(f"Error in main_menu_handler: {e}")
        await query.answer("خطایی رخ داده است.")
        
        # Show main menu as fallback
        user = await db_manager.get_or_create_user(
            chat_id=update.effective_chat.id,
            username=update.effective_user.username
        )
        keyboard = get_main_keyboard(user)
        await query.edit_message_text("منوی اصلی:", reply_markup=keyboard) 