from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from datetime import datetime, timedelta
import json
import logging

def escape_markdown(text):
    """Escape special Markdown characters"""
    if not text:
        return text
    
    # Characters that need escaping in Markdown
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text

from database.database import async_session
from database.models import User, Order, Server, Account, ServerAccount, Invitation
from services.server_manager import ServerManager
from services.account_manager import AccountManager
from services.xui_api import create_client_config
from services.monitoring import monitoring_service
from bot.states import AdminStates
from bot.keyboards import get_admin_main_keyboard, get_admin_orders_keyboard, get_admin_users_keyboard, get_admin_servers_keyboard
from config.settings import ADMIN_IDS, SERVICE_PLANS, to_persian_number
from bot.utils import format_data_size, format_price
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

async def admin_required(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check if user is admin"""
    user_id = update.effective_user.id
    return user_id in ADMIN_IDS

async def admin_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main admin menu"""
    if not await admin_required(update, context):
        await update.message.reply_text("🚫 شما دسترسی ادمین ندارید")
        return ConversationHandler.END
    
    keyboard = get_admin_main_keyboard()
    text = """
🔧 **پنل مدیریت**

به پنل مدیریت ربات خوش آمدید. از منوی زیر گزینه مورد نظر خود را انتخاب کنید:

• مدیریت سفارشات
• مدیریت کاربران  
• مدیریت سرورها
• آمار و گزارشات
• تنظیمات سیستم
"""
    
    # Add server status warning if no servers configured
    from config.settings import settings
    if not settings.servers:
        text += "\n⚠️ **هشدار:** هیچ سرور در فایل .env تنظیم نشده است!"
    else:
        text += f"\n✅ {len(settings.servers)} سرور پیکربندی شده"

    # پاسخ بر اساس نوع آپدیت (پیام یا CallbackQuery)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return AdminStates.MAIN_MENU

async def admin_orders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Orders management menu"""
    if not await admin_required(update, context):
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    keyboard = get_admin_orders_keyboard()
    
    # Get pending orders count
    async with async_session() as session:
        pending_count = await session.scalar(
            select(func.count(Order.id)).where(Order.status == 'pending')
        )
    
    text = f"""
📋 **مدیریت سفارشات**

تعداد سفارشات در انتظار: {to_persian_number(str(pending_count))}

گزینه مورد نظر خود را انتخاب کنید:
"""
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return AdminStates.ORDERS_MENU

async def admin_pending_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pending orders"""
    if not await admin_required(update, context):
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    async with async_session() as session:
        orders = await session.scalars(
            select(Order)
            .options(selectinload(Order.user))
            .where(Order.status == 'pending')
            .order_by(Order.created_at.desc())
            .limit(10)
        )
        orders_list = list(orders)
    
    if not orders_list:
        text = "✅ هیچ سفارش در انتظاری وجود ندارد"
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 بازگشت", callback_data="admin_orders_menu")
        ]])
    else:
        text = "📋 **سفارشات در انتظار:**\n\n"
        buttons = []
        
        for order in orders_list:
            plan_name = SERVICE_PLANS.get(order.plan_id, {}).get('name', 'نامشخص')
            username = escape_markdown(order.user.username) if order.user.username else 'بدون نام'
            safe_plan_name = escape_markdown(plan_name)
            order_text = f"""
🆔 سفارش: {to_persian_number(str(order.id))}
👤 کاربر: {username}
📱 چت ای دی: {to_persian_number(str(order.user.chat_id))}
📋 سرویس: {safe_plan_name}
💰 مبلغ: {to_persian_number(f'{order.amount:,}')} تومان
⏰ تاریخ: {order.created_at.strftime('%Y/%m/%d %H:%M')}
"""
            text += order_text + "\n" + "─" * 30 + "\n"
            
            buttons.append([
                InlineKeyboardButton(
                    f"بررسی سفارش {to_persian_number(str(order.id))}", 
                    callback_data=f"admin_review_order_{order.id}"
                )
            ])
        
        buttons.append([
            InlineKeyboardButton("🔙 بازگشت", callback_data="admin_orders_menu")
        ])
        keyboard = InlineKeyboardMarkup(buttons)
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return AdminStates.PENDING_ORDERS

