import logging
from telegram import Update
from telegram.ext import ContextTypes

from database.database import db_manager
from services.account_manager import account_manager
from bot.keyboards import get_test_account_keyboard, get_main_keyboard
from bot.utils import format_data_size
from config.settings import settings, ADMIN_IDS
from io import BytesIO
import qrcode
from telegram import InputMediaPhoto, InputFile

logger = logging.getLogger(__name__)

async def test_account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle test account callbacks"""
    try:
        query = update.callback_query
        await query.answer()
        
        # Get user
        user = await db_manager.get_or_create_user(
            chat_id=update.effective_chat.id,
            username=update.effective_user.username
        )
        
        if query.data == "test_account":
            await show_test_account_menu(query, user)
            
        elif query.data == "test_create":
            await create_test_account(query, user)
            
        elif query.data == "test_used":
            await show_test_used_message(query, user)
            
        elif query.data == "test_info":
            await show_test_account_info(query, user)
            
        else:
            await query.answer("عملیات نامعتبر!")
    
    except Exception as e:
        logger.error(f"Error in test_account_handler: {e}")
        await query.answer("خطایی رخ داده است.")

async def show_test_account_menu(query, user):
    """Show test account menu"""
    try:
        # Admins can always use test accounts
        is_admin = user.chat_id in ADMIN_IDS
        can_use_test = is_admin or not user.test_used
        
        if can_use_test:
            admin_note = ""
            if is_admin:
                admin_note = "👑 شما به عنوان ادمین می‌توانید بدون محدودیت اکانت تست دریافت کنید.\n\n"
            
            text = f"""
🧪 اکانت تست رایگان

{admin_note}شما می‌توانید یک اکانت تست رایگان دریافت کنید! 🎉

📊 مشخصات اکانت تست:
• حجم: {format_data_size(settings.test_account_data_limit)}
• مدت: {settings.test_account_expire_hours} ساعت
• سرور: بهترین سرور موجود
• تمامی پروتکل‌ها

🎯 هدف: آزمایش کیفیت سرویس قبل از خرید

⚠️ نکات مهم:
• هر کاربر فقط یک بار می‌تواند استفاده کند
• پس از اتمام زمان، حذف خواهد شد
• امکان تمدید وجود ندارد

آیا می‌خواهید اکانت تست دریافت کنید؟
            """
        else:
            text = f"""
🧪 اکانت تست

❌ شما قبلاً از اکانت تست استفاده کرده‌اید

📊 مشخصات اکانت تست:
• حجم: {format_data_size(settings.test_account_data_limit)}
• مدت: {settings.test_account_expire_hours} ساعت

💡 برای استفاده مجدد، می‌توانید از سرویس‌های پولی استفاده کنید.

از منوی "خرید سرویس" اقدام کنید.
            """
        
        keyboard = get_test_account_keyboard(can_use_test)
        await query.edit_message_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in show_test_account_menu: {e}")
        await query.answer("خطایی رخ داد.")

async def create_test_account(query, user):
    """Create test account for user"""
    try:
        # Initialize variables to avoid UnboundLocalError when configs are empty
        configs: dict = {}
        first_config: str | None = None

        # Check if user can use test account (admins can always use)
        is_admin = user.chat_id in ADMIN_IDS
        if not is_admin and user.test_used:
            await query.answer("شما قبلاً از اکانت تست استفاده کرده‌اید!")
            return
        # اگر ادمین است و قبلاً استفاده کرده، مقدار را ریست می‌کنیم که اجازه ساخت بدهد
        if is_admin and user.test_used:
            user.test_used = False
            await db_manager.update_user(user)
        
        # Create test account
        test_account = await account_manager.create_test_account(user.id)
        
        if test_account:
            # Generate configurations using test template
            configs = await account_manager.generate_test_config_urls(test_account.uuid)

            config_text = ""
            if configs:
                # Get first available config
                first_server = list(configs.keys())[0]
                first_protocol = list(configs[first_server].keys())[0]
                first_config = configs[first_server][first_protocol]

                config_text = f"""

🔧 کانفیگ سرویس (🇩🇪 Germany VMess TCP):
`{first_config}`

💡 برای مشاهده همه کانفیگ‌ها از منوی "مشاهده سرویس‌ها" استفاده کنید.
                """
            
            admin_note = ""
            if is_admin:
                admin_note = "👑 شما به عنوان ادمین می‌توانید نامحدود اکانت تست دریافت کنید.\n\n"
            
            text = f"""
✅ اکانت تست با موفقیت ایجاد شد! 🎉

{admin_note}📧 ایمیل سرویس: `{test_account.email}`
🆔 UUID: `{test_account.uuid}`

📊 مشخصات:
• حجم: {format_data_size(settings.test_account_data_limit)}
• مدت: {settings.test_account_expire_hours} ساعت
• انقضا: {test_account.expire_time.strftime('%Y/%m/%d %H:%M')}

{config_text}

