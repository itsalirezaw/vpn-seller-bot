#!/usr/bin/env python3
"""
🗄️ راه‌اندازی سریع دیتابیس SQLite برای VPN Telegram Bot

استفاده:
    python setup_database.py

ویژگی‌ها:
    ✅ ساخت تمام جدول‌ها
    ✅ اضافه کردن داده‌های پیش‌فرض
    ✅ تست عملکرد
    ✅ بک‌آپ خودکار
"""

import sqlite3
import os
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# رنگ‌ها برای نمایش بهتر
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def print_status(message, status="info"):
    """پرینت با رنگ"""
    colors = {
        "success": Colors.GREEN,
        "error": Colors.RED,
        "warning": Colors.YELLOW,
        "info": Colors.BLUE,
        "header": Colors.PURPLE + Colors.BOLD
    }
    color = colors.get(status, Colors.WHITE)
    print(f"{color}{message}{Colors.RESET}")

def create_database_tables(db_path="vpn_bot.db"):
    """ساخت تمام جدول‌های مورد نیاز"""
    
    print_status("🗄️  در حال ساخت جدول‌های دیتابیس...", "header")
    
    # SQL برای ساخت جدول‌ها
    tables_sql = """
    -- جدول کاربران
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER UNIQUE NOT NULL,
        username TEXT,
        full_name TEXT,
        wallet_balance REAL DEFAULT 0.0,
        invite_code TEXT UNIQUE,
        gift_data INTEGER DEFAULT 0,
        gift_days INTEGER DEFAULT 0,
        test_used BOOLEAN DEFAULT 0,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- جدول سرورها
    CREATE TABLE IF NOT EXISTS servers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        host TEXT NOT NULL,
        port INTEGER NOT NULL,
        web_base_path TEXT DEFAULT '/',
        username TEXT NOT NULL,
        password TEXT NOT NULL,
        location TEXT,
        max_users INTEGER DEFAULT 100,
        current_users INTEGER DEFAULT 0,
        is_active BOOLEAN DEFAULT 1,
        last_health_check TIMESTAMP,
        config TEXT, -- JSON config
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(host, port)
    );

    -- جدول اکانت‌ها
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        uuid TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        total_data_limit INTEGER, -- bytes (0 = unlimited)
        expire_time TIMESTAMP NOT NULL,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );

    -- جدول مصرف سرورها
    CREATE TABLE IF NOT EXISTS server_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        server_id INTEGER NOT NULL,
        inbound_id INTEGER DEFAULT 1,
        data_used INTEGER DEFAULT 0, -- bytes
        last_sync TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (account_id) REFERENCES accounts (id) ON DELETE CASCADE,
        FOREIGN KEY (server_id) REFERENCES servers (id) ON DELETE CASCADE,
        UNIQUE(account_id, server_id)
    );

    -- جدول سفارشات
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL, -- 'purchase', 'wallet_charge', 'renewal'
        service_plan TEXT,
        amount REAL NOT NULL,
        account_id INTEGER,
        status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
        receipt_file_id TEXT,
        admin_note TEXT,
        admin_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        processed_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (account_id) REFERENCES accounts (id) ON DELETE SET NULL
    );

    -- جدول تمپلیت‌های کانفیگ
    CREATE TABLE IF NOT EXISTS config_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        protocol TEXT NOT NULL,
        description TEXT,
        template_data TEXT, -- JSON
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- جدول سشن کاربران
    CREATE TABLE IF NOT EXISTS user_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        session_type TEXT NOT NULL,
        session_data TEXT, -- JSON
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );

    -- جدول دعوت‌نامه‌ها
    CREATE TABLE IF NOT EXISTS invitations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inviter_id INTEGER NOT NULL,
        invited_id INTEGER NOT NULL,
        is_used BOOLEAN DEFAULT 0,
        reward_claimed BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (inviter_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (invited_id) REFERENCES users (id) ON DELETE CASCADE,
        UNIQUE(inviter_id, invited_id)
    );
    """

    # ایجاد ایندکس‌ها برای بهینه‌سازی
    indexes_sql = """
    -- ایندکس‌ها برای بهینه‌سازی
    CREATE INDEX IF NOT EXISTS idx_users_chat_id ON users(chat_id);
    CREATE INDEX IF NOT EXISTS idx_users_invite_code ON users(invite_code);
    CREATE INDEX IF NOT EXISTS idx_accounts_uuid ON accounts(uuid);
    CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id);
    CREATE INDEX IF NOT EXISTS idx_accounts_expire_time ON accounts(expire_time);
    CREATE INDEX IF NOT EXISTS idx_server_accounts_account_id ON server_accounts(account_id);
    CREATE INDEX IF NOT EXISTS idx_server_accounts_server_id ON server_accounts(server_id);
    CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
    CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
    CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
    CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at);
    CREATE INDEX IF NOT EXISTS idx_invitations_inviter_id ON invitations(inviter_id);
    """

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # اجرای دستورات ساخت جدول
        cursor.executescript(tables_sql)
        print_status("✅ جدول‌ها با موفقیت ایجاد شدند", "success")
        
        # اجرای ایندکس‌ها
        cursor.executescript(indexes_sql)
        print_status("✅ ایندکس‌ها با موفقیت ایجاد شدند", "success")
        
        conn.commit()
        conn.close()
        
        return True
        
    except Exception as e:
        print_status(f"❌ خطا در ساخت جدول‌ها: {e}", "error")
        return False

