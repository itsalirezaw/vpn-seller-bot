import logging
import qrcode
from io import BytesIO
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import telegram

from database.database import db_manager
from database.models import Account
from services.account_manager import account_manager
from telegram.ext import ConversationHandler

from bot.keyboards import (
    get_services_keyboard, 
    get_account_detail_keyboard,
    get_config_display_keyboard,
    get_renewal_plans_keyboard,
    get_renewal_time_period_keyboard,
    get_renewal_data_plans_keyboard,
    get_main_keyboard,
    get_renew_accounts_keyboard,
)
from bot.states import ConversationStates
from bot.utils import format_data_size, format_price, format_usage_size
from config.settings import SERVICE_PLANS
from config.payment_utils import format_payment_info

logger = logging.getLogger(__name__)

async def services_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle services-related callbacks"""
    try:
        query = update.callback_query
        await query.answer()
        
        # Get user
        user = await db_manager.get_or_create_user(
            chat_id=update.effective_chat.id,
            username=update.effective_user.username
        )
        
        if query.data == "services_list":
            await show_services_list(query, user)
            
        elif query.data.startswith("services_view_"):
            account_id = int(query.data.split("_")[-1])
            await show_account_details(query, account_id)
            
        elif query.data.startswith("services_config_"):
            account_id = int(query.data.split("_")[-1])
            await show_account_configs(query, account_id)
            
        elif query.data.startswith("services_qr_"):
            account_id = int(query.data.split("_")[-1])
            await show_subscription_qr(query, account_id)
            
        elif query.data.startswith("services_subscription_"):
            account_id = int(query.data.split("_")[-1])
            await show_subscription_link(query, account_id)

        elif query.data.startswith("services_delete_"):
            account_id = int(query.data.split("_")[-1])
            await confirm_delete_service(query, account_id)

        elif query.data.startswith("confirm_delete_"):
            account_id = int(query.data.split("_")[-1])
            await delete_service(query, account_id, user)
            
        elif query.data.startswith("services_tutorial_"):
            account_id = int(query.data.split("_")[-1])
            await show_tutorial_menu(query, account_id)

        elif query.data.startswith("tutorial_android_"):
            account_id = int(query.data.split("_")[-1])
            await send_android_tutorial(query, account_id)

        elif query.data.startswith("tutorial_ios_"):
            account_id = int(query.data.split("_")[-1])
            await show_ios_apps_menu(query, account_id)



        elif query.data.startswith("tutorial_ios_streisand_"):
            account_id = int(query.data.split("_")[-1])
            await send_ios_streisand_tutorial(query, account_id)

        elif query.data.startswith("tutorial_ios_v2box_"):
            account_id = int(query.data.split("_")[-1])
            await send_ios_v2box_tutorial(query, account_id)
            
        elif query.data == "renew_service":
            # User chose renewal from main menu – show list of user accounts
            await show_renew_services_list(query, user)
            return ConversationStates.RENEWAL_PLAN_SELECTION
 
        # ---------------- Renewal detailed callbacks (match BEFORE generic "renew_*") ----------------
            
        elif query.data.startswith("renewal_plan_"):
            parts = query.data.split("_")
            account_id = int(parts[2])
            plan_id = "_".join(parts[3:])  # plan id may contain underscores
            await show_renewal_order_summary(query, account_id, plan_id)
            return ConversationStates.RENEWAL_PAYMENT_METHOD
            
        elif query.data.startswith("renewal_payment_"):
            parts = query.data.split("_")
            account_id = int(parts[2])
            plan_id = "_".join(parts[3:-1])
            payment_method = parts[-1]
            await handle_renewal_payment(query, context, account_id, plan_id, payment_method)
            # If direct payment we expect receipt – move to RENEWAL_RECEIPT_UPLOAD else end
            if payment_method == "direct":
                context.user_data['state'] = ConversationStates.RENEWAL_RECEIPT_UPLOAD
                logger.info(f"=== MOVING TO RENEWAL_RECEIPT_UPLOAD STATE ===")
                logger.info(f"User data after setting state: {context.user_data}")
                return ConversationStates.RENEWAL_RECEIPT_UPLOAD
            return ConversationHandler.END

        elif query.data.startswith("confirm_services_renewal_"):
            # confirm_services_renewal_<account_id>_<plan_id>
            parts = query.data.split("_")
            if len(parts) >= 5:
                account_id = int(parts[3])
                plan_id = "_".join(parts[4:])  # plan_id may contain underscores
                await handle_services_wallet_confirmation(query, context, account_id, plan_id)
            return

        elif query.data == "cancel_renewal":
            # Import the cancel function from payment handler
            from .payment import cancel_payment_process
            await cancel_payment_process(update, context, "renewal")
            return ConversationHandler.END
            
        elif query.data.startswith("renew_"):
            # renew_<account_id>
            try:
                account_id = int(query.data.split("_")[-1])
            except ValueError:
                await query.answer("اکانت نامعتبر!")
                return

            # Store account_id in context and show time period selection
            context.user_data['renewal_account_id'] = account_id
            await show_renewal_time_periods(query, account_id)
            return ConversationStates.RENEWAL_PLAN_SELECTION
            
        elif query.data.startswith("renewal_period_"):
            # renewal_period_<period>
            parts = query.data.split("_")
            period = parts[2]
            account_id = context.user_data.get('renewal_account_id')
            if not account_id:
                await query.answer("خطا در پردازش!")
                return
            await show_renewal_data_plans_for_period(query, account_id, period)
            return ConversationStates.RENEWAL_PLAN_SELECTION
            
        else:
            await query.answer("عملیات نامعتبر!")
    
    except Exception as e:
        logger.error(f"Error in services_handler: {e}")
        await query.answer("خطایی رخ داده است.")

async def show_services_list(query, user):
    """Show user's services list"""
    try:
        # Get user accounts
        accounts = await account_manager.get_user_accounts(user.id)
        
        if not accounts:
            text = """
📋 سرویس‌های شما

شما هنوز هیچ سرویسی ندارید.
برای خرید سرویس جدید از گزینه "خرید سرویس" استفاده کنید.
            """
            keyboard = get_main_keyboard(user)
        else:
            text = f"""
📋 سرویس‌های شما

تعداد: {len(accounts)}

سرویس مورد نظرت رو انتخاب کن: 😊
            """
            keyboard = get_services_keyboard(accounts)
        
        await query.edit_message_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in show_services_list: {e}")
        await query.answer("خطایی در نمایش سرویس‌ها رخ داد.")

