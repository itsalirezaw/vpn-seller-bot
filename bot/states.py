from enum import IntEnum

class ConversationStates(IntEnum):
    """Conversation states for the bot"""
    
    # Purchase flow states
    PURCHASE_PLAN_SELECTION = 1
    PURCHASE_PAYMENT_METHOD = 2
    PURCHASE_RECEIPT_UPLOAD = 3
    
    # Wallet charge flow states
    WALLET_AMOUNT_INPUT = 10
    WALLET_RECEIPT_UPLOAD = 11
    
    # Renewal flow states
    RENEWAL_PLAN_SELECTION = 20
    RENEWAL_PAYMENT_METHOD = 21
    RENEWAL_RECEIPT_UPLOAD = 22
    
    # Admin flow states
    ADMIN_SERVER_MANAGEMENT = 30
    ADMIN_USER_MANAGEMENT = 31
    ADMIN_ORDER_MANAGEMENT = 32
    ADMIN_TEMPLATE_MANAGEMENT = 33
    
    # Gift system states
    GIFT_ACCOUNT_SELECTION = 40
    GIFT_AMOUNT_INPUT = 41
    
    # Support states
    SUPPORT_MESSAGE_INPUT = 50

class AdminStates(IntEnum):
    """Admin conversation states"""
    
    # Main admin menu
    MAIN_MENU = 100
    
    # Order management states
    ORDERS_MENU = 110
    PENDING_ORDERS = 111
    REVIEW_ORDER = 112
    ADD_ORDER_NOTE = 113
    
    # User management states
    USERS_MENU = 120
    USER_SEARCH = 121
    USER_DETAILS = 122
    USER_BAN = 123
    
    # Server management states
    SERVERS_MENU = 130
    SERVER_ADD = 131
    SERVER_EDIT = 132
    SERVER_DELETE = 133
    
    # System management states
    SYSTEM_STATS = 140
    SYSTEM_CONFIG = 141
    SYSTEM_BACKUP = 142 