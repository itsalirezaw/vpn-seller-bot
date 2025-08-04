"""Renewal flow (behaves like purchase but applies to an existing account)

All callback prefixes are `renew_` or `renewal_`.
"""

import logging
import os
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from database.database import db_manager
from database.models import Order
from services.account_manager import account_manager
from bot.keyboards import (
    get_payment_method_keyboard,
    get_cancel_keyboard,
    get_main_keyboard,
)
from bot.states import ConversationStates
from bot.utils import format_price
from config.settings import SERVICE_PLANS, settings
from bot.handlers.admin import escape_markdown
from bot.handlers.payment import notify_admins_instant_renewal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# entry-point handler (similar to purchase_handler)
# ---------------------------------------------------------------------------

async def renewal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main renewal conversation handler."""
    try:
        # ------------------------------------------------------------------
        # CallbackQuery section (buttons)
        # ------------------------------------------------------------------
        if update.callback_query:
            query = update.callback_query
            await query.answer()

            # Ensure we have user object
            user = await db_manager.get_or_create_user(
                chat_id=update.effective_chat.id,
                username=update.effective_user.username,
            )

            # Entry 0.a – user pressed main "renew_service" button
            if query.data == "renew_service":
                from bot.handlers.services import show_renew_services_list
                await show_renew_services_list(query, user)
                return ConversationHandler.END

            # Entry 0.b – direct account button:  renew_<accountId>
            if query.data.startswith("renew_") and query.data.count("_") == 1:
                parts = query.data.split("_")
                if len(parts) == 2 and parts[1].isdigit():
                    account_id = int(parts[1])
                    context.user_data.clear()
                    context.user_data["renew_account_id"] = account_id
                    await _show_plans(query, account_id)
                    return ConversationStates.RENEWAL_PLAN_SELECTION
                # if not digit fall through to unknown

            # Step 1 – plan chosen: renewal_plan_<planId>
            if query.data.startswith("renewal_plan_"):
                plan_id = query.data[len("renewal_plan_") :]
                context.user_data["renew_plan_id"] = plan_id
                await _confirm_plan(query, plan_id)
                return ConversationStates.RENEWAL_PAYMENT_METHOD

            # Step 2 – payment method chosen: renewal_payment_<wallet|direct>
            if query.data.startswith("renewal_payment_"):
                payment_method = query.data.split("_")[-1]
                return await _handle_payment_method(query, context, user, payment_method)

            # Confirm wallet renewal
            if query.data == "confirm_renewal_wallet":
                return await _handle_wallet_confirmation(query, context, user)
            
            # Cancel
            if query.data == "cancel_renewal":
                await _cancel_flow(update, context, user)
                return ConversationHandler.END

        # ------------------------------------------------------------------
        # Photo/document message – receipt upload
        # ------------------------------------------------------------------
        elif context.user_data.get("state") == ConversationStates.RENEWAL_RECEIPT_UPLOAD:
            logger.info("=== renewal_handler: expecting receipt upload ===")
            logger.info(f"user_data: {context.user_data}")
            
            # Check if user wants to cancel via text message
            if update.message.text and update.message.text.lower() in ['انصراف', 'لغو', 'cancel', 'انصراف میدم', 'لغو میکنم']:
                await _cancel_flow(update, context, user)
                return ConversationHandler.END
            
            if update.message.photo or update.message.document:
                logger.info("Photo/document received, calling _handle_receipt_upload")
                return await _handle_receipt_upload(update, context)
            logger.info("No photo/document in message")
            await update.message.reply_text(
                "لطفاً عکس رسید را ارسال کنید یا از دکمه انصراف استفاده کنید.",
                reply_markup=get_cancel_keyboard("renewal"),
            )
            return ConversationStates.RENEWAL_RECEIPT_UPLOAD

    except Exception as e:
        logger.error(f"renewal_handler error: {e}")
    return ConversationHandler.END

# ---------------------------------------------------------------------------
# Helper step functions
# ---------------------------------------------------------------------------

async def _show_plans(query, account_id: int):
    """Show list of plans for renewal."""
    # Get user to check for pending orders
    user = await db_manager.get_or_create_user(
        chat_id=query.from_user.id,
        username=query.from_user.username,
    )
    
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
    
    keyboard = [
        [
            InlineKeyboardButton(
                f"{plan['name']} - {format_price(plan['price'])}",
                callback_data=f"renewal_plan_{plan_id}",
            )
        ]
        for plan_id, plan in SERVICE_PLANS.items()
    ]
    keyboard.append(
        [InlineKeyboardButton("🔙 بازگشت", callback_data="cancel_renewal")]
    )
    await query.edit_message_text(
        f"🔄 تمدید سرویس\n\nاکانت # {account_id}\n\nپلن را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _confirm_plan(query, plan_id: str):
    plan = SERVICE_PLANS.get(plan_id)
    if not plan:
        await query.answer("پلن نامعتبر!")
        return
    text = (
        f"📦 پلن: {plan['name']}\n"
        f"💾 حجم: {'نامحدود' if plan['data_limit']==0 else str(plan['data_limit']//(1024**3))+' GB'}\n"
        f"⏳ مدت: {plan['expire_days']} روز\n\n"
        "روش پرداخت را انتخاب کنید:"
    )
    kb = get_payment_method_keyboard(prefix="renewal_payment_")
    await query.edit_message_text(text, reply_markup=kb)


async def _handle_payment_method(query, ctx, user, payment_method: str):
    # Check if user has pending orders before processing payment
    pending_orders = await db_manager.get_pending_orders(user.id)
    
    if pending_orders:
        text = """
