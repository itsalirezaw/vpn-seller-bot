import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from database.database import db_manager
from services.account_manager import account_manager
from bot.keyboards import (
    get_purchase_plans_keyboard,
    get_time_period_keyboard,
    get_data_plans_keyboard,
    get_payment_method_keyboard,
    get_main_keyboard,
    get_cancel_keyboard
)
from bot.states import ConversationStates
from bot.utils import format_price
from config.settings import SERVICE_PLANS, settings
from bot.handlers.admin import escape_markdown
from config.payment_utils import format_payment_info

logger = logging.getLogger(__name__)

async def purchase_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle purchase-related callbacks and conversations"""
    try:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            
            # Get user
            user = await db_manager.get_or_create_user(
                chat_id=update.effective_chat.id,
                username=update.effective_user.username
            )
            
            if query.data == "purchase_new":
                await show_purchase_plans(query, user)
                return ConversationStates.PURCHASE_PLAN_SELECTION
                
            elif query.data.startswith("period_"):
                period = query.data.split("_", 1)[1]
                # Check if we're in the right state or if this is a stray callback
                current_state = context.user_data.get('state')
                if current_state != ConversationStates.PURCHASE_PLAN_SELECTION and current_state is not None:
                    # This is a stray callback, redirect to main menu
                    from .main_menu import main_menu_handler
                    await main_menu_handler(update, context)
                    return ConversationHandler.END
                
                await show_data_plans_for_period(query, period)
                return ConversationStates.PURCHASE_PLAN_SELECTION
                
            elif query.data.startswith("plan_"):
                plan_id = query.data[len("plan_"):]  # keep full id even if contains underscores
                # Check if we're in the right state or if this is a stray callback
                current_state = context.user_data.get('state')
                if current_state != ConversationStates.PURCHASE_PLAN_SELECTION and current_state is not None:
                    # This is a stray callback, redirect to main menu
                    from .main_menu import main_menu_handler
                    await main_menu_handler(update, context)
                    return ConversationHandler.END
                
                await show_order_summary(query, context, user, plan_id)
                return ConversationStates.PURCHASE_PAYMENT_METHOD
                
            elif query.data.startswith("payment_"):
                payment_method = query.data.split("_")[1]
                # Check if we're in the right state or if this is a stray callback
                current_state = context.user_data.get('state')
                if current_state != ConversationStates.PURCHASE_PAYMENT_METHOD and current_state is not None:
                    # This is a stray callback, redirect to main menu
                    from .main_menu import main_menu_handler
                    await main_menu_handler(update, context)
                    return ConversationHandler.END
                
                result = await handle_payment_method(query, context, user, payment_method)
                
                if result:
                    return result
                elif payment_method == "direct":
                    return ConversationStates.PURCHASE_RECEIPT_UPLOAD
                else:
                    return ConversationHandler.END

            elif query.data == "confirm_wallet_payment":
                # Finalize wallet payment after user confirmation
                selected_plan = context.user_data.get('selected_plan')
                if not selected_plan:
                    await query.answer("پلن یافت نشد، لطفاً دوباره تلاش کنید.")
                    return ConversationHandler.END

                plan = SERVICE_PLANS[selected_plan]
                await handle_wallet_payment(query, context, user, plan, selected_plan)
                return ConversationHandler.END

            elif query.data == "cancel_purchase":
                # Import the cancel function from payment handler
                from .payment import cancel_payment_process
                await cancel_payment_process(update, context, "purchase")
                return ConversationHandler.END
                
        else:
            # Handle text messages in conversation
            return await handle_conversation_message(update, context)
    
    except Exception as e:
        logger.error(f"Error in purchase_handler: {e}")
        if update.callback_query:
            await update.callback_query.answer("خطایی رخ داده است.")
        else:
            await update.message.reply_text("خطایی رخ داده است.")
        return ConversationHandler.END

async def show_purchase_plans(query, user):
    """Show time period selection first"""
    try:
        # Check if user has pending orders
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
        
        text = f"""
🛒 خرید سرویس جدید

💰 موجودی کیف پول: {format_price(user.wallet_balance)}

