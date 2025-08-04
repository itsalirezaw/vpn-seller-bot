#!/usr/bin/env python3
"""
VPN Bot Startup Script
This script helps you configure and run the VPN bot step by step.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_file_exists(file_path):
    """Check if a file exists"""
    return Path(file_path).exists()

def check_env_file():
    """Check if .env file exists and is configured"""
    if not check_file_exists('.env'):
        print("❌ فایل .env یافت نشد!")
        print("📝 لطفاً فایل .env را ایجاد کنید.")
        print("📖 راهنمای کامل در فایل CONFIG_GUIDE.md موجود است.")
        print("\nمرحله 1: فایل .env ایجاد کنید")
        print("مرحله 2: تنظیمات BOT_TOKEN, ADMIN_IDS و اطلاعات سرور را پر کنید")
        return False
    
    # Check if key variables are set
    from dotenv import load_dotenv
    load_dotenv()
    
    bot_token = os.getenv('BOT_TOKEN', '')
    admin_ids = os.getenv('ADMIN_IDS', '')
    server_host = os.getenv('SERVER_0_HOST', '')
    
    if not bot_token or bot_token == 'your_bot_token_here':
        print("❌ BOT_TOKEN تنظیم نشده است!")
        print("📝 لطفاً BOT_TOKEN را از @BotFather دریافت کنید.")
        return False
    
    if not admin_ids or admin_ids == 'your_admin_chat_id_here':
        print("❌ ADMIN_IDS تنظیم نشده است!")
        print("📝 لطفاً Chat ID خود را از @userinfobot دریافت کنید.")
        return False
    
    if not server_host or server_host == 'your_server_ip':
        print("❌ SERVER_0_HOST تنظیم نشده است!")
        print("📝 لطفاً IP آدرس سرور X-UI را وارد کنید.")
        return False
    
    print("✅ فایل .env تنظیم شده است.")
    return True

def check_database():
    """Check if database is set up"""
    db_path = "vpn_bot.db"
    if not check_file_exists(db_path):
        print("❌ دیتابیس یافت نشد!")
        print("📝 لطفاً دیتابیس را راه‌اندازی کنید:")
        print("   Windows: database_commands.bat")
        print("   Linux/Mac: python setup_database.py")
        return False
    
    print("✅ دیتابیس آماده است.")
    return True

def check_requirements():
    """Check if requirements are installed"""
    try:
        import telegram
        import sqlalchemy
        import aiohttp
        import dotenv
        print("✅ پکیج‌های مورد نیاز نصب شده‌اند.")
        return True
    except ImportError as e:
        print(f"❌ پکیج مورد نیاز نصب نشده: {e}")
        print("📝 لطفاً پکیج‌ها را نصب کنید:")
        print("   pip3 install python-telegram-bot python-dotenv sqlalchemy aiosqlite aiohttp requests --no-cache-dir")
        return False

def main():
    """Main startup function"""
    import asyncio
    from database.database import init_db, init_default_data

    print("🤖 VPN Bot Startup Script")
    print("=" * 50)
    
    # Check all prerequisites
    checks = [
        ("پکیج‌های پایتون", check_requirements),
        ("فایل تنظیمات", check_env_file),
        ("دیتابیس", check_database),
    ]
    
    all_passed = True
    for name, check_func in checks:
        print(f"\n🔍 بررسی {name}...")
        if not check_func():
            all_passed = False
    
    if not all_passed:
        print("\n❌ برخی از شرایط برآورده نشده‌اند.")
        print("📖 لطفاً فایل CONFIG_GUIDE.md را مطالعه کنید.")
        print("📖 یا فایل QUICK_START.md را برای راهنمای سریع بخوانید.")
        return False
    
    print("\n🎉 همه چیز آماده است! در حال شروع بات...")
    print("=" * 50)
    
    # ------------------------------------------------------------------
    # 0) Ensure database schema & default data are in place
    # ------------------------------------------------------------------
    try:
        init_db()  # ساخت جدول‌ها (idempotent)
        asyncio.run(init_default_data())  # داده‌های پیش‌فرض و سرورها/تمپلیت‌ها (UPSERT)
    except Exception as db_err:
        print(f"❌ خطا در همگام‌سازی دیتابیس: {db_err}")
        return False

    # ------------------------------------------------------------------
    # 1) Start the bot (main.py)
    # ------------------------------------------------------------------
    try:
        subprocess.run([sys.executable, "main.py"], check=True)
    except KeyboardInterrupt:
        print("\n👋 بات متوقف شد.")
    except Exception as e:
        print(f"\n❌ خطا در اجرای بات: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        input("\nPress Enter to exit...") 