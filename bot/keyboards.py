from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Optional
from database.models import User, Account
from config.settings import SERVICE_PLANS

def get_main_keyboard(user: User) -> InlineKeyboardMarkup:
    """Get main menu keyboard"""
    keyboard = [
        [InlineKeyboardButton("🛒 خرید سرویس", callback_data="purchase_new")],
        [InlineKeyboardButton("♻️ تمدید سرویس", callback_data="renew_service")],
        [InlineKeyboardButton("👀 مشاهده سرویس‌ها", callback_data="services_list")],
        [InlineKeyboardButton("👝 شارژ کیف پول", callback_data="wallet_charge")],
    ]
    
    # Add invite and test account buttons
    keyboard.append([
        InlineKeyboardButton("🎁 دعوت دوستان", callback_data="invite_system"),
        InlineKeyboardButton("🌐 اکانت تست", callback_data="test_account")
    ])
    
    # Add wallet balance info
    balance_text = f"💰 موجودی: {user.wallet_balance:,.0f} تومان"
    keyboard.append([InlineKeyboardButton(balance_text, callback_data="wallet_info")])
    
    return InlineKeyboardMarkup(keyboard)

def get_services_keyboard(accounts: List[Account]) -> InlineKeyboardMarkup:
    """Get services list keyboard"""
    keyboard = []
    
    for account in accounts:
        # Format account status
        status = "🟢 فعال" if account.is_active else "🔴 غیرفعال"
        if account.is_expired:
            status = "⏰ منقضی"
        elif account.total_data_limit > 0 and account.total_used_data >= account.total_data_limit:
            status = "📵 تمام شده"
        
        button_text = f"{account.email[:15]}... - {status}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"services_view_{account.id}")])
    
    # Add back button
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(keyboard)

def get_account_detail_keyboard(account: Account) -> InlineKeyboardMarkup:
    """Get account detail keyboard"""
    keyboard = []
    
    # Config and QR buttons
    keyboard.append([
        InlineKeyboardButton("📄 کانفیگ", callback_data=f"services_config_{account.id}"),
        InlineKeyboardButton("📱 QR کد", callback_data=f"services_qr_{account.id}")
    ])
    
    # Tutorial button (full width)
    keyboard.append([
        InlineKeyboardButton("📚 آموزش", callback_data=f"services_tutorial_{account.id}")
    ])
    
    # Renewal button (if account is active)
    if account.is_active:
        keyboard.append([InlineKeyboardButton("🔄 تمدید", callback_data=f"renew_{account.id}")])

    # Delete service button
    keyboard.append([InlineKeyboardButton("🗑️ حذف سرویس", callback_data=f"services_delete_{account.id}")])
 
    # Back buttons
    keyboard.append([
        InlineKeyboardButton("🔙 بازگشت", callback_data="services_list"),
        InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def get_time_period_keyboard() -> InlineKeyboardMarkup:
    """Get time period selection keyboard"""
    keyboard = [
        [InlineKeyboardButton("📅 یک ماهه", callback_data="period_1m")],
        [InlineKeyboardButton("📅 سه ماهه", callback_data="period_3m")], 
        [InlineKeyboardButton("📅 شش ماهه", callback_data="period_6m")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_data_plans_keyboard(period: str) -> InlineKeyboardMarkup:
    """Get data plans keyboard for specific time period"""
    keyboard = []
    
    # Filter plans by period
    period_plans = {k: v for k, v in SERVICE_PLANS.items() if v.get('period') == period}
    
    for plan_id, plan_info in period_plans.items():
        data_gb = plan_info['data_limit'] // (1024**3)
        button_text = f"{data_gb} گیگ - {plan_info['price']:,.0f} تومان"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"plan_{plan_id}")])
    
    # Back button
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="purchase_new")])
    
    return InlineKeyboardMarkup(keyboard)

def get_purchase_plans_keyboard() -> InlineKeyboardMarkup:
    """Legacy function - redirects to time period selection"""
    return get_time_period_keyboard()