async def show_account_details(query, account_id):
    """Show detailed account information"""
    try:
        # Get account (eager-loaded)
        account = await account_manager.get_account_by_id(account_id)
          
        if not account:
            await query.answer("اکانت یافت نشد!")
            return
        
        # Sync usage data
        await account_manager.sync_account_usage(account.uuid)
        
        # Refresh account data from database after sync to ensure we have latest info
        account = await account_manager.get_account_by_id(account_id)
        
        # Also refresh user data to get updated wallet balance
        user = await db_manager.get_or_create_user(
            chat_id=query.from_user.id,
            username=query.from_user.username,
        )
        
        # Get account limits
        limits = await account_manager.check_account_limits(account.uuid)

        # Identify service plan (best-effort) - now based on remaining time
        plan_name = "نامشخص"
        remaining_days = (account.expire_time - datetime.utcnow()).days
        
        # Try to match based on data limit and current remaining time
        for pid, pinfo in SERVICE_PLANS.items():
            if pinfo.get('data_limit') == account.total_data_limit:
                # For recently renewed accounts, check if remaining days is close to plan days
                plan_days = pinfo.get('expire_days', 0)
                if abs(remaining_days - plan_days) <= 2:  # Allow 2 day tolerance for timing differences
                    plan_name = pinfo['name']
                    break
        
        # If no match found, fall back to showing actual remaining time
        if plan_name == "نامشخص":
            plan_name = f"سفارشی ({remaining_days} روز باقی‌مانده)"

        # Generate subscription link
        sub_link = await account_manager.generate_subscription_link(account.uuid)
        
        # Format status
        status_emoji = "🟢" if account.is_active else "🔴"
        if account.is_expired:
            status_emoji = "⏰"
        elif limits.get('data_limit_exceeded', False):
            status_emoji = "📵"
        
        status_text = "فعال" if account.is_active else "غیرفعال"
        if account.is_expired:
            status_text = "منقضی شده"
        elif limits.get('data_limit_exceeded', False):
            status_text = "حجم تمام شده"
        
        # Get server accounts
        server_accounts = await account_manager.get_account_servers(account.id)
        server_list = "\n".join([f"• {server.name}" for server, _ in server_accounts])
        
        text = f"""
📊 جزئیات سرویس

🔗 لینک اشتراک: `{sub_link or 'در دسترس نیست'}`

{status_emoji} وضعیت: {status_text}

📊 حجم:
• کل: {format_data_size(account.total_data_limit)}
• مصرف: {format_usage_size(limits.get('total_usage', 0))}
• باقی: {format_data_size(limits.get('remaining_data', 0))}

⏰ زمان:
• انقضا: {account.expire_time.strftime('%Y/%m/%d')}
• باقی: {(account.expire_time - datetime.utcnow()).days} روز

🖥️ سرورها:
{server_list}
        """
        
        keyboard = get_account_detail_keyboard(account)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_account_details: {e}")
        await query.answer("خطایی در نمایش جزئیات رخ داد.")

