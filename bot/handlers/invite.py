import logging
from telegram import Update
from telegram.ext import ContextTypes

from database.database import db_manager
from database.models import Invitation, Account
from services.account_manager import account_manager
from bot.keyboards import (
    get_invite_keyboard,
    get_gift_account_selection_keyboard,
    get_main_keyboard
)
from bot.utils import format_data_size, format_price
from config.settings import settings

logger = logging.getLogger(__name__)

async def invite_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle invite system callbacks"""
    try:
        query = update.callback_query
        await query.answer()
        
        # Get user
        user = await db_manager.get_or_create_user(
            chat_id=update.effective_chat.id,
            username=update.effective_user.username
        )
        
        if query.data == "invite_system":
            await show_invite_system(query, user)
            
        elif query.data == "invite_stats":
            await show_invite_stats(query, user)
            
        elif query.data == "invite_share":
            await show_invite_link(query, user)
            
        elif query.data == "invite_use_gifts":
            await show_gift_account_selection(query, user)
            
        elif query.data.startswith("gift_account_"):
            account_id = int(query.data.split("_")[-1])
            await apply_gifts_to_account(query, user, account_id)
            
        else:
            await query.answer("عملیات نامعتبر!")
    
    except Exception as e:
        logger.error(f"Error in invite_handler: {e}")
        await query.answer("خطایی رخ داده است.")

async def show_invite_system(query, user):
    """Show invite system main menu"""
    try:
        # Get invite statistics
        invite_count = await get_user_invite_count(user.id)
        
        text = f"""
🎁 سیستم دعوت دوستان