⏳ زمان اشتراک مورد نظرت رو انتخاب کن: 🤓
        """
        
        keyboard = get_time_period_keyboard()
        await query.edit_message_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in show_purchase_plans: {e}")
        await query.answer("خطایی در نمایش پلن‌ها رخ داد.")

async def show_data_plans_for_period(query, period):
    """Show data plans for selected time period"""
    try:
        period_names = {
            "1m": "یک ماهه",
            "3m": "سه ماهه", 
            "6m": "شش ماهه"
        }
        
        text = f"""
📊 انتخاب حجم برای پلن {period_names.get(period, "")}

یکی از پلن‌ها رو انتخاب کن و برو برای پرداختش 🤲
        """
        
        keyboard = get_data_plans_keyboard(period)
        await query.edit_message_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in show_data_plans_for_period: {e}")
        await query.answer("خطایی رخ داد.")

async def show_order_summary(query, context, user, plan_id):
    """Show detailed order summary before payment"""
    try:
        logger.info(f"Order summary: received plan_id={plan_id}")
        
        if plan_id not in SERVICE_PLANS:
            await query.answer("پلن نامعتبر!")
            return
        
        plan = SERVICE_PLANS[plan_id]
        context.user_data['selected_plan'] = plan_id
        
        # Create account name format 
        user_name = f"VPN-{user.chat_id}-{str(user.id)[:5]}"
        data_gb = plan['data_limit'] // (1024**3)
        
        text = f"""
📋 پیش فاکتور شما:
    
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

سفارش شما آماده پرداخت است 🤲

روش پرداخت رو انتخاب کن: 😊
        """
        
        keyboard = get_payment_method_keyboard()
        await query.edit_message_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in show_order_summary: {e}")
        await query.answer("خطایی رخ داد.")

async def handle_plan_selection(query, context, user, plan_id):
    """Legacy function - redirects to order summary"""
    await show_order_summary(query, context, user, plan_id)

async def handle_payment_method(query, context, user, payment_method):
    """Handle payment method selection"""
    try:
        # Get selected plan from context
        selected_plan = context.user_data.get('selected_plan')
        if not selected_plan:
            await query.answer("لطفاً دوباره پلن را انتخاب کنید.")
            return
        
        plan = SERVICE_PLANS[selected_plan]
        
        if payment_method == "wallet":
            # Store selected plan for later
            context.user_data['selected_plan'] = selected_plan

            if user.wallet_balance < plan['price']:
                # Wallet insufficient – prompt user to top-up or switch method
                shortage = plan['price'] - user.wallet_balance
                text = f"""
❌ موجودی کیف پول کافی نیست

💰 قیمت سرویس: {format_price(plan['price'])}
💳 موجودی شما: {format_price(user.wallet_balance)}
💸 کمبود: {format_price(shortage)}

می‌توانید کیف پول خود را شارژ کنید یا روش پرداخت کارت به کارت را انتخاب کنید.
                """
                # Keyboard: charge wallet or use card to card
                from bot.keyboards import get_cancel_keyboard
                keyboard = [[
                    InlineKeyboardButton("💳 شارژ کیف پول", callback_data="wallet_charge")
                ], [
                    InlineKeyboardButton("💰 پرداخت کارت به کارت", callback_data="payment_direct")
                ], [
                    InlineKeyboardButton("🔙 بازگشت", callback_data="purchase_new")
                ]]
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
                return ConversationStates.PURCHASE_PAYMENT_METHOD

            # Sufficient balance – ask for confirmation
            text = f"""
💳 پرداخت از کیف پول

📦 پلن: {plan['name']}
💰 مبلغ: {format_price(plan['price'])}
💳 موجودی فعلی: {format_price(user.wallet_balance)}
💳 موجودی پس از خرید: {format_price(user.wallet_balance - plan['price'])}

آیا تایید می‌کنید؟
            """
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ تایید و پرداخت", callback_data="confirm_wallet_payment")],
                [InlineKeyboardButton("🔙 انصراف", callback_data="cancel_purchase")]
            ])
            await query.edit_message_text(text, reply_markup=keyboard)
            return ConversationStates.PURCHASE_PAYMENT_METHOD

        elif payment_method == "direct":
            await handle_direct_payment(query, context, user, plan, selected_plan)
            return ConversationStates.PURCHASE_RECEIPT_UPLOAD
        else:
            await query.answer("روش پرداخت نامعتبر!")
            return ConversationHandler.END
    
    except Exception as e:
        logger.error(f"Error in handle_payment_method: {e}")
        await query.answer("خطایی رخ داد.")
        return ConversationHandler.END

async def handle_wallet_payment(query, context, user, plan, plan_id):
    """Handle wallet payment"""
    try:
        if user.wallet_balance < plan['price']:
            text = f"""