async def show_account_configs(query, account_id):
    """Show account configurations"""
    try:
        # Get account
        account = await account_manager.get_account_by_id(account_id)
        
        if not account:
            await query.answer("اکانت یافت نشد!")
            return
        
        # Generate configurations
        configs = await account_manager.generate_config_urls(account.uuid)
        
        if not configs:
            await query.answer("خطا در تولید کانفیگ!")
            return
        
        config_text = "📄 کانفیگ‌های سرویس\n\n"
        
        for server_name, server_configs in configs.items():
            # Use HTML parsing instead of Markdown to avoid conflicts
            # Escape HTML characters in server name
            escaped_server_name = server_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            config_text += f"🖥️ <b>{escaped_server_name}</b>\n\n"
            
            for protocol, config_url in server_configs.items():
                # Escape HTML characters in protocol name
                escaped_protocol = protocol.upper().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                config_text += f"<b>{escaped_protocol}:</b>\n"
                # Escape HTML characters in config URL
                escaped_config_url = config_url.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                config_text += f"<code>{escaped_config_url}</code>\n\n"
        
        config_text += "برای کپی کردن، روی هر کانفیگ کلیک کن 😊"
        
        keyboard = get_config_display_keyboard(account_id)
        await query.edit_message_text(config_text, reply_markup=keyboard, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Error in show_account_configs: {e}")
        await query.answer("خطایی در نمایش کانفیگ رخ داد.")

async def show_account_qr(query, context, account_id):
    """Show QR codes for account configurations"""
    try:
        # Get account
        account = await account_manager.get_account_by_id(account_id)
        
        if not account:
            await query.answer("اکانت یافت نشد!")
            return
        
        # Generate configurations
        configs = await account_manager.generate_config_urls(account.uuid)
        
        if not configs:
            await query.answer("خطا در تولید کانفیگ!")
            return
        
        # Generate QR codes for first server and first protocol
        first_server = list(configs.keys())[0]
        first_protocol = list(configs[first_server].keys())[0]
        config_url = configs[first_server][first_protocol]
        
        # Create QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(config_url)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to bytes
        bio = BytesIO()
        img.save(bio, 'PNG')
        bio.seek(0)
        
        caption = f"""
📱 QR کد سرویس

🖥️ سرور: {first_server}
🔧 پروتکل: {first_protocol.upper()}

برای اتصال، این QR کد را در برنامه VPN اسکن کنید.
        """
        
        # Send QR code photo
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=bio,
            caption=caption
        )
        
        await query.answer("QR کد ارسال شد!")
        
    except Exception as e:
        logger.error(f"Error in show_account_qr: {e}")
        await query.answer("خطایی در تولید QR کد رخ داد.")

async def show_subscription_link(query, account_id):
    """Show subscription link"""
    try:
        # Get account
        account = await account_manager.get_account_by_id(account_id)
        
        if not account:
            await query.answer("اکانت یافت نشد!")
            return
        
        # Generate subscription link
        sub_link = await account_manager.generate_subscription_link(account.uuid)
        
        if not sub_link:
            await query.answer("خطا در تولید لینک اشتراک!")
            return
        
        text = f"""
🔗 لینک اشتراک

برای اضافه کردن همه کانفیگ‌ها به برنامه VPN، از لینک زیر استفاده کنید:

`{sub_link}`

📝 نحوه استفاده:
1. لینک بالا را کپی کنید
2. در برنامه VPN گزینه "Import from URL" را انتخاب کنید
3. لینک را paste کنید
4. همه کانفیگ‌ها اضافه خواهند شد

💡 با استفاده از لینک اشتراک، کانفیگ‌های جدید خودکار اضافه می‌شوند.
        """
        
        keyboard = get_account_detail_keyboard(account)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_subscription_link: {e}")
        await query.answer("خطایی در تولید لینک اشتراک رخ داد.")

