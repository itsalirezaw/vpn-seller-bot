import logging
from telegram import Update
from telegram.ext import ContextTypes

from database.database import db_manager
from database.models import User, Invitation
from bot.keyboards import get_main_keyboard
from config.settings import settings

logger = logging.getLogger(__name__)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    try:
        chat_id = update.effective_chat.id
        username = update.effective_user.username
        
        # Check if user came from invite link
        invite_code = None
        if context.args and len(context.args) > 0:
            invite_code = context.args[0]
        
        # Get or create user
        user = await db_manager.get_or_create_user(chat_id, username)
        
        # Handle invite if present
        if invite_code and invite_code != str(chat_id):
            await handle_invite(user, invite_code)
        
        # Welcome message
        welcome_text = f"""
🌟به ربات پرایویت پارتی خوش اومدی🌟

سلام {username or 'عزیز'} 😊

اینجا می‌تونی با خیال راحت سرویس پرسرعت و امن خودت رو داشته باشی ⚡️

گزینه مورد نظرت رو انتخاب کن: 💡
        """
        
        keyboard = get_main_keyboard(user)
        await update.message.reply_text(welcome_text, reply_markup=keyboard)
        
        logger.info(f"User {chat_id} started the bot")
        
    except Exception as e:
        logger.error(f"Error in start_handler: {e}")
        await update.message.reply_text("خطایی رخ داده است. لطفاً دوباره تلاش کنید.")

async def handle_invite(user: User, invite_code: str):
    """Handle invite code"""
    try:
        # Check if invite code is valid (should be a chat_id)
        try:
            inviter_chat_id = int(invite_code)
        except ValueError:
            logger.warning(f"Invalid invite code: {invite_code}")
            return
        
        # Get inviter user
        inviter = await db_manager.get_user_by_chat_id(inviter_chat_id)
        if not inviter:
            logger.warning(f"Inviter not found: {inviter_chat_id}")
            return
        
        # Check if invitation already exists
        db = db_manager.get_session()
        try:
            existing_invite = db.query(Invitation).filter_by(
                inviter_id=inviter.id,
                invited_id=user.id
            ).first()
            
            if existing_invite:
                logger.info(f"Invitation already exists between {inviter.id} and {user.id}")
                return
            
            # Create invitation record
            invitation = Invitation(
                inviter_id=inviter.id,
                invited_id=user.id,
                reward_claimed=False
            )
            db.add(invitation)
            
            # Add reward to inviter
            inviter.gift_data += settings.invite_reward_data
            inviter.gift_days += settings.invite_reward_days
            
            db.commit()
            
            logger.info(f"Invitation created: {inviter.id} invited {user.id}")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error handling invite: {e}")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in handle_invite: {e}") 