❌ موجودی ناکافی

💰 قیمت سرویس: {format_price(plan['price'])}
💳 موجودی شما: {format_price(user.wallet_balance)}
💸 کمبود: {format_price(plan['price'] - user.wallet_balance)}

لطفاً ابتدا کیف پول خود را شارژ کنید.
            """
            keyboard = get_main_keyboard(user)
            await query.edit_message_text(text, reply_markup=keyboard)
            return
        
        # Deduct from wallet
        await db_manager.update_user_wallet(user.id, -plan['price'])
        
        # Create account
        account = await account_manager.create_account(user.id, plan_id)
        # Generate subscription link
        sub_link = None
        if account:
            sub_link = await account_manager.generate_subscription_link(account.uuid)
        
        if account:
            data_gb = plan['data_limit'] // (1024**3)
            text = f"""
✅ خرید موفق بود! 🎉

🔗 لینک سابسکرایب:
`{sub_link or 'در دسترس نیست'}`

📦 {plan['period_name']} - {data_gb} گیگ
⏳ مدت: {plan['expire_days']} روز

💰 مبلغ: {format_price(plan['price'])}
💳 موجودی: {format_price(user.wallet_balance - plan['price'])}

از منوی "مشاهده سرویس‌ها" برای کانفیگ استفاده کن 😊
            """
        else:
            # Refund on failure
            await db_manager.update_user_wallet(user.id, plan['price'])
            text = """
❌ خطا در ایجاد سرویس

مبلغ به کیف پولت بازگردانده شد.
لطفاً دوباره تلاش کن 😊
            """
        
        keyboard = get_main_keyboard(user)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in handle_wallet_payment: {e}")
        await query.answer("خطایی در پردازش پرداخت رخ داد.")

async def handle_direct_payment(query, context, user, plan, plan_id):
    """Handle direct card-to-card payment"""
    try:
        # Create order
        order = await db_manager.create_order(
            user_id=user.id,
            order_type="purchase",
            amount=plan['price'],
            plan_id=plan_id
        )
        
        if not order:
            await query.answer("خطا در ایجاد سفارش!")
            return
        
        # Store order info in context
        context.user_data['pending_order'] = order.id
        context.user_data['selected_plan'] = plan_id
        context.user_data['state'] = ConversationStates.PURCHASE_RECEIPT_UPLOAD
        
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
3️⃣ سرویس فعال می‌شه

منتظر رسیدت هستیم 😊
        """
        
        keyboard = get_cancel_keyboard("purchase")
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in handle_direct_payment: {e}")
        await query.answer("خطایی در ایجاد سفارش رخ داد.")