async def show_tutorial(query, account_id):
    """Show setup tutorial"""
    try:
        text = """
📚 آموزش نصب و تنظیم

🔧 **برنامه‌های پیشنهادی:**

📱 **Android:**
• V2rayNG
• Clash for Android
• SagerNet

🍎 **iOS:**
• FoxyProxy
• Shadowrocket
• QuantumultX

💻 **Windows:**
• V2rayN
• Clash for Windows
• WinXray

🖥️ **macOS:**
• V2rayU
• ClashX
• Qv2ray

🐧 **Linux:**
• V2raya
• Clash
• Qv2ray

📖 **مراحل نصب:**
1. برنامه مورد نظر را نصب کنید
2. کانفیگ را از بخش "مشاهده کانفیگ" کپی کنید
3. در برنامه گزینه "Add Config" را انتخاب کنید
4. کانفیگ را paste کنید
5. روی Connect کلیک کنید

💡 برای راهنمای تصویری هر برنامه، با پشتیبانی تماس بگیرید.
        """
        
        keyboard = get_account_detail_keyboard(query.data.split("_")[-1])
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_tutorial: {e}")
        await query.answer("خطایی در نمایش آموزش رخ داد.")

async def show_renewal_time_periods(query, account_id):
    """Show time period selection for renewal"""
    try:
        # Get account
        account = await account_manager.get_account_by_id(account_id)
        
        if not account:
            await query.answer("اکانت یافت نشد!")
            return
        
        text = f"""
🔄 تمدید سرویس

📧 سرویس: {account.email}

⏳ زمان اشتراک مورد نظرت رو برای تمدید انتخاب کن: 🤓

💡 نکته: حجم و زمان انتخاب شده به سرویس فعلی شما اضافه خواهد شد.
        """
        
        keyboard = get_renewal_time_period_keyboard(account_id)
        await query.edit_message_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in show_renewal_time_periods: {e}")
        await query.answer("خطایی رخ داد.")

async def show_renewal_data_plans_for_period(query, account_id, period):
    """Show data plans for selected time period in renewal"""
    try:
        # Get account
        account = await account_manager.get_account_by_id(account_id)
        
        if not account:
            await query.answer("اکانت یافت نشد!")
            return
        
        period_names = {
            "1m": "یک ماهه",
            "3m": "سه ماهه", 
            "6m": "شش ماهه"
        }
        
        text = f"""
🔄 تمدید سرویس

📧 سرویس: {account.email}

📊 انتخاب حجم برای پلن {period_names.get(period, "")}

یکی از پلن‌ها رو انتخاب کن و برو برای پرداختش 🤲
        """
        
        keyboard = get_renewal_data_plans_keyboard(account_id, period)
        await query.edit_message_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in show_renewal_data_plans_for_period: {e}")
        await query.answer("خطایی رخ داد.")

async def show_renewal_options(query, account_id):
    """Legacy function - redirects to time period selection"""
    await show_renewal_time_periods(query, account_id)

async def show_renewal_order_summary(query, account_id, plan_id):
    """Show detailed renewal order summary before payment"""
    try:
        if plan_id not in SERVICE_PLANS:
            await query.answer("پلن نامعتبر!")
            return
        
        plan = SERVICE_PLANS[plan_id]
        
        # Get account and user
        account = await account_manager.get_account_by_id(account_id)
        user = await db_manager.get_or_create_user(
            chat_id=query.message.chat_id,
            username=query.from_user.username
        )
        
        if not account:
            await query.answer("اکانت یافت نشد!")
            return
        
        data_gb = plan['data_limit'] // (1024**3)
        
        text = f"""
📋 پیش فاکتور تمدید:
    
〽️ نام سرویس: {plan['period_name']} حجم {data_gb} گیگ
⏳ مدت اعتبار: {plan['expire_days']} روز
📊 حجم اکانت: {data_gb} گیگ

🌍 ویژگی‌ها:
- بهترین لوکیشن های اروپا
- پرسرعت روی تمامی اپراتورها  
- بدون محدودیت کاربر
- پشتیبانی 24 ساعته

💎 قیمت: {format_price(plan['price'])}

💰 موجودی کیف پول شما: {format_price(user.wallet_balance)}

💡 نکته: حجم و زمان انتخاب شده به سرویس فعلی شما اضافه خواهد شد.

سفارش تمدید شما آماده پرداخت است 🤲

روش پرداخت رو انتخاب کن: 😊
        """
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        kb_rows = []
        kb_rows.append([InlineKeyboardButton("💳 پرداخت از کیف پول", callback_data=f"renewal_payment_{account_id}_{plan_id}_wallet")])
        kb_rows.append([InlineKeyboardButton("💰 پرداخت مستقیم", callback_data=f"renewal_payment_{account_id}_{plan_id}_direct")])
        kb_rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"renew_{account_id}")])
        
        keyboard = InlineKeyboardMarkup(kb_rows)
        await query.edit_message_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in show_renewal_order_summary: {e}")
        await query.answer("خطایی رخ داد.")