async def admin_review_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Review specific order"""
    if not await admin_required(update, context):
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    order_id = int(query.data.split('_')[-1])
    
    async with async_session() as session:
        order = await session.scalar(
            select(Order)
            .options(selectinload(Order.user))
            .where(Order.id == order_id)
        )
    
    if not order:
        await query.edit_message_text("❌ سفارش یافت نشد")
        return AdminStates.PENDING_ORDERS
    
    plan_info = SERVICE_PLANS.get(order.plan_id, {})
    
    username = escape_markdown(order.user.username) if order.user.username else 'بدون نام'
    safe_plan_name = escape_markdown(plan_info.get('name', 'نامشخص'))
    
    text = f"""
📋 **جزئیات سفارش**

🆔 شماره سفارش: {to_persian_number(str(order.id))}
👤 کاربر: {username}
📱 Chat ID: {to_persian_number(str(order.user.chat_id))}
💳 User ID: {to_persian_number(str(order.user.id))}
📋 سرویس: {safe_plan_name}
💰 مبلغ: {to_persian_number(f'{order.amount:,}')} تومان
⏰ تاریخ ایجاد: {order.created_at.strftime('%Y/%m/%d %H:%M')}
📄 وضعیت: {order.status}
"""
    
    if order.receipt_path:
        text += f"\n📷 رسید پرداخت: موجود"
    
    if hasattr(order, 'admin_note') and order.admin_note:
        safe_admin_note = escape_markdown(order.admin_note)
        text += f"\n📝 یادداشت ادمین: {safe_admin_note}"
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تایید", callback_data=f"admin_approve_order_{order.id}"),
            InlineKeyboardButton("❌ رد", callback_data=f"admin_reject_order_{order.id}")
        ],
        [
            InlineKeyboardButton("📷 مشاهده رسید", callback_data=f"admin_view_receipt_{order.id}")
        ] if order.receipt_path else [],
        [
            InlineKeyboardButton("📝 افزودن یادداشت", callback_data=f"admin_add_note_{order.id}")
        ],
        [
            InlineKeyboardButton("🔙 بازگشت", callback_data="admin_pending_orders")
        ]
    ])
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    # در صورت وجود رسید، عکس آن را برای ادمین ارسال کن
    if order.receipt_path:
        try:
            with open(order.receipt_path, 'rb') as receipt_file:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=receipt_file,
                    caption=f"📷 رسید پرداخت سفارش {to_persian_number(str(order.id))}"
                )
        except FileNotFoundError:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="❌ فایل رسید یافت نشد"
            )
 
    return AdminStates.REVIEW_ORDER

async def admin_view_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View order receipt"""
    if not await admin_required(update, context):
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    order_id = int(query.data.split('_')[-1])
    
    async with async_session() as session:
        order = await session.scalar(
            select(Order).where(Order.id == order_id)
        )
    
    if not order or not order.receipt_path:
        await query.edit_message_text("❌ رسید یافت نشد")
        return AdminStates.REVIEW_ORDER
    
    # Send receipt as document/photo
    try:
        with open(order.receipt_path, 'rb') as receipt_file:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=receipt_file,
                caption=f"📷 رسید پرداخت سفارش {to_persian_number(str(order.id))}"
            )
    except FileNotFoundError:
        await query.edit_message_text("❌ فایل رسید یافت نشد")
        return AdminStates.REVIEW_ORDER
    
    # Return to order review
    return await admin_review_order(update, context)

