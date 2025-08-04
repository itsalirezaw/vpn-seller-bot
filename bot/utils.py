"""
Bot utility functions
"""

from config.settings import settings

def format_data_size(bytes_size: int) -> str:
    """Format data size in human readable format"""
    if bytes_size == 0:
        return "نامحدود"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(bytes_size)
    unit_index = 0
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    return f"{size:.1f} {units[unit_index]}"

def format_usage_size(bytes_size: int) -> str:
    """Format usage data size in human readable format (0 = 0 B, not unlimited)"""
    if bytes_size == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(bytes_size)
    unit_index = 0
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    return f"{size:.1f} {units[unit_index]}"

def format_price(price: float) -> str:
    """Format price in Iranian Toman"""
    return f"{price:,.0f} تومان"

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in settings.bot.ADMIN_IDS 