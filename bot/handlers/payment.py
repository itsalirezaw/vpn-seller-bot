import logging
from datetime import datetime
from telegram.constants import ParseMode
import os
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import telegram

from database.database import db_manager
from database.models import Order
from bot.keyboards import get_main_keyboard, get_cancel_keyboard
from bot.states import ConversationStates
from bot.utils import format_price
from config.settings import settings
from bot.handlers.admin import escape_markdown
from config.payment_utils import format_payment_info

logger = logging.getLogger(__name__)

async def payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment-related callbacks and conversations"""
    try:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            
            # Get user
            user = await db_manager.get_or_create_user(
                chat_id=update.effective_chat.id,
                username=update.effective_user.username
            )
            
            if query.data == "wallet_charge":
                await start_wallet_charge(query, user)
                return ConversationStates.WALLET_AMOUNT_INPUT
                
            elif query.data == "cancel_wallet":
                await cancel_payment_process(update, context, "wallet")
                return ConversationHandler.END
                
            elif query.data == "cancel_purchase":
                await cancel_payment_process(update, context, "purchase")
                return ConversationHandler.END
                
            elif query.data == "cancel_renewal":
                await cancel_payment_process(update, context, "renewal")
                return ConversationHandler.END
                
        else:
            # Handle text/photo messages in conversation
            return await handle_conversation_message(update, context)
    
    except Exception as e:
        logger.error(f"Error in payment_handler: {e}")
        if update.callback_query:
            await update.callback_query.answer("خطایی رخ داده است.")
        else:
            await update.message.reply_text("خطایی رخ داده است.")
        return ConversationHandler.END

async def start_wallet_charge(query, user):
    """Start wallet charge process"""
    try:
        text = f"""
💳 شارژ کیف پول

💰 موجودی فعلی: {format_price(user.wallet_balance)}

🔹 حداقل مبلغ شارژ: {format_price(settings.min_wallet_charge)}
🔹 حداکثر مبلغ شارژ: {format_price(settings.max_wallet_charge)}

💡 مبلغ مورد نظر برای شارژ را بنویس:
(مثال: 50000 یا 100000)

⚠️ یادت نره که مبلغ رو به تومان وارد کنی
        """
        
        keyboard = get_cancel_keyboard("wallet")
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
        logger.error(f"Error in start_wallet_charge: {e}")
        await query.answer("خطایی رخ داد.")

async def handle_conversation_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages during payment conversation"""
    logger.info(f"=== handle_conversation_message called ===")
    logger.info(f"User state: {context.user_data.get('state')}")
    logger.info(f"Full user_data: {context.user_data}")
    try:
        # Check if user wants to cancel
        if update.message.text and update.message.text.lower() in ['انصراف', 'لغو', 'cancel', 'انصراف میدم', 'لغو میکنم']:
            # Determine which type of cancellation based on state
            user_state = context.user_data.get('state')
            if user_state == ConversationStates.WALLET_AMOUNT_INPUT or user_state == ConversationStates.WALLET_RECEIPT_UPLOAD:
                await cancel_payment_process(update, context, "wallet")
            elif user_state == ConversationStates.PURCHASE_RECEIPT_UPLOAD:
                await cancel_payment_process(update, context, "purchase")
            elif user_state == ConversationStates.RENEWAL_RECEIPT_UPLOAD:
                await cancel_payment_process(update, context, "renewal")
            else:
                await cancel_payment_process(update, context, "payment")
            return ConversationHandler.END
        
        user_state = context.user_data.get('state')
        
        if user_state == ConversationStates.WALLET_AMOUNT_INPUT or not user_state:
            # Handle amount input
            return await handle_amount_input(update, context)
            
        elif user_state == ConversationStates.WALLET_RECEIPT_UPLOAD:
            # Handle receipt upload
            if update.message.photo or update.message.document:
                return await handle_wallet_receipt_upload(update, context)
            else:
                await update.message.reply_text(
                    "عکس رسید رو ارسال کن یا از دکمه انصراف استفاده کن.",
                    reply_markup=get_cancel_keyboard("wallet")
                )
                return ConversationStates.WALLET_RECEIPT_UPLOAD
                
        elif user_state == ConversationStates.PURCHASE_RECEIPT_UPLOAD:
            # Handle purchase receipt upload (from purchase flow)
            if update.message.photo:
                # Import here to avoid circular import
                from .purchase import handle_receipt_upload
                return await handle_receipt_upload(update, context)
            else:
                await update.message.reply_text(
                    "عکس رسید رو ارسال کن یا از دکمه انصراف استفاده کن.",
                    reply_markup=get_cancel_keyboard("purchase")
                )
                return ConversationStates.PURCHASE_RECEIPT_UPLOAD
                
        elif user_state == ConversationStates.RENEWAL_RECEIPT_UPLOAD:
            # Handle renewal receipt upload
            logger.info(f"In RENEWAL_RECEIPT_UPLOAD state, user_data: {context.user_data}")
            if update.message.photo or update.message.document:
                return await handle_renewal_receipt_upload(update, context)
            else:
                await update.message.reply_text(
                    "عکس رسید رو ارسال کن یا از دکمه انصراف استفاده کن.",
                    reply_markup=get_cancel_keyboard("renewal")
                )
                return ConversationStates.RENEWAL_RECEIPT_UPLOAD
        else:
            await update.message.reply_text("وضعیت نامعتبر. لطفاً دوباره شروع کنید.")
            return ConversationHandler.END
    
    except Exception as e:
        logger.error(f"Error in handle_conversation_message: {e}")
        await update.message.reply_text("خطایی رخ داده است.")
        return ConversationHandler.END