async def admin_approve_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve order and create account"""
    if not await admin_required(update, context):
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    order_id = int(query.data.split('_')[-1])
    
    async with async_session() as session:
        order = await session.scalar(
            select(Order)
            .options(selectinload(Order.user))
            .where(Order.id == order_id)
        )
        
        if not order:
            await query.edit_message_text("❌ سفارش یافت نشد")
            return AdminStates.REVIEW_ORDER
        
        if order.status != 'pending':
            await query.edit_message_text("❌ این سفارش قبلاً پردازش شده است")
            return AdminStates.REVIEW_ORDER
        
        plan_info = SERVICE_PLANS.get(order.plan_id, {})

        try:
            account_manager = AccountManager()

            # ------------------------------------------------------------------
            # Purchase orders – create new account if not already
            # ------------------------------------------------------------------
            if order.type == 'purchase':
                if order.account_id:
                    account = await session.scalar(select(Account).where(Account.id == order.account_id))
                else:
                    account = await account_manager.create_account(
                        user_id=order.user.id,
                        plan_id=order.plan_id
                    )
                    order.account_id = account.id

                # Check server assignments to warn admin if needed
                account_servers = await account_manager.get_account_servers(account.id)

            # ------------------------------------------------------------------
            # Renewal orders – account already exists, nothing else to do
            # ------------------------------------------------------------------
            elif order.type == 'renewal':
                # Fetch related account just for messaging
                account = await session.scalar(select(Account).where(Account.id == order.account_id))
                account_servers = []  # Not relevant for renewals

            # ------------------------------------------------------------------
            # Wallet charge orders – add money to user wallet
            # ------------------------------------------------------------------
            elif order.type == 'wallet_charge':
                # Add money to user wallet
                from database.database import db_manager
                await db_manager.update_user_wallet(order.user.id, order.amount)
                account = None
                account_servers = []

            else:
                account = None
                account_servers = []

            # Update order status
            order.status = 'approved'
            order.processed_at = datetime.now()
            await session.commit()

            # ------------------------------------------------------------------
            # Notify user
            # ------------------------------------------------------------------
            if order.type == 'purchase':
                safe_plan_name = escape_markdown(plan_info.get('name', 'نامشخص'))
                approval_message = (
                    "🎉 **سفارش شما تایید شد**\n\n"
                    "سرویس شما با موفقیت فعال شده 🔥\n\n"
                    f"📋 سرویس: {safe_plan_name}\n\n"
                    "🔧 برای مشاهده جزئیات از منوی \"مشاهده سرویس‌ها\" استفاده کن 🤓"
                )
            elif order.type == 'wallet_charge':
                # Get updated wallet balance
                updated_user = await session.scalar(select(User).where(User.id == order.user.id))
                approval_message = (
                    "💰 **شارژ کیف پول تایید شد**\n\n"
                    f"💳 مبلغ شارژ: {format_price(order.amount)}\n"
                    f"💰 موجودی جدید: {format_price(updated_user.wallet_balance)}\n\n"
                    "✅ کیف پول شما شارژ شد."
                )
            else:  # renewal
                # برای تمدیدها، چک کن که آیا قبلاً approved شده یا نه
                if order.status == 'approved':
                    # قبلاً تمدید فوری انجام شده - فقط پیام تایید نهایی
                    approval_message = (
                        "✅ **تمدید تایید شد**\n\n"
                        "تمدید شما انجام شده 🔥"
                    )
                else:
                    # تمدید عادی که باید الان انجام بشه
                    safe_plan_name = escape_markdown(plan_info.get('name', 'نامشخص'))
                    approval_message = (
                        "✅ **تمدید تایید شد**\n\n"
                        f"📋 پلن: {safe_plan_name}\n\n"
                        "سرویس شما تمدید شد 🔥"
                    )

            await context.bot.send_message(
                chat_id=order.user.chat_id,
                text=approval_message,
                parse_mode=ParseMode.MARKDOWN,
            )

            # ------------------------------------------------------------------
            # Notify admin feedback
            # ------------------------------------------------------------------
            admin_message = f"✅ سفارش {to_persian_number(str(order.id))} تایید شد"
            admin_buttons = [[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_pending_orders")]]
            
            if order.type == 'purchase' and account and not account_servers:
                admin_message += f"\n⚠️ نیاز به تخصیص دستی سرور برای اکانت {account.uuid[:8]}..."
                admin_buttons.insert(0, [InlineKeyboardButton("🔗 تخصیص سرور", callback_data=f"admin_assign_server_{account.id}")])
            
            await query.edit_message_text(admin_message, reply_markup=InlineKeyboardMarkup(admin_buttons))

        except Exception as e:
            logger.error(f"Error approving order {order.id}: {e}")
            await query.edit_message_text(
                f"❌ خطا در تایید سفارش: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 بازگشت", callback_data="admin_pending_orders")
                ]])
            )
    return AdminStates.PENDING_ORDERS

async def admin_reject_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reject order: refund user and delete any associated account from all servers"""
    if not await admin_required(update, context):
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    order_id = int(query.data.split('_')[-1])
    
    async with async_session() as session:
        order: Order = await session.scalar(
            select(Order).options(selectinload(Order.user)).where(Order.id == order_id)
        )
        
        # Validate order
        if not order:
            await query.edit_message_text("❌ سفارش یافت نشد")
            return AdminStates.REVIEW_ORDER
        
        if order.status != 'pending':
            await query.edit_message_text("❌ این سفارش قبلاً پردازش شده است")
            return AdminStates.REVIEW_ORDER
        
        try:
            # 1) Update order status
            order.status = 'rejected'
            order.processed_at = datetime.now()
            
            # ذخیره UUID اکانت (در صورت وجود) پیش از بستن سشن
            account_uuid = None
            if order.account_id:
                account_uuid = await session.scalar(
                    select(Account.uuid).where(Account.id == order.account_id)
                )

            await session.commit()      # <-- پایان تراکنش

            # ------------------------------------------------------------------
            # Renewal vs Purchase differentiation
            # ------------------------------------------------------------------
            if order.type == 'purchase':
                # حذف کامل اکانت برای خریدهای رد شده
                if account_uuid:
                    acct_mgr = AccountManager()
                    await acct_mgr.delete_account(account_uuid)
            elif order.type == 'renewal':
                # فقط حذف حجم/زمان اضافه شده برای تمدید رد شده
                plan_info = SERVICE_PLANS.get(order.plan_id, {})

                if order.account_id:
                    acc = await session.scalar(select(Account).where(Account.id == order.account_id))
                    if acc:
                        # Rollback added quota
                        if plan_info.get('data_limit', 0) > 0 and acc.total_data_limit > 0:
                            acc.total_data_limit = max(0, acc.total_data_limit - plan_info['data_limit'])

                        if plan_info.get('expire_days', 0) > 0:
                            acc.expire_time -= timedelta(days=plan_info['expire_days'])

                        await session.commit()

                        # Rollback also on X-UI servers
                        try:
                            acct_mgr = AccountManager()
                            server_pairs = await acct_mgr.get_account_servers(acc.id)
                            server_names = [srv.name for srv, _ in server_pairs]
                            expire_days = max(0, (acc.expire_time - datetime.utcnow()).days)
                            client_config = create_client_config(
                                user_uuid=acc.uuid,
                                email=acc.email,
                                total_bytes=acc.total_data_limit,
                                expire_days=expire_days
                            )
                            client_config["enable"] = True
                            await acct_mgr.server_manager.xui_manager.update_client_on_servers(
                                server_names,
                                4,
                                acc.uuid,
                                client_config,
                            )
                        except Exception as e:
                            logger.error(f"Error rolling back quota on X-UI servers: {e}")

            # ------------------------------------------------------------------
            # Notify user for rejection
            # ------------------------------------------------------------------
            if order.type == 'renewal':
                reject_text = (
                    "❌ **تمدید شما رد شد**\n\n"
                    f"🆔 شماره سفارش: {to_persian_number(str(order.id))}\n"
                    f"💰 مبلغ: {to_persian_number(f'{order.amount:,}')} تومان\n\n"
                    "اعتبار اضافه شده به سرویس شما حذف شد 🔥\n"
                    "در صورت نیاز به پیگیری، لطفاً با پشتیبانی ارتباط بگیر 🤓"
                )
            else:
                reject_text = (
                    "❌ **سفارش رد شد**\n\n"
                    f"🆔 شماره سفارش: {to_persian_number(str(order.id))}\n"
                    f"💰 مبلغ: {to_persian_number(f'{order.amount:,}')} تومان\n\n"
                    "به دلیل عدم تطابق تراکنش، سفارش شما رد شد و اکانت مربوطه حذف گردید 🔥\n"
                    "در صورت نیاز به پیگیری، لطفاً با پشتیبانی ارتباط بگیر 🤓"
                )
            
            await context.bot.send_message(
                chat_id=order.user.chat_id,
                text=reject_text
            )
            
            logger.info(f"Order {order.id} rejected by admin")

            await query.edit_message_text("✅ سفارش با موفقیت رد شد")

        except Exception as e:
            logger.error(f"Error rejecting order {order.id}: {e}")
            await query.edit_message_text(f"❌ خطا در رد سفارش: {str(e)}")

    return AdminStates.PENDING_ORDERS