async def handle_renewal_plan_selection(query, account_id, plan_id):
    """Legacy function - redirects to order summary"""
    await show_renewal_order_summary(query, account_id, plan_id)

async def handle_renewal_payment(query, context, account_id, plan_id, payment_method):
    """Handle renewal payment"""
    try:
        if plan_id not in SERVICE_PLANS:
            await query.answer("پلن نامعتبر!")
            return
        
        plan = SERVICE_PLANS[plan_id]
        
        # Get user and account
        user = await db_manager.get_or_create_user(
            chat_id=query.message.chat_id,
            username=query.from_user.username
        )
        
        account = await account_manager.get_account_by_id(account_id)
        
        if not account:
            await query.answer("اکانت یافت نشد!")
            return
        
        if payment_method == "wallet":
            # Pay from wallet
            if user.wallet_balance >= plan['price']:
                # Show confirmation before processing payment
                text = f"""
💳 تایید تمدید از کیف پول

📦 پلن: {plan['name']}
🔄 حجم اضافه: {'نامحدود' if plan['data_limit'] == 0 else f"{plan['data_limit'] // (1024**3)} گیگابایت"}
📅 زمان اضافه: {plan['expire_days']} روز
💰 مبلغ: {format_price(plan['price'])}

💳 موجودی فعلی: {format_price(user.wallet_balance)}
💳 موجودی پس از تمدید: {format_price(user.wallet_balance - plan['price'])}

آیا تایید می‌کنید؟
                """
                
                # Store info for confirmation (services.py specific data)
                context.user_data['renewal_services_account_id'] = account_id
                context.user_data['renewal_services_plan_id'] = plan_id
                
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ تایید و تمدید", callback_data=f"confirm_services_renewal_{account_id}_{plan_id}")],
                    [InlineKeyboardButton("🔙 انصراف", callback_data=f"services_view_{account_id}")]
                ])
                
                await query.edit_message_text(text, reply_markup=keyboard)
                return  # Stay in same function, don't continue
                
            else:
                text = "❌ موجودی کیف پول کافی نیست!"
                keyboard = get_account_detail_keyboard(account)
        
        else:  # direct payment method
            # Create order for direct payment
            order = await db_manager.create_order(
                user_id=user.id,
                order_type="renewal",
                amount=plan['price'],
                plan_id=plan_id,
                account_id=account_id
            )
            
            if order:
                from config.settings import settings
                data_gb = plan['data_limit'] // (1024**3)
                text = f"""
💰 پرداخت کارت به کارت

📦 پلن: {plan['period_name']} - {data_gb} گیگ
💰 مبلغ: {format_price(plan['price'])}

💳 اطلاعات پرداخت:
{format_payment_info()}

📋 مراحل:
1️⃣ مبلغ رو به شماره کارت واریز کن
2️⃣ عکس رسید رو ارسال کن
3️⃣ سرویس تمدید می‌شه

منتظر رسیدت هستیم 😊
                """
                
                # Store order info in context
                context.user_data['pending_renewal_order'] = order.id
                context.user_data['state'] = ConversationStates.RENEWAL_RECEIPT_UPLOAD
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو پرداخت", callback_data="cancel_renewal")]])
            else:
                text = "❌ خطا در ایجاد سفارش!"
                keyboard = get_account_detail_keyboard(account)
            
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in handle_renewal_payment: {e}")
        await query.answer("خطایی رخ داد.") 