async def handle_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle wallet charge amount input"""
    try:
        amount_text = update.message.text.strip()
        
        # Check if user wants to cancel
        if amount_text.lower() in ['انصراف', 'لغو', 'cancel', 'انصراف میدم', 'لغو میکنم']:
            await cancel_payment_process(update, context, "wallet")
            return ConversationHandler.END
        
        # Validate amount
        try:
            amount = float(amount_text.replace(',', ''))
        except ValueError:
            await update.message.reply_text(
                "❌ مبلغ وارد شده نامعتبر است.\nلطفاً فقط عدد وارد کنی (مثال: 50000)",
                reply_markup=get_cancel_keyboard("wallet")
            )
            return ConversationStates.WALLET_AMOUNT_INPUT
        
        # Check amount limits
        if amount < settings.min_wallet_charge:
            await update.message.reply_text(
                f"❌ مبلغ کمتر از حداقل مجاز است.\nحداقل: {format_price(settings.min_wallet_charge)}",
                reply_markup=get_cancel_keyboard("wallet")
            )
            return ConversationStates.WALLET_AMOUNT_INPUT
        
        if amount > settings.max_wallet_charge:
            await update.message.reply_text(
                f"❌ مبلغ بیشتر از حداکثر مجاز است.\nحداکثر: {format_price(settings.max_wallet_charge)}",
                reply_markup=get_cancel_keyboard("wallet")
            )
            return ConversationStates.WALLET_AMOUNT_INPUT
        
        # Get user
        user = await db_manager.get_or_create_user(
            chat_id=update.effective_chat.id,
            username=update.effective_user.username
        )
        
        # Create wallet charge order
        order = await db_manager.create_order(
            user_id=user.id,
            order_type="wallet_charge",
            amount=amount
        )
        
        if not order:
            await update.message.reply_text(
                "❌ خطا در ایجاد سفارش!\nلطفاً دوباره تلاش کن.",
                reply_markup=get_cancel_keyboard("wallet")
            )
            return ConversationHandler.END
        
        # Store order info in context
        context.user_data['pending_wallet_order'] = order.id
        context.user_data['wallet_charge_amount'] = amount
        context.user_data['state'] = ConversationStates.WALLET_RECEIPT_UPLOAD
        
        text = f"""
💳 شارژ کیف پول

💰 مبلغ: {format_price(amount)}

💳 اطلاعات پرداخت:
{format_payment_info()}