async def admin_assign_server(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually assign servers to an account"""
    if not await admin_required(update, context):
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    account_id = int(query.data.split('_')[-1])
    
    async with async_session() as session:
        account = await session.scalar(select(Account).where(Account.id == account_id))
        
        if not account:
            await query.edit_message_text("❌ اکانت یافت نشد")
            return AdminStates.MAIN_MENU
        
        try:
            # Try to assign account to best available servers
            account_manager = AccountManager()
            success = await account_manager.assign_account_to_servers(account.uuid)
            
            if success:
                await query.edit_message_text(
                    f"✅ سرورها با موفقیت به اکانت {account.uuid[:8]}... تخصیص داده شدند",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 بازگشت", callback_data="admin_pending_orders")
                    ]])
                )
                
                # Send final account info to user
                user = await session.scalar(select(User).where(User.id == account.user_id))
                if user:
                    safe_email = escape_markdown(account.email)
                    safe_uuid = escape_markdown(account.uuid)
                    final_text = f"""
🎉 **اکانت شما آماده شد!**

🔗 **اطلاعات اکانت:**
📧 ایمیل: `{safe_email}`
🆔 UUID: `{safe_uuid}`
⏰ تاریخ انقضا: {account.expire_time.strftime('%Y/%m/%d')}

✅ اکانت شما روی سرورها فعال شد 🔥
"""
                    
                    await context.bot.send_message(
                        chat_id=user.chat_id,
                        text=final_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                    # Send config info
                    config_info = f"ایمیل: {account.email}\nUUID: {account.uuid}\nانقضا: {account.expire_time.strftime('%Y/%m/%d')}"
                    safe_config_info = escape_markdown(config_info)
                    await context.bot.send_message(
                        chat_id=user.chat_id,
                        text=f"🔧 **اطلاعات اکانت:**\n\n```\n{safe_config_info}\n```",
                        parse_mode=ParseMode.MARKDOWN
                    )
            else:
                await query.edit_message_text(
                    f"❌ خطا در تخصیص سرور به اکانت {account.uuid[:8]}...\n\n"
                    "احتمالاً:\n"
                    "• هیچ سرور فعال نیست\n"
                    "• سرورها در فایل .env تنظیم نشده‌اند\n"
                    "• API سرورها در دسترس نیست\n\n"
                    "لطفاً log ها را بررسی کن 🤓",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 بازگشت", callback_data="admin_pending_orders")
                ]])
            )
            
        except Exception as e:
            logger.error(f"Error in manual server assignment: {e}")
        await query.edit_message_text(
                f"❌ خطا در تخصیص سرور: {str(e)}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data="admin_pending_orders")
            ]])
        )
    
    return AdminStates.PENDING_ORDERS

async def admin_users_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Users management menu"""
    if not await admin_required(update, context):
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    keyboard = get_admin_users_keyboard()
    
    # Get users stats
    async with async_session() as session:
        total_users = await session.scalar(select(func.count(User.id)))
        active_users = await session.scalar(
            select(func.count(User.id)).where(User.is_active == True)
        )
    
    text = f"""
👥 **مدیریت کاربران**

کل کاربران: {to_persian_number(str(total_users))}
کاربران فعال: {to_persian_number(str(active_users))}

گزینه مورد نظر خود را انتخاب کنید:
"""
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return AdminStates.USERS_MENU

async def admin_user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed user statistics"""
    if not await admin_required(update, context):
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    async with async_session() as session:
        # Basic stats
        total_users = await session.scalar(select(func.count(User.id)))
        active_users = await session.scalar(
            select(func.count(User.id)).where(User.is_active == True)
        )
        users_with_accounts = await session.scalar(
            select(func.count(User.id.distinct())).select_from(User).join(Account)
        )
        
        # New users in last 30 days
        thirty_days_ago = datetime.now() - timedelta(days=30)
        new_users_30d = await session.scalar(
            select(func.count(User.id)).where(User.created_at >= thirty_days_ago)
        )
        
        # Top users by wallet balance
        top_users = await session.scalars(
            select(User).order_by(User.wallet_balance.desc()).limit(10)
        )
        top_users_list = list(top_users)
    
    text = f"""
📊 **آمار کاربران**

👥 کل کاربران: {to_persian_number(str(total_users))}
✅ کاربران فعال: {to_persian_number(str(active_users))}
🔗 دارای حساب VPN: {to_persian_number(str(users_with_accounts))}
🆕 عضویت ۳۰ روز اخیر: {to_persian_number(str(new_users_30d))}

💰 **کاربران با بالاترین موجودی:**
"""
    
    for i, user in enumerate(top_users_list[:5], 1):
        safe_username = escape_markdown(user.username) if user.username else 'بدون نام'
        text += f"\n{i}. {safe_username}: {to_persian_number(f'{user.wallet_balance:,}')} تومان"
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 بازگشت", callback_data="admin_users_menu")
    ]])
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return AdminStates.USERS_MENU

async def admin_servers_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Servers management menu"""
    if not await admin_required(update, context):
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    keyboard = get_admin_servers_keyboard()
    
    # Get servers stats
    async with async_session() as session:
        servers = await session.scalars(select(Server))
        servers_list = list(servers)
    
    text = f"""
🖥️ **مدیریت سرورها**

تعداد سرورها: {to_persian_number(str(len(servers_list)))}
سرورهای فعال: {to_persian_number(str(len([s for s in servers_list if s.is_active])))}

گزینه مورد نظر خود را انتخاب کنید:
"""
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return AdminStates.SERVERS_MENU

async def admin_server_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show server status"""
    if not await admin_required(update, context):
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    async with async_session() as session:
        servers = await session.scalars(select(Server))
        servers_list = list(servers)
    
    text = "🖥️ **وضعیت سرورها:**\n\n"
    
    server_manager = ServerManager()
    
    for server in servers_list:
        try:
            # Get server metrics
            metrics = await server_manager.get_server_metrics(server.id)
            
            status_icon = "🟢" if server.is_active else "🔴"
            online_icon = "✅" if metrics.is_online else "❌"
            
            safe_server_name = escape_markdown(server.name)
            safe_server_host = escape_markdown(server.host)
            server_text = f"""
{status_icon} **{safe_server_name}**
🌐 آدرس: {safe_server_host}:{server.port}
{online_icon} وضعیت: {'آنلاین' if metrics.is_online else 'آفلاین'}
�� کاربران فعال: {to_persian_number(str(metrics.active_clients))}
📊 ترافیک: {format_data_size(metrics.total_traffic)}
💾 استفاده CPU: {metrics.cpu_usage:.1f}%
🧠 استفاده RAM: {metrics.ram_usage:.1f}%
"""
            text += server_text + "\n" + "─" * 30 + "\n"
            
        except Exception as e:
            logger.error(f"Error getting server {server.id} metrics: {e}")
            safe_server_name = escape_markdown(server.name)
            safe_server_host = escape_markdown(server.host)
            text += f"""
🔴 **{safe_server_name}**
🌐 آدرس: {safe_server_host}:{server.port}
❌ خطا در دریافت اطلاعات
"""
        text += "\n" + "─" * 30 + "\n"
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 بروزرسانی", callback_data="admin_server_status"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="admin_servers_menu")
    ]])
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return AdminStates.SERVERS_MENU

async def admin_monitoring_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show monitoring status"""
    if not await admin_required(update, context):
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    try:
        status = await monitoring_service.get_system_status()

        text = f"""
📊 **وضعیت سیستم مانیتورینگ**

🖥️ **سرورها:**
• کل سرورها: {to_persian_number(str(status['servers']['total']))}
• فعال: {to_persian_number(str(status['servers']['active']))}
• آنلاین: {to_persian_number(str(status['servers']['online']))}
• آفلاین: {to_persian_number(str(status['servers']['offline']))}

👥 **حساب‌های کاربری:**
• کل حساب‌ها: {to_persian_number(str(status['accounts']['total']))}
• فعال: {to_persian_number(str(status['accounts']['active']))}

📈 **آمار ترافیک:**
"""
        if status.get('traffic_stats'):
            for server_id, stats in status['traffic_stats'].items():
                total_formatted = f"{stats.get('total', 0):,}"
                text += f"• سرور {server_id}: {to_persian_number(total_formatted)} بایت\n"

        text += f"""
⚠️ **هشدارها:**
• هشدارهای فعال: {to_persian_number(str(status['alerts']['active']))}
• هشدارهای بحرانی: {to_persian_number(str(status['alerts']['critical']))}
"""

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 بروزرسانی", callback_data="admin_system_status"),
                InlineKeyboardButton("🔙 بازگشت", callback_data="admin_main_menu")
            ]]),
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        await query.edit_message_text(
            f"❌ خطا در دریافت وضعیت سیستم: {str(e)}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت", callback_data="admin_main_menu")
            ]]),
            parse_mode=ParseMode.MARKDOWN
        )

    return AdminStates.MAIN_MENU