⚠️ سفارش در انتظار

 یک سفارش در انتظار تایید داری.

لطفاً تا تایید سفارش قبلی، سفارش جدید ثبت نکن.
        """
        keyboard = get_main_keyboard(user)
        await query.edit_message_text(text, reply_markup=keyboard)
        return ConversationHandler.END
    
    plan_id = ctx.user_data.get("renew_plan_id")
    if not plan_id or plan_id not in SERVICE_PLANS:
        await query.answer("پلن یافت نشد، مجدداً انتخاب کنید!")
        return ConversationHandler.END
    plan = SERVICE_PLANS[plan_id]

    # Wallet payment ------------------------------------------------------
    if payment_method == "wallet":
        if user.wallet_balance < plan["price"]:
            deficit = plan["price"] - user.wallet_balance
            text_insufficient = f"""
❌ موجودی کیف پول کافی نیست!

💰 قیمت پلن: {format_price(plan['price'])}
💳 موجودی شما: {format_price(user.wallet_balance)}
💸 کمبود: {format_price(deficit)}

برای تمدید، ابتدا کیف پول خود را شارژ کنید یا روش پرداخت کارت به کارت را انتخاب کنید.
            """
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard_insufficient = InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 پرداخت مستقیم", callback_data="renewal_payment_direct")],
                [InlineKeyboardButton("👝 شارژ کیف پول", callback_data="wallet_charge")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data=f"renew_{ctx.user_data['renew_account_id']}")]
            ])
            await query.edit_message_text(text_insufficient, reply_markup=keyboard_insufficient)
            return ConversationStates.RENEWAL_PAYMENT_METHOD
        
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
        
        # Store plan info for confirmation
        ctx.user_data["renewal_confirm_plan_id"] = plan_id
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ تایید و تمدید", callback_data="confirm_renewal_wallet")],
            [InlineKeyboardButton("🔙 انصراف", callback_data="cancel_renewal")]
        ])
        
        await query.edit_message_text(text, reply_markup=keyboard)
        return ConversationStates.RENEWAL_PAYMENT_METHOD

    # Direct card-to-card payment ----------------------------------------
    account_id = ctx.user_data["renew_account_id"]
    order = await db_manager.create_order(
        user_id=user.id,
        order_type="renewal",
        amount=plan["price"],
        plan_id=plan_id,
        account_id=account_id,
    )
    ctx.user_data.update(
        {
            "pending_renewal_order": order.id,
            "state": ConversationStates.RENEWAL_RECEIPT_UPLOAD,
        }
    )
    from config.payment_utils import format_payment_info
    text = (
        f"💰 پرداخت کارت به کارت\n\n"
        f"مبلغ: {format_price(plan['price'])}\n\n"
        f"{format_payment_info()}\n\n"
        "عکس رسید را ارسال کنید."
    )
    await query.edit_message_text(
        text, reply_markup=get_cancel_keyboard("renewal"), parse_mode="Markdown"
    )
    return ConversationStates.RENEWAL_RECEIPT_UPLOAD


async def _handle_receipt_upload(update: Update, ctx):
    order_id = ctx.user_data.get("pending_renewal_order")
    plan_id = ctx.user_data.get("renew_plan_id")
    account_id = ctx.user_data.get("renew_account_id")
    user = await db_manager.get_or_create_user(update.effective_chat.id, update.effective_user.username)

    if not (order_id and plan_id and account_id):
        await update.message.reply_text("خطا، لطفاً از ابتدا تمدید را شروع کنید.")
        return ConversationHandler.END

    # Save receipt file ---------------------------------------------------
    file_id = (update.message.photo[-1].file_id if update.message.photo else update.message.document.file_id)
    file = await ctx.bot.get_file(file_id)
    os.makedirs("receipts", exist_ok=True)
    path = f"receipts/renew_{order_id}_{file_id}.jpg"
    await file.download_to_drive(path)

    db = db_manager.get_session()
    try:
        order: Optional[Order] = db.query(Order).get(order_id)
        if order:
            order.receipt_path = path
            db.commit()
    finally:
        db.close()

    # Apply renewal immediately -----------------------------------------
    success = await _apply_renewal(account_id, plan_id)

    plan = SERVICE_PLANS[plan_id]
    txt = (
        "✅ تمدید با موفقیت انجام شد! 🎉" if success else "❌ خطا در تمدید؛ رسید برای بررسی ادمین ذخیره شد."
    )
    await update.message.reply_text(txt, reply_markup=get_main_keyboard(user))

    # Notify admins (instant)
    try:
        logger.info(f"Attempting to notify admins about renewal order {order_id}")
        await notify_admins_instant_renewal(ctx, user, order_id, plan)
        logger.info(f"Admin notification sent for renewal order {order_id}")
    except Exception as e:
        logger.error(f"Failed to notify admins about renewal order {order_id}: {e}")
    ctx.user_data.clear()
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

async def _apply_renewal(account_id: int, plan_id: str) -> bool:
    """Call AccountManager.renew_account and return True on success."""
    from database.models import Account as DBAccount
    acc = await account_manager.get_account_by_id(account_id)
    if not acc:
        return False
    plan = SERVICE_PLANS[plan_id]
    return await account_manager.renew_account(
        acc.uuid, plan["data_limit"], plan["expire_days"]
    )


async def _send_wallet_result(query, user, plan, success: bool):
    if success:
        txt = f"""