📋 مراحل:
1️⃣ مبلغ رو به شماره کارت واریز کن 💰
2️⃣ عکس رسید رو ارسال کن 🖼
3️⃣ کیف پول شارژ می‌شه ✅

منتظر رسید شما هستیم 🤓
        """
        
        keyboard = get_cancel_keyboard("wallet")
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')
        
        return ConversationStates.WALLET_RECEIPT_UPLOAD
        
    except Exception as e:
        logger.error(f"Error in handle_amount_input: {e}")
        await update.message.reply_text("خطایی رخ داده است.")
        return ConversationHandler.END

async def handle_wallet_receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle wallet charge receipt upload"""
    try:
        # Get pending order
        order_id = context.user_data.get('pending_wallet_order')
        amount = context.user_data.get('wallet_charge_amount')
        
        if not order_id or not amount:
            await update.message.reply_text("خطا: سفارش یافت نشد. لطفاً دوباره تلاش کنید.")
            return ConversationHandler.END
        
        # Get user
        user = await db_manager.get_or_create_user(
            chat_id=update.effective_chat.id,
            username=update.effective_user.username
        )
        
        # Download and save receipt
        if update.message.photo:
            file_id = update.message.photo[-1].file_id  # Get highest resolution
            file = await context.bot.get_file(file_id)
            extension = "jpg"
        elif update.message.document:
            file_id = update.message.document.file_id
            file = await context.bot.get_file(file_id)
            extension = update.message.document.file_name.split('.')[-1] if update.message.document.file_name else "dat"
        else:
            await update.message.reply_text("لطفاً عکس یا فایل رسید را ارسال کنید.")
            return ConversationStates.WALLET_RECEIPT_UPLOAD
        
        # Create receipts directory
        os.makedirs("receipts", exist_ok=True)
        
        receipt_path = f"receipts/wallet_receipt_{order_id}_{file_id}.{extension}"
        await file.download_to_drive(receipt_path)
        
        # Update order with receipt
        db = db_manager.get_session()
        try:
            order = db.query(Order).filter_by(id=order_id).first()
            if order:
                order.receipt_path = receipt_path
                db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating order with receipt: {e}")
        finally:
            db.close()
        
        text = f"""
✅ رسید دریافت شد! 🎉

💰 مبلغ شارژ: {format_price(amount)}
📄 رسید: ثبت شده

⏳ کیف پول شما پس از تایید رسید توسط ادمین شارژ خواهد شد.

🕐 زمان تایید: معمولاً کمتر از 30 دقیقه

📞 در صورت سوال با پشتیبانی تماس بگیر 🤓
        """
        
        # Notify admins
        await notify_admins_wallet_charge(context, user, order_id, amount)
        
        keyboard = get_main_keyboard(user)
        await update.message.reply_text(text, reply_markup=keyboard)
        
        # Clear context
        context.user_data.pop('pending_wallet_order', None)
        context.user_data.pop('wallet_charge_amount', None)
        context.user_data.pop('state', None)
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in handle_wallet_receipt_upload: {e}")
        await update.message.reply_text("خطایی در پردازش رسید رخ داد.")
        return ConversationHandler.END