async def handle_services_wallet_confirmation(query, context, account_id, plan_id):
    """Handle wallet payment confirmation from services.py"""
    try:
        if plan_id not in SERVICE_PLANS:
            await query.answer("پلن نامعتبر!")
            return
        
        plan = SERVICE_PLANS[plan_id]
        
        # Get user and account
        user = await db_manager.get_or_create_user(
            chat_id=query.message.chat_id,
            username=query.from_user.username
        )
        
        account = await account_manager.get_account_by_id(account_id)
        
        if not account:
            await query.answer("اکانت یافت نشد!")
            return
        
        # Check wallet balance again
        if user.wallet_balance < plan['price']:
            await query.answer("موجودی کافی نیست")
            return
        
        logger.info(f"=== WALLET RENEWAL START (services.py confirmed) ===")
        logger.info(f"User: {user.id}, Account: {account_id}, Plan: {plan_id}")
        logger.info(f"Account UUID: {account.uuid}")
        logger.info(f"Plan details: {plan}")
        
        # Deduct from wallet
        await db_manager.update_user_wallet(user.id, -plan['price'])
        logger.info(f"Wallet updated - deducted {plan['price']}")
        
        # Renew account
        success = await account_manager.renew_account(
            account.uuid,
            plan['data_limit'],
            plan['expire_days']
        )
        logger.info(f"Renewal result: {success}")
        logger.info(f"=== WALLET RENEWAL END (services.py confirmed) ===")
        
        if success:
            text = f"""
✅ تمدید موفق!

سرویس شما با موفقیت تمدید شد! 🎉

📦 پلن: {plan['name']}
💰 مبلغ پرداختی: {format_price(plan['price'])}
💳 پرداخت از: کیف پول

🔄 حجم اضافه شده: {'نامحدود' if plan['data_limit'] == 0 else f"{plan['data_limit'] // (1024**3)} گیگابایت"}
📅 زمان اضافه شده: {plan['expire_days']} روز

💰 موجودی باقی‌مانده: {format_price(user.wallet_balance - plan['price'])}

🔄 جزئیات سرویس به‌روزرسانی شد. برای مشاهده تغییرات روی "🔄 به‌روزرسانی" کلیک کنید.
            """
        else:
            # Refund on failure
            await db_manager.update_user_wallet(user.id, plan['price'])
            text = "❌ خطا در تمدید سرویس. مبلغ به کیف پول شما بازگردانده شد."
        
        keyboard = get_account_detail_keyboard(account)
        await query.edit_message_text(text, reply_markup=keyboard)
        
        # Clear context
        context.user_data.pop('renewal_services_account_id', None)
        context.user_data.pop('renewal_services_plan_id', None)
        
    except Exception as e:
        logger.error(f"Error in handle_services_wallet_confirmation: {e}")
        await query.answer("خطایی رخ داد.")

async def show_subscription_qr(query, account_id):
    """Show QR code for subscription link"""
    try:
        # Get account
        account = await account_manager.get_account_by_id(account_id)
        
        if not account:
            await query.answer("اکانت یافت نشد!")
            return
        
        # Generate subscription link
        sub_link = await account_manager.generate_subscription_link(account.uuid)
        
        if not sub_link:
            await query.answer("خطا در تولید لینک اشتراک!")
            return
        
        # Create QR code
        import qrcode
        from io import BytesIO
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(sub_link)
        qr.make(fit=True)
        
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to bytes
        bio = BytesIO()
        qr_img.save(bio, 'PNG')
        bio.seek(0)
        
        text = f"""
📱 QR کد لینک اشتراک

🔗 لینک: `{sub_link}`

📋 دستورالعمل:
• این QR کد را با دوربین برنامه V2rayNG یا V2Box اسکن کنید
• یا لینک بالا را کپی کرده و در برنامه import کنید

💡 برای آموزش کامل روی دکمه "آموزش" کلیک کنید.
        """
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📚 آموزش", callback_data=f"services_tutorial_{account_id}")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data=f"services_view_{account_id}")]
        ])
        
        # Send QR code as photo
        await query.message.reply_photo(
            photo=bio,
            caption=text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        # Edit original message to show that QR was sent
        await query.edit_message_text(
            "📱 QR کد لینک اشتراک ارسال شد!\n\nبرای بازگشت به جزئیات سرویس، دکمه زیر را فشار دهید.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت به جزئیات", callback_data=f"services_view_{account_id}")]
            ])
        )
        
    except Exception as e:
        logger.error(f"Error in show_subscription_qr: {e}")
        await query.answer("خطایی در نمایش QR کد رخ داد.")

# ================== Tutorial System ==================