✅ تمدید موفق!

سرویس شما با موفقیت تمدید شد! 🎉

📦 پلن: {plan['name']}
💰 مبلغ پرداختی: {format_price(plan['price'])}
💳 پرداخت از: کیف پول

🔄 حجم اضافه شده: {'نامحدود' if plan['data_limit'] == 0 else f"{plan['data_limit'] // (1024**3)} گیگابایت"}
📅 زمان اضافه شده: {plan['expire_days']} روز

💰 موجودی باقی‌مانده: {format_price(user.wallet_balance - plan['price'])}

🔧 برای مشاهده جزئیات سرویس به "مشاهده سرویس‌ها" مراجعه کنید.
        """
    else:
        # refund
        await db_manager.update_user_wallet(user.id, plan["price"])
        txt = "❌ خطا در تمدید سرویس. مبلغ به کیف پول شما بازگردانده شد."
    
    await query.edit_message_text(txt, reply_markup=get_main_keyboard(user))


async def _handle_wallet_confirmation(query, ctx, user):
    """Handle wallet payment confirmation"""
    plan_id = ctx.user_data.get("renewal_confirm_plan_id") or ctx.user_data.get("renew_plan_id")
    account_id = ctx.user_data.get("renew_account_id")
    
    if not plan_id or not account_id:
        await query.answer("خطا در تایید، لطفاً دوباره تلاش کنید.")
        return ConversationHandler.END
    
    plan = SERVICE_PLANS[plan_id]
    
    # Check wallet balance again
    if user.wallet_balance < plan["price"]:
        await query.answer("موجودی کافی نیست")
        return ConversationHandler.END
    
    logger.info(f"=== WALLET RENEWAL START (CONFIRMED) ===")
    logger.info(f"User: {user.id}, Account: {account_id}, Plan: {plan_id}")
    logger.info(f"Plan details: {plan}")
    
    # Deduct from wallet
    await db_manager.update_user_wallet(user.id, -plan["price"])
    logger.info(f"Wallet updated - deducted {plan['price']}")
    
    # Apply renewal
    success = await _apply_renewal(account_id, plan_id)
    logger.info(f"Renewal result: {success}")
    logger.info(f"=== WALLET RENEWAL END (CONFIRMED) ===")
    
    # Send result
    await _send_wallet_result(query, user, plan, success)
    
    # Clear context
    ctx.user_data.clear()
    return ConversationHandler.END


async def _cancel_flow(update, context, user):
    # Import the cancel function from payment handler
    from .payment import cancel_payment_process
    
    await cancel_payment_process(update, context, "renewal")