def get_payment_method_keyboard(prefix: str = "payment_") -> InlineKeyboardMarkup:
    """Return payment method keyboard.
    prefix determines callback_data. e.g. prefix="renewal_payment_" → renewal_payment_wallet
    """
    back_cb = "cancel_renewal" if prefix.startswith("renewal") else "cancel_purchase"
    keyboard = [
        [InlineKeyboardButton("👝 پرداخت از کیف پول", callback_data=f"{prefix}wallet")],
        [InlineKeyboardButton("💳 پرداخت مستقیم", callback_data=f"{prefix}direct")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data=back_cb)]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_config_display_keyboard(account_id: int) -> InlineKeyboardMarkup:
    """Get config display keyboard – only provides a back button (no bulk copy for VMess links)"""
    keyboard = [
        [InlineKeyboardButton("🔙 بازگشت", callback_data=f"services_view_{account_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_invite_keyboard(user: User) -> InlineKeyboardMarkup:
    """Get invite system keyboard"""
    keyboard = []
    
    # Show invite statistics
    keyboard.append([InlineKeyboardButton("📊 آمار دعوت", callback_data="invite_stats")])
    
    # Share invite link
    keyboard.append([InlineKeyboardButton("🔗 اشتراک لینک", callback_data="invite_share")])
    
    # Use gifts (if available)
    if user.gift_data > 0 or user.gift_days > 0:
        gift_text = f"🎁 استفاده از هدایا ({user.gift_data // (1024**3)}GB, {user.gift_days} روز)"
        keyboard.append([InlineKeyboardButton(gift_text, callback_data="invite_use_gifts")])
    
    # Back button
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(keyboard)

def get_gift_account_selection_keyboard(accounts: List[Account]) -> InlineKeyboardMarkup:
    """Get gift account selection keyboard"""
    keyboard = []
    
    for account in accounts:
        if account.is_active:
            button_text = f"{account.email[:15]}... - {'فعال' if account.is_active else 'غیرفعال'}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"gift_account_{account.id}")])
    
    # Back button
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="invite_system")])
    
    return InlineKeyboardMarkup(keyboard)

def get_test_account_keyboard(can_use_test: bool) -> InlineKeyboardMarkup:
    """Get test account keyboard"""
    keyboard = []
    
    if can_use_test:
        keyboard.append([InlineKeyboardButton("🌐 دریافت اکانت تست", callback_data="test_create")])
    else:
        keyboard.append([InlineKeyboardButton("❌ قبلاً استفاده شده", callback_data="test_used")])
    
    # Test account info
    keyboard.append([InlineKeyboardButton("ℹ️ اطلاعات اکانت تست", callback_data="test_info")])
    
    # Back button
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Get admin panel keyboard"""
    keyboard = [
        [InlineKeyboardButton("🖥️ مدیریت سرورها", callback_data="admin_servers")],
        [InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin_users")],
        [InlineKeyboardButton("💳 مدیریت سفارشات", callback_data="admin_orders")],
        [InlineKeyboardButton("⚙️ مدیریت تمپلیت‌ها", callback_data="admin_templates")],
        [InlineKeyboardButton("📊 آمار سیستم", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]
    ]
    
    return InlineKeyboardMarkup(keyboard)

def get_admin_orders_keyboard() -> InlineKeyboardMarkup:
    """Get admin orders management keyboard"""
    keyboard = [
        [InlineKeyboardButton("⏳ سفارشات در انتظار", callback_data="admin_pending_orders")],
        [InlineKeyboardButton("✅ سفارشات تایید شده", callback_data="admin_orders_approved")],
        [InlineKeyboardButton("❌ سفارشات رد شده", callback_data="admin_orders_rejected")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_main_menu")]
    ]
    
    return InlineKeyboardMarkup(keyboard)

def get_order_approval_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Get order approval keyboard"""
    keyboard = [
        [InlineKeyboardButton("✅ تایید", callback_data=f"admin_approve_{order_id}")],
        [InlineKeyboardButton("❌ رد", callback_data=f"admin_reject_{order_id}")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_orders_pending")]
    ]
    
    return InlineKeyboardMarkup(keyboard)

def get_renewal_plans_keyboard(account_id: int) -> InlineKeyboardMarkup:
    """Get renewal plans keyboard"""
    keyboard = []
    
    for plan_id, plan_info in SERVICE_PLANS.items():
        button_text = f"{plan_info['name']} - {plan_info['price']:,.0f} تومان"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"renewal_plan_{account_id}_{plan_id}")])
    
    # Back button
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"services_view_{account_id}")])
    
    return InlineKeyboardMarkup(keyboard)