async def show_tutorial_menu(query, account_id):
    """Show tutorial menu with Android/iOS options"""
    try:
        text = """
📚 آموزش استفاده از سرویس

لطفاً سیستم عامل خود را انتخاب کنید:
        """
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🤖 اندروید", callback_data=f"tutorial_android_{account_id}")],
            [InlineKeyboardButton("🍎 iOS", callback_data=f"tutorial_ios_{account_id}")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data=f"services_view_{account_id}")]
        ])
        
        await query.edit_message_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in show_tutorial_menu: {e}")
        await query.answer("خطایی رخ داد.")

async def send_android_tutorial(query, account_id):
    """Send Android V2rayNG tutorial video"""
    try:
        text = """
🤖 آموزش اندروید - V2rayNG

در حال ارسال ویدیو آموزشی...
        """
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت به آموزش", callback_data=f"services_tutorial_{account_id}")]
        ])
        
        await query.edit_message_text(text, reply_markup=keyboard)
        
        # TODO: Replace with actual video file_id or URL
        video_url = "https://example.com/android_v2rayng_tutorial.mp4"  # Replace with actual video
        
        try:
            # Send tutorial video
            await query.message.reply_video(
                video=video_url,
                caption="🤖 آموزش نصب و راه‌اندازی V2rayNG روی اندروید",
                reply_markup=keyboard
            )
        except Exception:
            # If video fails, send text instructions
            instructions = """
🤖 آموزش V2rayNG برای اندروید:

1️⃣ نصب برنامه V2rayNG از Google Play Store
2️⃣ باز کردن برنامه و انتخاب گزینه "+"
3️⃣ انتخاب "Import from Clipboard" یا "Scan QR code"
4️⃣ کپی کردن لینک اشتراک یا اسکن QR کد
5️⃣ انتخاب سرور و اتصال

🔗 لینک دانلود: https://play.google.com/store/apps/details?id=com.v2ray.ang
            """
            
            await query.message.reply_text(instructions, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in send_android_tutorial: {e}")
        await query.answer("خطایی در ارسال آموزش رخ داد.")

async def show_ios_apps_menu(query, account_id):
    """Show iOS apps menu (Streisand, V2Box)"""
    try:
        text = """
🍎 آموزش iOS

لطفاً برنامه مورد نظر خود را انتخاب کنید:
        """
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Streisand", callback_data=f"tutorial_ios_streisand_{account_id}")],
            [InlineKeyboardButton("📦 V2Box", callback_data=f"tutorial_ios_v2box_{account_id}")],
            [InlineKeyboardButton("🔙 بازگشت به آموزش", callback_data=f"services_tutorial_{account_id}")]
        ])
        
        await query.edit_message_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in show_ios_apps_menu: {e}")
        await query.answer("خطایی رخ داد.")

async def send_ios_streisand_tutorial(query, account_id):
    """Send iOS Streisand tutorial video"""
    try:
        text = """
🍎 آموزش iOS - Streisand

در حال ارسال ویدیو آموزشی...
        """
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت به iOS", callback_data=f"tutorial_ios_{account_id}")]
        ])
        
        await query.edit_message_text(text, reply_markup=keyboard)
        
        # TODO: Replace with actual video file_id or URL
        video_url = "https://example.com/ios_streisand_tutorial.mp4"  # Replace with actual video
        
        try:
            await query.message.reply_video(
                video=video_url,
                caption="🍎 آموزش نصب و راه‌اندازی Streisand روی iOS",
                reply_markup=keyboard
            )
        except Exception:
            instructions = """
🍎 آموزش Streisand برای iOS:

1️⃣ نصب برنامه Streisand از App Store
2️⃣ باز کردن برنامه و انتخاب گزینه اضافه کردن سرور
3️⃣ انتخاب "Import from Clipboard" یا "Scan QR code"  
4️⃣ کپی کردن لینک اشتراک یا اسکن QR کد
5️⃣ انتخاب سرور و اتصال

⚠️ ممکن است نیاز به VPN برای دانلود باشد.
            """
            
            await query.message.reply_text(instructions, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in send_ios_streisand_tutorial: {e}")
        await query.answer("خطایی در ارسال آموزش رخ داد.")

async def send_ios_v2box_tutorial(query, account_id):
    """Send iOS V2Box tutorial video"""
    try:
        text = """
🍎 آموزش iOS - V2Box

در حال ارسال ویدیو آموزشی...
        """
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت به iOS", callback_data=f"tutorial_ios_{account_id}")]
        ])
        
        await query.edit_message_text(text, reply_markup=keyboard)
        
        # TODO: Replace with actual video file_id or URL
        video_url = "https://example.com/ios_v2box_tutorial.mp4"  # Replace with actual video
        
        try:
            await query.message.reply_video(
                video=video_url,
                caption="🍎 آموزش نصب و راه‌اندازی V2Box روی iOS",
                reply_markup=keyboard
            )
        except Exception:
            instructions = """
🍎 آموزش V2Box برای iOS:

1️⃣ نصب برنامه V2Box از App Store
2️⃣ باز کردن برنامه و انتخاب گزینه "+"
3️⃣ انتخاب "Import from URL" یا "Scan QR code"
4️⃣ کپی کردن لینک اشتراک یا اسکن QR کد
5️⃣ انتخاب سرور و اتصال

⚠️ ممکن است نیاز به VPN برای دانلود باشد.
            """
            
            await query.message.reply_text(instructions, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in send_ios_v2box_tutorial: {e}")
        await query.answer("خطایی در ارسال آموزش رخ داد.")

# ================== Deletion Flow ==================

async def confirm_delete_service(query, account_id):
    """Show confirmation prompt before deleting service"""
    try:
        text = """
⚠️ **حذف سرویس**

با حذف سرویس، اکانت شما از تمامی سرورها و دیتابیس حذف می‌شود و قابل بازیابی نیست.

آیا مطمئن هستید؟
        """

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ تایید حذف", callback_data=f"confirm_delete_{account_id}")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data=f"services_view_{account_id}")]
        ])

        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in confirm_delete_service: {e}")
        await query.answer("خطایی رخ داد.")