async def admin_system_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show system statistics"""
    if not await admin_required(update, context):
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    async with async_session() as session:
        # Orders stats
        total_orders = await session.scalar(select(func.count(Order.id)))
        pending_orders = await session.scalar(
            select(func.count(Order.id)).where(Order.status == 'pending')
        )
        approved_orders = await session.scalar(
            select(func.count(Order.id)).where(Order.status == 'approved')
        )
        
        # Revenue stats
        total_revenue = await session.scalar(
            select(func.sum(Order.amount)).where(Order.status == 'approved')
        ) or 0
        
        # Account stats
        total_accounts = await session.scalar(select(func.count(Account.id)))
        active_accounts = await session.scalar(
            select(func.count(Account.id)).where(Account.is_active == True)
        )
        
        # Invitation stats
        total_invites = await session.scalar(select(func.count(Invitation.id)))
        successful_invites = await session.scalar(
            select(func.count(Invitation.id)).where(Invitation.used == True)
        )
    
    text = f"""
📊 **آمار کل سیستم**

📋 **سفارشات:**
• کل سفارشات: {to_persian_number(str(total_orders))}
• در انتظار: {to_persian_number(str(pending_orders))}
• تایید شده: {to_persian_number(str(approved_orders))}

💰 **درآمد:**
• کل درآمد: {to_persian_number(f'{total_revenue:,}')} تومان