👥 تعداد دعوت‌های شما: {invite_count} نفر
🎁 هدایای جمع‌آوری شده:
• حجم: {user.gift_data // (1024**3) if user.gift_data > 0 else 0} گیگابایت
• زمان: {user.gift_days} روز

💡 قوانین سیستم دعوت:
• برای هر دعوت موفق {settings.invite_reward_data // (1024**3)} گیگ + {settings.invite_reward_days} روز دریافت کنید
• هدایا را می‌توانید روی اکانت‌های خود اعمال کنید
• دعوت شده باید از لینک شما ثبت‌نام کند

از گزینه‌های زیر استفاده کنید:
        """
        
        keyboard = get_invite_keyboard(user)
        await query.edit_message_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in show_invite_system: {e}")
        await query.answer("خطایی رخ داد.")

async def show_invite_stats(query, user):
    """Show detailed invite statistics"""
    try:
        # Get invitations made by this user
        db = db_manager.get_session()
        try:
            invitations = db.query(Invitation).filter_by(inviter_id=user.id).all()
            
            total_invites = len(invitations)
            total_rewards_data = total_invites * settings.invite_reward_data
            total_rewards_days = total_invites * settings.invite_reward_days
            
            # Get recent invitations (last 10)
            recent_invites = invitations[-10:] if len(invitations) > 10 else invitations
            
            invite_list = ""
            if recent_invites:
                for inv in recent_invites:
                    invited_user = db.query(db_manager.get_session().query(
                        db_manager.SessionLocal().query(
                            db_manager.User
                        ).filter_by(id=inv.invited_id).first()
                    ))
                    # This is getting complex, let's simplify
                    invite_list += f"• کاربر {inv.invited_id} - {inv.created_at.strftime('%Y/%m/%d')}\n"
            else:
                invite_list = "هنوز دعوتی نداشته‌اید"
            
        finally:
            db.close()
        
        text = f"""
📊 آمار تفصیلی دعوت‌ها

👥 کل دعوت‌ها: {total_invites} نفر
🎁 کل هدایای کسب شده:
• حجم: {total_rewards_data // (1024**3)} گیگابایت
• زمان: {total_rewards_days} روز

💰 ارزش هدایا (تقریبی): {format_price(total_invites * 25000)}

📋 آخرین دعوت‌ها:
{invite_list}

🔗 کد دعوت شما: `{user.invite_code}`

برای دعوت بیشتر از لینک اشتراک استفاده کنید!
        """
        
        keyboard = get_invite_keyboard(user)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_invite_stats: {e}")
        await query.answer("خطایی رخ داد.")

async def show_invite_link(query, user):
    """Show invite link for sharing"""
    try:
        # Get bot info to create invite link
        bot_info = await query.bot.get_me()
        bot_username = bot_info.username
        
        invite_link = f"https://t.me/{bot_username}?start={user.invite_code}"
        
        text = f"""
🔗 لینک دعوت شما

لینک دعوت: `{invite_link}`

📱 نحوه اشتراک:
1. لینک بالا را کپی کنید
2. در شبکه‌های اجتماعی، گروه‌ها یا با دوستان به اشتراک بگذارید
3. وقتی کسی از لینک شما ثبت‌نام کند، هدیه دریافت می‌کنید

🎁 جایزه هر دعوت:
• {settings.invite_reward_data // (1024**3)} گیگابایت حجم اضافی
• {settings.invite_reward_days} روز زمان اضافی

💡 نکته: دعوت شده باید حتماً از لینک شما استفاده کند تا شما جایزه دریافت کنید.

📈 با دعوت 10 نفر، {10 * settings.invite_reward_data // (1024**3)} گیگ هدیه دریافت کنید!
        """
        
        keyboard = get_invite_keyboard(user)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_invite_link: {e}")
        await query.answer("خطایی رخ داد.")

async def show_gift_account_selection(query, user):
    """Show account selection for applying gifts"""
    try:
        if user.gift_data == 0 and user.gift_days == 0:
            await query.answer("شما هدیه‌ای برای استفاده ندارید!")
            return
        
        # Get user's active accounts
        accounts = await account_manager.get_user_accounts(user.id)
        active_accounts = [acc for acc in accounts if acc.is_active]
        
        if not active_accounts:
            text = """
❌ اکانت فعالی ندارید

برای استفاده از هدایا، ابتدا باید حداقل یک سرویس فعال داشته باشید.

از منوی "خرید سرویس" اقدام کنید.
            """
            keyboard = get_invite_keyboard(user)
            await query.edit_message_text(text, reply_markup=keyboard)
            return
        
        text = f"""
🎁 اعمال هدایا

هدایای موجود:
• حجم: {user.gift_data // (1024**3)} گیگابایت
• زمان: {user.gift_days} روز

سرویسی که می‌خواهید هدایا را به آن اضافه کنید انتخاب کنید:

💡 نکته: هدایا به سرویس انتخابی اضافه خواهد شد.
        """
        
        keyboard = get_gift_account_selection_keyboard(active_accounts)
        await query.edit_message_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in show_gift_account_selection: {e}")
        await query.answer("خطایی رخ داد.")

async def apply_gifts_to_account(query, user, account_id):
    """Apply user's gifts to selected account"""
    try:
        if user.gift_data == 0 and user.gift_days == 0:
            await query.answer("شما هدیه‌ای برای استفاده ندارید!")
            return
        
        # Get account
        db = db_manager.get_session()
        try:
            account = db.query(Account).filter_by(
                id=account_id,
                user_id=user.id
            ).first()
            
            if not account:
                await query.answer("اکانت یافت نشد!")
                return
            
            if not account.is_active:
                await query.answer("این اکانت فعال نیست!")
                return
            
            # Apply gifts to account
            success = await account_manager.renew_account(
                account.uuid,
                user.gift_data,
                user.gift_days
            )
            
            if success:
                # Clear user's gifts
                user.gift_data = 0
                user.gift_days = 0
                db.commit()
                
                text = f"""
✅ هدایا با موفقیت اعمال شد!

📧 سرویس: {account.email}

🎁 هدایای اعمال شده:
• حجم اضافی: {user.gift_data // (1024**3) if user.gift_data > 0 else 0} گیگابایت
• زمان اضافی: {user.gift_days} روز

🔄 سرویس شما با حجم و زمان جدید به‌روزرسانی شد.

💡 برای کسب هدایای بیشتر، دوستان خود را دعوت کنید!
                """
                
                logger.info(f"Gifts applied to account {account.uuid} for user {user.chat_id}")
                
            else:
                text = """
❌ خطا در اعمال هدایا

متأسفانه خطایی در اعمال هدایا رخ داد.
لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.
                """
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error applying gifts: {e}")
            text = "خطایی در اعمال هدایا رخ داد."
        finally:
            db.close()
        
        keyboard = get_invite_keyboard(user)
        await query.edit_message_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in apply_gifts_to_account: {e}")
        await query.answer("خطایی رخ داد.")

async def get_user_invite_count(user_id: int) -> int:
    """Get count of successful invitations for a user"""
    try:
        db = db_manager.get_session()
        try:
            count = db.query(Invitation).filter_by(inviter_id=user_id).count()
            return count
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting invite count: {e}")
        return 0

# format_price moved to bot.utils 