async def delete_service(query, account_id, user):
    """Delete service from servers and database"""
    try:
        # Fetch account
        account = await account_manager.get_account_by_id(account_id)
        if not account:
            await query.answer("اکانت یافت نشد!")
            return

        # Delete via account_manager
        success = await account_manager.delete_account(account.uuid)

        if success:
            text = "✅ سرویس با موفقیت حذف شد."
        else:
            text = "❌ خطا در حذف سرویس. لطفاً بعداً دوباره تلاش کنید."

        # Show updated services list
        accounts = await account_manager.get_user_accounts(user.id)
        from bot.keyboards import get_services_keyboard
        keyboard = get_services_keyboard(accounts)

        await query.edit_message_text(text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Error deleting service: {e}")
        await query.answer("خطایی در حذف سرویس رخ داد.") 

# ---------------------------------------------------------------------------
# New helper to show list of accounts for renewal
# ---------------------------------------------------------------------------

async def show_renew_services_list(query, user):
    """Present user accounts to choose for renewal from main menu"""
    try:
        # Check if user has pending orders (purchase or renewal)
        pending_orders = await db_manager.get_pending_orders(user.id)
        
        if pending_orders:
            text = """
⚠️ سفارش در انتظار

 یک سفارش در انتظار تایید داری.

لطفاً تا تایید سفارش قبلی، سفارش جدید ثبت نکن.


            """
            keyboard = get_main_keyboard(user)
            await query.edit_message_text(text, reply_markup=keyboard)
            return
        
        accounts = await account_manager.get_user_accounts(user.id)

        if not accounts:
            text = (
                "🔄 تمدید سرویس\n\n"
                "شما هیچ سرویسی برای تمدید ندارید. 📭\n"
                "برای ایجاد سرویس جدید ابتدا از گزینه خرید سرویس استفاده کنید."
            )
            keyboard = get_main_keyboard(user)
        else:
            text = (
                "🔄 تمدید سرویس\n\n"
                "سرویس مورد نظر را انتخاب کنید تا فرآیند تمدید را ادامه دهید:"
            )
            keyboard = get_renew_accounts_keyboard(accounts)

        try:
            await query.edit_message_text(text, reply_markup=keyboard)
        except telegram.error.BadRequest as e:
            # If content is unchanged, delete and send new message
            if "Message is not modified" in str(e) or "message is not modified" in str(e).lower():
                try:
                    await query.delete_message()
                except Exception:
                    pass  # Silently ignore if we cannot delete
                
                # Send new message
                await context.bot.send_message(
                    chat_id=query.from_user.id,
                    text=text,
                    reply_markup=keyboard
                )
            else:
                # For other BadRequest errors, try to send new message
                await context.bot.send_message(
                    chat_id=query.from_user.id,
                    text=text,
                    reply_markup=keyboard
                )

    except Exception as e:
        logger.error(f"Error in show_renew_services_list: {e}")
        await query.answer("خطایی در نمایش سرویس‌ها رخ داد.") 