👥 **حساب‌های کاربری:**
• کل حساب‌ها: {to_persian_number(str(total_accounts))}
• فعال: {to_persian_number(str(active_accounts))}

🔗 **دعوت‌نامه‌ها:**
• کل دعوت‌نامه‌ها: {to_persian_number(str(total_invites))}
• استفاده شده: {to_persian_number(str(successful_invites))}

⏰ آخرین بروزرسانی: {datetime.now().strftime('%Y/%m/%d %H:%M')}
"""
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 بروزرسانی", callback_data="admin_system_stats"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="admin_main_menu")
    ]])
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return AdminStates.MAIN_MENU

async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel admin conversation"""
    if not await admin_required(update, context):
        return ConversationHandler.END
    
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "✅ عملیات لغو شد",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔧 بازگشت به پنل ادمین", callback_data="admin_main_menu")
        ]])
    )
    return ConversationHandler.END

async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin commands and callback queries"""
    if not await admin_required(update, context):
        return ConversationHandler.END

    # 1) /admin command sent as a regular message
    if update.message:
        return await admin_main_menu(update, context)

    # 2) Callback query interactions (all buttons start with "admin_")
    query = update.callback_query
    if not query:
        # No callback and not a message; nothing to handle
        return ConversationHandler.END

    data = query.data or ""

    if data == "admin_main_menu":
        return await admin_main_menu(update, context)
    elif data == "admin_orders_menu":
        return await admin_orders_menu(update, context)
    elif data == "admin_pending_orders":
        return await admin_pending_orders(update, context)
    elif data.startswith("admin_review_order_"):
        return await admin_review_order(update, context)
    elif data.startswith("admin_view_receipt_"):
        return await admin_view_receipt(update, context)
    elif data.startswith("admin_approve_order_"):
        return await admin_approve_order(update, context)
    elif data.startswith("admin_reject_order_"):
        return await admin_reject_order(update, context)
    elif data.startswith("admin_assign_server_"):
        return await admin_assign_server(update, context)
    elif data == "admin_users_menu":
        return await admin_users_menu(update, context)
    elif data == "admin_user_stats":
        return await admin_user_stats(update, context)
    elif data == "admin_servers_menu":
        return await admin_servers_menu(update, context)
    elif data == "admin_server_status":
        return await admin_server_status(update, context)
    elif data == "admin_monitoring_status":
        return await admin_monitoring_status(update, context)
    elif data == "admin_system_stats":
        return await admin_system_stats(update, context)
    elif data == "admin_cancel":
        return await admin_cancel(update, context)

    # If no handler matched, notify and show main menu
    await query.answer("گزینه نامعتبر")
    return await admin_main_menu(update, context)