async def handle_renewal_receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle renewal receipt upload"""
    logger.info("=== handle_renewal_receipt_upload called ===")
    try:
        # Get pending order
        order_id = context.user_data.get('pending_renewal_order')
        
        if not order_id:
            await update.message.reply_text("خطا: سفارش یافت نشد. لطفاً دوباره تلاش کنید.")
            return ConversationHandler.END
        
        # Get user
        user = await db_manager.get_or_create_user(
            chat_id=update.effective_chat.id,
            username=update.effective_user.username
        )
        
        # Download and save receipt
        if update.message.photo:
            file_id = update.message.photo[-1].file_id  # Get highest resolution
            file = await context.bot.get_file(file_id)
            extension = "jpg"
        elif update.message.document:
            file_id = update.message.document.file_id
            file = await context.bot.get_file(file_id)
            extension = update.message.document.file_name.split('.')[-1] if update.message.document.file_name else "dat"
        else:
            await update.message.reply_text("لطفاً عکس یا فایل رسید را ارسال کنید.")
            return ConversationStates.RENEWAL_RECEIPT_UPLOAD
        
        # Create receipts directory
        os.makedirs("receipts", exist_ok=True)
        
        receipt_path = f"receipts/renewal_receipt_{order_id}_{file_id}.{extension}"
        await file.download_to_drive(receipt_path)
        
        # Update order with receipt and get order details
        success = False  # فرض اولیه
        db = db_manager.get_session()
        try:
            order = db.query(Order).filter_by(id=order_id).first()
            if order:
                order.receipt_path = receipt_path
                db.commit()
                
                # Get plan and account info
                from config.settings import SERVICE_PLANS
                plan = SERVICE_PLANS.get(order.plan_id, {})

                # Renew account immediately (before admin approval)
                if order.account_id:
                    from services.account_manager import account_manager
                    # Fetch account to obtain UUID
                    from database.models import Account as DBAccount
                    acc_obj = db.query(DBAccount).filter_by(id=order.account_id).first()
                    logger.info(f"Processing renewal for order {order_id}, account_id: {order.account_id}")
                    if acc_obj:
                        logger.info(f"Found account: {acc_obj.uuid}, email: {acc_obj.email}")
                        logger.info(f"Plan data: {plan}")
                        try:
                            renewal_result = await account_manager.renew_account(
                                acc_obj.uuid,
                                plan.get('data_limit', 0),
                                plan.get('expire_days', 0)
                            )
                            logger.info(f"Renewal result: {renewal_result}")
                            if renewal_result:
                                # موفق بود – سفارش را تایید (approved) علامت بزنیم
                                order.status = 'approved'
                                order.processed_at = datetime.utcnow()
                                db.commit()
                                success = True
                                logger.info(f"Order {order_id} marked as approved after successful renewal")
                            else:
                                success = False
                                logger.error(f"Renewal returned False for account {acc_obj.uuid}")
                        except Exception as e:
                            # Log but ادامه جریان برای تجربه آنی کاربر
                            logger.error(f"Error renewing account immediately: {e}")
                            success = False
                    else:
                        logger.error(f"Account not found for account_id: {order.account_id}")
                        success = False
                else:
                    logger.error(f"No account_id in order {order_id}")
                    success = False

                # Build user response text
                if success:
                    text = f"""
رسید ارسال شد!  🧾
سرویس شما با موفقیت تمدید شد! 🎉

📦 پلن: {plan.get('name', 'نامشخص')}
💰 مبلغ: {format_price(order.amount)}