def get_confirmation_keyboard(action: str, item_id: str) -> InlineKeyboardMarkup:
    """Get confirmation keyboard"""
    keyboard = [
        [InlineKeyboardButton("✅ تایید", callback_data=f"confirm_{action}_{item_id}")],
        [InlineKeyboardButton("❌ انصراف", callback_data=f"cancel_{action}_{item_id}")]
    ]
    
    return InlineKeyboardMarkup(keyboard)

def get_cancel_keyboard(action: str) -> InlineKeyboardMarkup:
    """Get cancel keyboard"""
    keyboard = [
        [InlineKeyboardButton("❌ لغو پرداخت", callback_data=f"cancel_{action}")],
    ]
    
    return InlineKeyboardMarkup(keyboard)

def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    """Get main admin panel keyboard"""
    keyboard = [
        [InlineKeyboardButton("📋 مدیریت سفارشات", callback_data="admin_orders_menu")],
        [InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin_users_menu")],
        [InlineKeyboardButton("🖥️ مدیریت سرورها", callback_data="admin_servers_menu")],
        [InlineKeyboardButton("📊 آمار سیستم", callback_data="admin_system_stats")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]
    ]
    
    return InlineKeyboardMarkup(keyboard)

def get_admin_users_keyboard() -> InlineKeyboardMarkup:
    """Get admin users management keyboard"""
    keyboard = [
        [InlineKeyboardButton("📊 آمار کاربران", callback_data="admin_user_stats")],
        [InlineKeyboardButton("🔍 جستجوی کاربر", callback_data="admin_search_user")],
        [InlineKeyboardButton("🚫 لیست کاربران مسدود", callback_data="admin_banned_users")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_main_menu")]
    ]
    
    return InlineKeyboardMarkup(keyboard)

def get_admin_servers_keyboard() -> InlineKeyboardMarkup:
    """Get admin servers management keyboard"""
    keyboard = [
        [InlineKeyboardButton("📊 وضعیت سرورها", callback_data="admin_server_status")],
        [InlineKeyboardButton("➕ افزودن سرور", callback_data="admin_add_server")],
        [InlineKeyboardButton("🔧 مدیریت سرورها", callback_data="admin_manage_servers")],
        [InlineKeyboardButton("🔄 بررسی سلامت", callback_data="admin_health_check")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_main_menu")]
    ]
    
    return InlineKeyboardMarkup(keyboard) 

# ---------------------------------------------------------------------------
# Renewal helpers
# ---------------------------------------------------------------------------

def get_renewal_time_period_keyboard(account_id: int) -> InlineKeyboardMarkup:
    """Get time period selection keyboard for renewal"""
    keyboard = [
        [InlineKeyboardButton("📅 یک ماهه", callback_data=f"renewal_period_1m")],
        [InlineKeyboardButton("📅 سه ماهه", callback_data=f"renewal_period_3m")], 
        [InlineKeyboardButton("📅 شش ماهه", callback_data=f"renewal_period_6m")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data=f"services_view_{account_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_renewal_data_plans_keyboard(account_id: int, period: str) -> InlineKeyboardMarkup:
    """Get data plans keyboard for specific time period in renewal"""
    keyboard = []
    
    # Filter plans by period
    period_plans = {k: v for k, v in SERVICE_PLANS.items() if v.get('period') == period}
    
    for plan_id, plan_info in period_plans.items():
        data_gb = plan_info['data_limit'] // (1024**3)
        button_text = f"{data_gb} گیگ - {plan_info['price']:,.0f} تومان"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"renewal_plan_{account_id}_{plan_id}")])
    
    # Back button
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"renew_{account_id}")])
    
    return InlineKeyboardMarkup(keyboard)

def get_renew_accounts_keyboard(accounts: List[Account]) -> InlineKeyboardMarkup:
    """Keyboard for selecting an account to renew"""
    keyboard: List[List[InlineKeyboardButton]] = []

    for account in accounts:
        # Human-readable status similar to get_services_keyboard
        status = "🟢 فعال" if account.is_active else "🔴 غیرفعال"
        if account.is_expired:
            status = "⏰ منقضی"
        elif account.total_data_limit > 0 and account.total_used_data >= account.total_data_limit:
            status = "📵 تمام شده"

        button_text = f"{account.email[:15]}... - {status}"
        # We reuse the same renew_<id> callback that services_handler already expects
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"renew_{account.id}")])

    # Back button
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(keyboard) 