async def handle_conversation_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages during purchase conversation"""
    try:
        # Check if user wants to cancel
        if update.message.text and update.message.text.lower() in ['انصراف', 'لغو', 'cancel', 'انصراف میدم', 'لغو میکنم']:
            # Import the cancel function from payment handler
            from .payment import cancel_payment_process
            await cancel_payment_process(update, context, "purchase")
            return ConversationHandler.END
        
        # This should handle receipt upload
        if update.message.photo:
            return await handle_receipt_upload(update, context)
        else:
            await update.message.reply_text(
                "لطفاً عکس رسید واریز را ارسال کنید یا از دکمه انصراف استفاده کنید.",
                reply_markup=get_cancel_keyboard("purchase")
            )
            return ConversationStates.PURCHASE_RECEIPT_UPLOAD
    
    except Exception as e:
        logger.error(f"Error in handle_conversation_message: {e}")
        await update.message.reply_text("خطایی رخ داده است.")
        return ConversationHandler.END

async def handle_receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle receipt photo upload"""
    try:
        # Get pending order
        order_id = context.user_data.get('pending_order')
        plan_id = context.user_data.get('selected_plan')
        
        if not order_id or not plan_id:
            await update.message.reply_text("خطا: سفارش یافت نشد. لطفاً دوباره تلاش کنید.")
            return ConversationHandler.END
        
        # Get user
        user = await db_manager.get_or_create_user(
            chat_id=update.effective_chat.id,
            username=update.effective_user.username
        )
        
        # Download and save receipt
        photo = update.message.photo[-1]  # Get highest resolution
        file = await context.bot.get_file(photo.file_id)
        
        # Create receipts directory
        import os
        os.makedirs("receipts", exist_ok=True)
        
        receipt_path = f"receipts/receipt_{order_id}_{photo.file_id}.jpg"
        await file.download_to_drive(receipt_path)
        
        # Update order with receipt
        db = db_manager.get_session()
        try:
            from database.models import Order
            order = db.query(Order).filter_by(id=order_id).first()
            if order:
                order.receipt_path = receipt_path
                db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating order with receipt: {e}")
        finally:
            db.close()
        
        # Create account immediately (before admin approval)
        plan = SERVICE_PLANS[plan_id]
        account = await account_manager.create_account(user.id, plan_id)
        # Generate subscription link
        sub_link = None
        if account:
            sub_link = await account_manager.generate_subscription_link(account.uuid)
        
        if account:
            # Update order with account info
            db = db_manager.get_session()
            try:
                order = db.query(Order).filter_by(id=order_id).first()
                if order:
                    order.account_id = account.id
                    db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"Error updating order with account: {e}")
            finally:
                db.close()
            
            text = f"""
✅ رسید دریافت شد!

سرویس شما با موفقیت ایجاد شد! 🎉

🔗 لینک سابسکرایب:
`{sub_link or 'در دسترس نیست'}`

📦 مشخصات:
• پلن: {plan['name']}
• حجم: {'نامحدود' if plan['data_limit'] == 0 else f"{plan['data_limit'] // (1024**3)} گیگابایت"}
• مدت: {plan['expire_days']} روز

💰 مبلغ: {format_price(plan['price'])}

🔧 برای مشاهده کانفیگ‌ها از منوی "مشاهده سرویس‌ها" استفاده کنید.

⏳ رسید شما در حال بررسی است:
• ✅ تایید: سرویس فعال باقی می‌ماند
• ❌ رد: سرویس حذف خواهد شد

📞 در صورت سوال با پشتیبانی تماس بگیرید.
            """
            
            # Notify admins
            await notify_admins_new_order(context, user, order, account, plan)
            
        else:
            text = """
❌ خطا در ایجاد سرویس

متأسفانه خطایی در ایجاد سرویس رخ داد.
رسید شما ثبت شده و توسط ادمین بررسی خواهد شد.

در صورت تایید رسید، سرویس شما فعال خواهد شد.
            """
        
        keyboard = get_main_keyboard(user)
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')
        
        # Clear context
        context.user_data.pop('pending_order', None)
        context.user_data.pop('selected_plan', None)
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in handle_receipt_upload: {e}")
        await update.message.reply_text("خطایی در پردازش رسید رخ داد.")
        return ConversationHandler.END

async def cancel_purchase(query, user):
    """Cancel purchase process"""
    try:
        text = """
❌ خرید لغو شد

خرید سرویس لغو شد.
می‌توانید هر زمان دوباره اقدام کنید.
        """
        
        keyboard = get_main_keyboard(user)
        await query.edit_message_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in cancel_purchase: {e}")
        await query.answer("خطایی رخ داد.")

async def notify_admins_new_order(context, user, order, account, plan):
    """Notify admins about new order"""
    try:
        admin_text = f"""
🔔 سفارش جدید دریافت شد

👤 کاربر: {escape_markdown(user.username) if user.username else 'N/A'} (ID: {user.chat_id})
📦 پلن: {escape_markdown(plan['name'])}
💰 مبلغ: {format_price(plan['price'])}

📧 سرویس ایجاد شده: {escape_markdown(account.email)}

📄 رسید: دریافت شده
⏳ وضعیت: در انتظار بررسی

برای مدیریت از دستور /admin استفاده کنید.
        """
        
        # Send to all admins
        for admin_id in settings.bot.ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_text,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Error sending notification to admin {admin_id}: {e}")
    
    except Exception as e:
        logger.error(f"Error in notify_admins_new_order: {e}") 