def insert_default_data(db_path="vpn_bot.db"):
    """اضافه کردن داده‌های پیش‌فرض"""
    
    print_status("📊 در حال اضافه کردن داده‌های پیش‌فرض...", "header")
    
    # تمپلیت‌های پروتکل
    protocol_templates = [
        {
            "name": "vmess_ws",
            "protocol": "vmess",
            "description": "VMess WebSocket",
            "template_data": json.dumps({
                "protocol": "vmess",
                "settings": {
                    "clients": [],
                    "decryption": "none",
                    "fallbacks": []
                },
                "streamSettings": {
                    "network": "ws",
                    "security": "none",
                    "wsSettings": {
                        "path": "/",
                        "headers": {}
                    }
                }
            })
        },
        {
            "name": "vmess_tcp",
            "protocol": "vmess", 
            "description": "VMess TCP",
            "template_data": json.dumps({
                "protocol": "vmess",
                "settings": {
                    "clients": [],
                    "decryption": "none",
                    "fallbacks": []
                },
                "streamSettings": {
                    "network": "tcp",
                    "security": "none",
                    "tcpSettings": {
                        "header": {
                            "type": "none"
                        }
                    }
                }
            })
        },
        {
            "name": "vless_ws",
            "protocol": "vless",
            "description": "VLESS WebSocket", 
            "template_data": json.dumps({
                "protocol": "vless",
                "settings": {
                    "clients": [],
                    "decryption": "none",
                    "fallbacks": []
                },
                "streamSettings": {
                    "network": "ws",
                    "security": "none",
                    "wsSettings": {
                        "path": "/vless",
                        "headers": {}
                    }
                }
            })
        },
        {
            "name": "trojan_ws",
            "protocol": "trojan",
            "description": "Trojan WebSocket",
            "template_data": json.dumps({
                "protocol": "trojan",
                "settings": {
                    "clients": [],
                    "fallbacks": []
                },
                "streamSettings": {
                    "network": "ws",
                    "security": "tls",
                    "wsSettings": {
                        "path": "/trojan",
                        "headers": {}
                    }
                }
            })
        }
    ]
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # اضافه کردن تمپلیت‌های پروتکل
        for template in protocol_templates:
            cursor.execute('''
                INSERT OR REPLACE INTO config_templates 
                (name, protocol, description, template_data, is_active)
                VALUES (?, ?, ?, ?, 1)
            ''', (template["name"], template["protocol"], 
                  template["description"], template["template_data"]))
        
        print_status("✅ تمپلیت‌های پروتکل اضافه شدند", "success")
        
        conn.commit()
        conn.close()
        
        return True
        
    except Exception as e:
        print_status(f"❌ خطا در اضافه کردن داده‌های پیش‌فرض: {e}", "error")
        return False

def add_sample_server(db_path="vpn_bot.db"):
    """اضافه کردن سرور نمونه"""
    
    print_status("🖥️  اضافه کردن سرور نمونه...", "info")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # چک کنیم سرور نمونه وجود داره یا نه
        cursor.execute("SELECT COUNT(*) FROM servers")
        server_count = cursor.fetchone()[0]
        
        if server_count == 0:
            cursor.execute('''
                INSERT INTO servers 
                (name, host, port, web_base_path, username, password, location, max_users, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            ''', ("Sample Server", "YOUR_SERVER_IP", 54321, "/", "admin", "YOUR_PASSWORD", "Sample Location", 100))
            
            print_status("✅ سرور نمونه اضافه شد (غیرفعال)", "success")
            print_status("⚠️  تنظیمات سرور را در فایل .env یا از طریق کد تغییر دهید", "warning")
        else:
            print_status("ℹ️  سرور(های) موجود پیدا شد", "info")
        
        conn.commit()
        conn.close()
        
        return True
        
    except Exception as e:
        print_status(f"❌ خطا در اضافه کردن سرور نمونه: {e}", "error")
        return False