📱 مراحل استفاده:
1. کانفیگ بالا را کپی کنید
2. در برنامه VPN paste کنید
3. اتصال برقرار کنید

📚 برای آموزش نصب، از منوی "مشاهده سرویس‌ها" > "آموزش" استفاده کنید.

⚠️ نکته: این اکانت پس از {settings.test_account_expire_hours} ساعت حذف خواهد شد.

🛒 برای خرید سرویس کامل، از منوی "خرید سرویس" استفاده کنید.
            """
            
            logger.info(f"Test account created for user {user.chat_id}: {test_account.uuid}")
            
            # فقط برای کاربران عادی مقدار test_used را True کن
            if not is_admin:
                user.test_used = True
                await db_manager.update_user(user)
            
            # Generate QR code only if we have a configuration string
            if first_config:
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(first_config)
                qr.make(fit=True)

                # Create an image from the QR Code instance
                img = qr.make_image(fill_color="black", back_color="white")

                # Convert the image to a file-like object
                img_io = BytesIO()
                img.save(img_io, format="PNG")
                img_io.seek(0)

                # After sending text, send QR code image separately
                # We'll send after editing the message below.
                qr_img_io = img_io
            
        else:
            text = """
❌ خطا در ایجاد اکانت تست

متأسفانه خطایی در ایجاد اکانت تست رخ داد.
ممکن است تمام سرورها در دسترس نباشند.

لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.
            """
        
        # Build a single caption with QR and details
        if configs and first_config:
            qr_img_io.seek(0)

            caption = f"""
🎉 *اکانت تست فعال شد!*

`{first_config}`

📧 ایمیل: `{test_account.email}`
🆔 UUID: `{test_account.uuid}`
📊 حجم: {format_data_size(settings.test_account_data_limit)} | مدت: {settings.test_account_expire_hours} ساعت
{admin_note}🔳 برای اتصال، QR را اسکن کنید یا کانفیگ را کپی نمایید.

⚠️ این اکانت پس از {settings.test_account_expire_hours} ساعت حذف خواهد شد.
"""

            keyboard = get_main_keyboard(user)

            # Ensure the BytesIO object has a name attribute for PTB to recognise it as a file
            if not hasattr(qr_img_io, "name"):
                qr_img_io.name = "qr.png"

            # Send a *new* photo message with caption instead of editing the existing text message
            await query.message.reply_photo(
                photo=InputFile(qr_img_io),
                caption=caption,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
        else:
            keyboard = get_main_keyboard(user)
            await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in create_test_account: {e}")
        await query.answer("خطایی در ایجاد اکانت تست رخ داد.")

async def show_test_used_message(query, user):
    """Show message for users who already used test account"""
    try:
        text = """
❌ اکانت تست قبلاً استفاده شده

شما قبلاً از اکانت تست استفاده کرده‌اید.

💡 گزینه‌های موجود:
• خرید سرویس از منوی "خرید سرویس"
• استفاده از سیستم دعوت
• شارژ کیف پول

از منوی "خرید سرویس" برای مشاهده پلن‌ها استفاده کنید.
        """
        
        keyboard = get_main_keyboard(user)
        await query.edit_message_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in show_test_used_message: {e}")
        await query.answer("خطایی رخ داد.")

async def show_test_account_info(query, user):
    """Show detailed information about test accounts"""
    try:
        text = f"""
ℹ️ اطلاعات کامل اکانت تست

🎯 **هدف:**
اکانت تست برای آزمایش کیفیت سرویس قبل از خرید طراحی شده است.

📊 **مشخصات:**
• حجم: {format_data_size(settings.test_account_data_limit)}
• مدت: {settings.test_account_expire_hours} ساعت
• تعداد سرور: 1 سرور (بهترین موجود)
• پروتکل: تمامی پروتکل‌های موجود
• سرعت: بدون محدودیت

⚠️ **محدودیت‌ها:**
• هر کاربر فقط یک بار
• غیرقابل تمدید
• حذف خودکار پس از انقضا
• عدم امکان بازیابی

🎁 **مزایا:**
• رایگان و بدون نیاز به پرداخت
• دسترسی فوری
• تست کامل امکانات
• بررسی سرعت و کیفیت

🚀 **نحوه استفاده:**
1. دکمه "دریافت اکانت تست" را بزنید
2. کانفیگ دریافتی را در برنامه VPN وارد کنید
3. اتصال برقرار کنید و تست کنید
4. در صورت رضایت، سرویس کامل خریداری کنید

💡 **توصیه:**
اگر از کیفیت سرویس راضی بودید، از پلن‌های کامل ما استفاده کنید که شامل:
• حجم‌های بالاتر
• مدت زمان طولانی‌تر
• چندین سرور همزمان
• پشتیبانی تخصصی

📞 **پشتیبانی:**
در صورت مشکل در استفاده از اکانت تست، با پشتیبانی تماس بگیرید.
        """
        
        keyboard = get_test_account_keyboard(not user.test_used)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_test_account_info: {e}")
        await query.answer("خطایی رخ داد.") 