🔄 حجم اضافه شده: {plan.get('data_limit', 0) // (1024**3) if plan.get('data_limit', 0) > 0 else 'نامحدود'} گیگابایت
📅 زمان اضافه شده: {plan.get('expire_days', 0)} روز

⏳ رسید شما در حال بررسی است:
• ✅ تایید: تمدید تایید نهایی می‌شود ✅
• ❌ رد : تمدید لغو خواهد شد ❌

📞 در صورت سوال با پشتیبانی تماس بگیر 🤓
                    """
                else:
                    text = (
                        "❌ خطا در تمدید سرویس\n\n"
                        "متأسفانه خطایی در تمدید سرویس رخ داد.\n"
                        "رسید شما ثبت شده و توسط ادمین بررسی خواهد شد 🤓"
                    )

                
        except Exception as e:
            db.rollback()
            logger.error(f"Error processing renewal receipt: {e}")
            text = "خطایی در پردازش رسید رخ داد."
        finally:
            db.close()
        
        # Always notify admins regardless of success
        logger.info(f"Notifying admins about renewal - success: {success}")
        if success:
            # برای تمدیدهای موفق، یک نوتیفیکیشن متفاوت بفرست
            await notify_admins_instant_renewal(context, user, order_id, plan)
        else:
            # فقط اگر تمدید خودکار موفق نبود
            await notify_admins_renewal_order(context, user, order_id)
        
        keyboard = get_main_keyboard(user)
        await update.message.reply_text(text, reply_markup=keyboard)
        
        # Clear context
        context.user_data.pop('pending_renewal_order', None)
        context.user_data.pop('state', None)
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in handle_renewal_receipt_upload: {e}")
        await update.message.reply_text("خطایی در پردازش رسید رخ داد.")
        return ConversationHandler.END

async def cancel_wallet_charge(query, user):
    """Cancel wallet charge process"""
    try:
        text = """
❌ شارژ کیف پول لغو شد ❌

عملیات شارژ کیف پول لغو شد.
میتونی هر زمان دوباره اقدام کنی 🤓
        """
        
        keyboard = get_main_keyboard(user)
        await query.edit_message_text(text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in cancel_wallet_charge: {e}")
        await query.answer("خطایی رخ داد.")

async def notify_admins_wallet_charge(context, user, order_id, amount):
    """Notify admins about wallet charge request"""
    try:
        admin_text = f"""
💳 درخواست شارژ کیف پول

👤 کاربر: {escape_markdown(user.username) if user.username else 'N/A'} (ID: {user.chat_id})
💰 مبلغ: {format_price(amount)}

📄 رسید: دریافت شده
⏳ وضعیت: در انتظار بررسی

برای مدیریت از دستور /admin استفاده کن 🤓
        """
        
        # Send to all admins
        for admin_id in settings.bot.ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Error sending notification to admin {admin_id}: {e}")
    
    except Exception as e:
        logger.error(f"Error in notify_admins_wallet_charge: {e}")

async def notify_admins_renewal_order(context, user, order_id):
    """Notify admins about renewal order"""
    try:
        admin_text = f"""
♻️ درخواست تمدید سرویس

👤 کاربر: {escape_markdown(user.username) if user.username else 'N/A'} (ID: {user.chat_id})
📄 رسید: دریافت شده
⏳ وضعیت: در انتظار بررسی

برای مدیریت از دستور /admin استفاده کن 🤓
        """
        
        # Send to all admins
        logger.info(f"Admin IDs configured: {settings.bot.ADMIN_IDS}")
        if not settings.bot.ADMIN_IDS:
            logger.error("No admin IDs configured in settings!")
            return
            
        for admin_id in settings.bot.ADMIN_IDS:
            try:
                logger.info(f"Sending renewal notification to admin {admin_id}")
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_text,
                    parse_mode=ParseMode.MARKDOWN
                )
                logger.info(f"Successfully sent renewal notification to admin {admin_id}")
            except Exception as e:
                logger.error(f"Error sending renewal notification to admin {admin_id}: {e}")
    
    except Exception as e:
        logger.error(f"Error in notify_admins_renewal_order: {e}")

async def notify_admins_instant_renewal(context, user, order_id, plan):
    """Notify admins about instant renewal (already processed)"""
    try:
        logger.info(f"notify_admins_instant_renewal called with user ID: {user.id}, chat_id: {user.chat_id}")
        
        admin_text = f"""
✅ تمدید فوری انجام شد

👤 کاربر: {escape_markdown(user.username) if user.username else 'N/A'} (ID: {user.chat_id})
📦 پلن: {plan.get('name', 'نامشخص')}
🔄 حجم: {plan.get('data_limit', 0) // (1024**3) if plan.get('data_limit', 0) > 0 else 'نامحدود'} گیگابایت
📅 زمان: {plan.get('expire_days', 0)} روز
💰 مبلغ: {format_price(plan.get('price', 0))}
📄 رسید: دریافت شده
✅ وضعیت: تمدید فوری انجام شد

📋 سفارش: {order_id}

⚠️ توجه: این تمدید به‌صورت خودکار انجام شده و نیازی به تایید نداره 🔥
        """
        
        # Check admin IDs
        from config.settings import ADMIN_IDS
        admin_ids = ADMIN_IDS if ADMIN_IDS else getattr(settings.bot, 'ADMIN_IDS', [])
        
        logger.info(f"Admin IDs for instant renewal: {admin_ids}")
        if not admin_ids:
            logger.error("No admin IDs configured for instant renewal!")
            return
            
        success_count = 0
        for admin_id in admin_ids:
            try:
                logger.info(f"Sending instant renewal notification to admin {admin_id}")
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_text,
                    parse_mode=ParseMode.MARKDOWN
                )
                success_count += 1
                logger.info(f"Successfully sent instant renewal notification to admin {admin_id}")
            except Exception as e:
                logger.error(f"Error sending instant renewal notification to admin {admin_id}: {e}")
        
        logger.info(f"Sent instant renewal notifications to {success_count}/{len(admin_ids)} admins")
    
    except Exception as e:
        logger.error(f"Error in notify_admins_instant_renewal: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}") 

async def cancel_payment_process(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str = "payment"):
    """Cancel payment process and return to main menu"""
    try:
        # Get user
        user = await db_manager.get_or_create_user(
            chat_id=update.effective_chat.id,
            username=update.effective_user.username
        )
        
        # Delete any pending orders from database
        pending_order_id = context.user_data.get('pending_order')
        pending_wallet_order_id = context.user_data.get('pending_wallet_order')
        pending_renewal_order_id = context.user_data.get('pending_renewal_order')
        
        if pending_order_id:
            try:
                await db_manager.delete_order(pending_order_id)
                logger.info(f"Deleted pending order {pending_order_id}")
            except Exception as e:
                logger.error(f"Error deleting pending order {pending_order_id}: {e}")
        
        if pending_wallet_order_id:
            try:
                await db_manager.delete_order(pending_wallet_order_id)
                logger.info(f"Deleted pending wallet order {pending_wallet_order_id}")
            except Exception as e:
                logger.error(f"Error deleting pending wallet order {pending_wallet_order_id}: {e}")
        
        if pending_renewal_order_id:
            try:
                await db_manager.delete_order(pending_renewal_order_id)
                logger.info(f"Deleted pending renewal order {pending_renewal_order_id}")
            except Exception as e:
                logger.error(f"Error deleting pending renewal order {pending_renewal_order_id}: {e}")
        
        # Clear any pending order data
        context.user_data.pop('pending_order', None)
        context.user_data.pop('pending_wallet_order', None)
        context.user_data.pop('pending_renewal_order', None)
        context.user_data.pop('selected_plan', None)
        context.user_data.pop('wallet_charge_amount', None)
        context.user_data.pop('state', None)
        
        # Delete the current message if it's a callback query
        if update.callback_query:
            try:
                await update.callback_query.delete_message()
            except Exception as e:
                logger.warning(f"Could not delete message: {e}")
        # If it's a text message, we can't delete it, but we can send a new message
        
        # Send new main menu message
        welcome_text = f"""
🏠 منوی اصلی

💰 موجودی کیف پول: {user.wallet_balance:,.0f} تومان
🎁 هدایا: {user.gift_data // (1024**3) if user.gift_data > 0 else 0}GB - {user.gift_days} روز

گزینه مورد نظرت رو انتخاب کن: 😊
        """
        
        keyboard = get_main_keyboard(user)
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=welcome_text,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in cancel_payment_process: {e}")
        # Fallback: try to send main menu anyway
        try:
            user = await db_manager.get_or_create_user(
                chat_id=update.effective_chat.id,
                username=update.effective_user.username
            )
            keyboard = get_main_keyboard(user)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="منوی اصلی:",
                reply_markup=keyboard
            )
        except Exception as fallback_error:
            logger.error(f"Fallback error in cancel_payment_process: {fallback_error}")

async def test_cancel_functionality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test function to verify cancel functionality works"""
    try:
        # Create a test order
        user = await db_manager.get_or_create_user(
            chat_id=update.effective_chat.id,
            username=update.effective_user.username
        )
        
        test_order = await db_manager.create_order(
            user_id=user.id,
            order_type="test",
            amount=1000
        )
        
        if test_order:
            context.user_data['pending_order'] = test_order.id
            await update.message.reply_text(f"Test order created: {test_order.id}")
            
            # Test cancel
            await cancel_payment_process(update, context, "test")
            await update.message.reply_text("Cancel test completed")
        else:
            await update.message.reply_text("Failed to create test order")
            
    except Exception as e:
        logger.error(f"Test error: {e}")
        await update.message.reply_text(f"Test error: {e}") 