def test_database(db_path="vpn_bot.db"):
    """تست عملکرد دیتابیس"""
    
    print_status("🧪 در حال تست دیتابیس...", "header")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # تست جدول‌ها
        tables = [
            "users", "servers", "accounts", "server_accounts", 
            "orders", "config_templates", "user_sessions", "invitations"
        ]
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print_status(f"  📋 {table}: {count} رکورد", "info")
        
        # تست تمپلیت‌های پروتکل
        cursor.execute("SELECT name, protocol FROM config_templates WHERE is_active = 1")
        templates = cursor.fetchall()
        
        print_status("🔌 پروتکل‌های فعال:", "info")
        for name, protocol in templates:
            print_status(f"  • {name} ({protocol})", "info")
        
        conn.close()
        
        print_status("✅ تست دیتابیس موفقیت‌آمیز بود", "success")
        return True
        
    except Exception as e:
        print_status(f"❌ خطا در تست دیتابیس: {e}", "error")
        return False

def create_backup(db_path="vpn_bot.db"):
    """ایجاد بک‌آپ از دیتابیس"""
    
    if not os.path.exists(db_path):
        return True
    
    print_status("💾 ایجاد بک‌آپ...", "info")
    
    try:
        # ایجاد پوشه بک‌آپ
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)
        
        # نام فایل بک‌آپ
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"vpn_bot_backup_{timestamp}.db"
        
        # کپی فایل
        shutil.copy2(db_path, backup_path)
        
        print_status(f"✅ بک‌آپ ایجاد شد: {backup_path}", "success")
        return True
        
    except Exception as e:
        print_status(f"❌ خطا در ایجاد بک‌آپ: {e}", "error")
        return False

def show_database_info(db_path="vpn_bot.db"):
    """نمایش اطلاعات دیتابیس"""
    
    print_status("📊 اطلاعات دیتابیس:", "header")
    
    try:
        # اندازه فایل
        file_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
        size_mb = file_size / (1024 * 1024)
        
        print_status(f"📁 مسیر: {os.path.abspath(db_path)}", "info")
        print_status(f"📏 اندازه: {size_mb:.2f} MB", "info")
        print_status(f"🕐 ایجاد شده: {datetime.fromtimestamp(os.path.getctime(db_path))}" if os.path.exists(db_path) else "🆕 جدید", "info")
        
        return True
        
    except Exception as e:
        print_status(f"❌ خطا در نمایش اطلاعات: {e}", "error")
        return False

def create_sql_dump(db_path="vpn_bot.db"):
    """ایجاد SQL dump برای انتقال به سرور دیگر"""
    
    if not os.path.exists(db_path):
        print_status("⚠️  فایل دیتابیس یافت نشد", "warning")
        return False
    
    print_status("📜 ایجاد SQL dump...", "info")
    
    try:
        conn = sqlite3.connect(db_path)
        
        # ایجاد پوشه dumps
        dump_dir = Path("dumps")
        dump_dir.mkdir(exist_ok=True)
        
        # نام فایل dump
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_path = dump_dir / f"vpn_bot_dump_{timestamp}.sql"
        
        # ایجاد dump
        with open(dump_path, 'w', encoding='utf-8') as f:
            for line in conn.iterdump():
                f.write(f"{line}\n")
        
        conn.close()
        
        print_status(f"✅ SQL dump ایجاد شد: {dump_path}", "success")
        print_status("💡 برای restore: sqlite3 new_db.db < dump_file.sql", "info")
        
        return True
        
    except Exception as e:
        print_status(f"❌ خطا در ایجاد SQL dump: {e}", "error")
        return False

def main():
    """تابع اصلی"""
    
    print_status("🚀 راه‌اندازی دیتابیس VPN Telegram Bot", "header")
    print_status("=" * 50, "header")
    
    db_path = "vpn_bot.db"
    
    # بک‌آپ از دیتابیس فعلی (اگر وجود داشته باشد)
    if os.path.exists(db_path):
        print_status("⚠️  دیتابیس موجود پیدا شد", "warning")
        create_backup(db_path)
    
    # نمایش اطلاعات دیتابیس
    show_database_info(db_path)
    
    # ایجاد جدول‌ها
    if not create_database_tables(db_path):
        print_status("❌ خطا در ساخت جدول‌ها", "error")
        return False
    
    # اضافه کردن داده‌های پیش‌فرض
    if not insert_default_data(db_path):
        print_status("❌ خطا در اضافه کردن داده‌های پیش‌فرض", "error")
        return False
    
    # اضافه کردن سرور نمونه
    add_sample_server(db_path)
    
    # تست دیتابیس
    if not test_database(db_path):
        print_status("❌ خطا در تست دیتابیس", "error")
        return False
    
    # ایجاد SQL dump
    create_sql_dump(db_path)
    
    print_status("=" * 50, "header")
    print_status("🎉 راه‌اندازی دیتابیس با موفقیت تکمیل شد!", "success")
    print_status("", "info")
    print_status("📋 مراحل بعدی:", "header")
    print_status("1. فایل .env را تنظیم کنید", "info")
    print_status("2. اطلاعات سرورهای X-UI را اضافه کنید", "info")  
    print_status("3. ربات را اجرا کنید: python main.py", "info")
    
    return True

if __name__ == "__main__":
    main() 