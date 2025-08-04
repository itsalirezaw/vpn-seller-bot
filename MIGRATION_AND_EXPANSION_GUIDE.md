# 🚀 راهنمای کامل مهاجرت و گسترش ربات VPN

این راهنمای جامع تمام مراحل مهاجرت ربات، اضافه کردن سرور جدید، و اضافه کردن پروتکل جدید را پوشش می‌دهد.

## 📋 فهرست مطالب

1. [مهاجرت کامل ربات به سرور جدید](#1️⃣-مهاجرت-کامل-ربات-به-سرور-جدید)
2. [اضافه کردن سرور جدید به تمام کاربران](#2️⃣-اضافه-کردن-سرور-جدید-به-تمام-کاربران)
3. [اضافه کردن پروتکل جدید به تمام کاربران](#3️⃣-اضافه-کردن-پروتکل-جدید-به-تمام-کاربران)
4. [عیب‌یابی و نکات مهم](#4️⃣-عیب‌یابی-و-نکات-مهم)

---

## 1️⃣ مهاجرت کامل ربات به سرور جدید

### 🎯 هدف
انتقال کامل ربات به سرور جدید بدون از دست رفتن هیچ‌گونه اطلاعات کاربران، تنظیمات، یا تاریخچه.

### ⚠️ پیش‌نیازها
- دسترسی SSH به سرور فعلی و جدید
- Python 3.8+ روی سرور جدید
- اتصال اینترنت پایدار
- فضای کافی روی سرور جدید

### 📝 مراحل تفصیلی

#### مرحله 1: ایجاد بک‌آپ کامل

```bash
# اجرای اسکریپت مهاجرت
cd /path/to/your/bot/directory
python scripts/migrate_to_new_server.py
```

**سوال تایید:** `Create migration backup? [y/N]:`
- پاسخ: `y` + Enter

**خروجی مورد انتظار:**
```
🚀 Starting migration backup creation...
💾 Backing up database...
⚙️  Backing up configuration...
📜 Backing up scripts...
📋 Creating migration info...
🔄 Creating restoration script...
✅ Migration backup created successfully!
📂 Backup location: migration_backup/bot_migration_20240101_123456
📦 Backup size: 25.3 MB
```

#### مرحله 2: انتقال فایل‌ها به سرور جدید

**روش 1: استفاده از scp**
```bash
# فشرده‌سازی بک‌آپ
cd migration_backup
tar -czf bot_migration_20240101_123456.tar.gz bot_migration_20240101_123456/

# انتقال به سرور جدید
scp bot_migration_20240101_123456.tar.gz user@new-server-ip:/home/user/
```

**روش 2: استفاده از Git (توصیه می‌شود)**
```bash
# در سرور فعلی
git add .
git commit -m "Pre-migration backup"
git push origin main

# در سرور جدید
git clone https://github.com/your-username/your-repo.git
cd your-repo
```

#### مرحله 3: آماده‌سازی سرور جدید

```bash
# نصب Python و pip
sudo apt update
sudo apt install python3 python3-pip python3-venv git -y

# ایجاد مجوزهای لازم
sudo chown -R $USER:$USER /home/$USER/
```

#### مرحله 4: بازیابی در سرور جدید

```bash
# اگر از scp استفاده کردید
cd /home/user/
tar -xzf bot_migration_20240101_123456.tar.gz
cd bot_migration_20240101_123456/

# اجرای اسکریپت بازیابی
chmod +x restore.sh
./restore.sh
```

**خروجی مورد انتظار:**
```
🔄 Starting VPN Bot restoration...
💾 Restoring database...
✅ Database restored
⚙️  Restoring configuration...
✅ Configuration restored
📜 Restoring code...
✅ Code restored
🎉 Restoration completed!
```

#### مرحله 5: به‌روزرسانی تنظیمات

```bash
# ویرایش فایل .env
nano .env
```

**تغییرات مورد نیاز در .env:**
```env
# به‌روزرسانی اطلاعات سرورهای X-UI (در صورت تغییر IP)
SERVER_1_HOST="new-server-1-ip"
SERVER_2_HOST="new-server-2-ip"

# به‌روزرسانی دامنه subscription (در صورت تغییر)
SUBSCRIPTION_DOMAIN="new-domain.com"

# سایر تنظیمات را بر اساس سرور جدید تنظیم کنید
```

#### مرحله 6: نصب وابستگی‌ها و تست

```bash
# نصب وابستگی‌ها
pip install -r requirements.txt

# تست دیتابیس
python setup_database.py

# تست ربات
python start_bot.py
```

**تست‌های ضروری:**
1. ✅ ربات به دستور `/start` پاسخ می‌دهد
2. ✅ تعداد کاربران حفظ شده است
3. ✅ سیستم پرداخت کار می‌کند
4. ✅ اتصال به سرورهای X-UI برقرار است
5. ✅ لینک‌های اشتراک کار می‌کنند

#### مرحله 7: به‌روزرسانی خدمات خارجی

```bash
# در صورت استفاده از webhook
# به‌روزرسانی URL webhook در BotFather

# در صورت تغییر دامنه
# به‌روزرسانی DNS records
```

---

## 2️⃣ اضافه کردن سرور جدید به تمام کاربران

### 🎯 هدف
اضافه کردن سرور جدید (مثل لهستان) به لیست سرورهای همه کاربران موجود تا در لینک اشتراک آن‌ها نمایش داده شود.

### ⚠️ پیش‌نیازها
- سرور X-UI جدید راه‌اندازی شده
- اتصال SSH به سرور جدید
- inbound مناسب در پنل X-UI ایجاد شده

### 📝 مراحل تفصیلی

#### مرحله 1: راه‌اندازی سرور X-UI جدید

**نصب X-UI بر روی سرور جدید:**
```bash
# اتصال SSH به سرور جدید
ssh root@poland-server-ip

# نصب X-UI
bash <(curl -Ls https://raw.githubusercontent.com/vaxilu/x-ui/master/install.sh)

# تنظیم نام کاربری و رمز عبور
# ایجاد inbound با تنظیمات مناسب (معمولاً ID: 4)
```

#### مرحله 2: اضافه کردن سرور به تنظیمات ربات

```bash
# ویرایش فایل .env
nano .env
```

**اضافه کردن تنظیمات سرور جدید:**
```env
# سرور جدید لهستان
SERVER_3_NAME="Poland"
SERVER_3_HOST="poland-server-ip"
SERVER_3_PORT="54321"
SERVER_3_WEB_BASE_PATH="/panel"
SERVER_3_USERNAME="admin"
SERVER_3_PASSWORD="your_x_ui_password"
SERVER_3_SSH_USERNAME="root"
SERVER_3_SSH_PASSWORD="your_ssh_password"
SERVER_3_IS_ACTIVE="true"
```

#### مرحله 3: همگام‌سازی تنظیمات

```bash
# همگام‌سازی سرورها با دیتابیس
python sync_templates.py
```

**خروجی مورد انتظار:**
```
Syncing server: Poland
✅ Server Poland added/updated in database
Template sync completed successfully
```

#### مرحله 4: ویرایش اسکریپت انتساب

```bash
# ویرایش اسکریپت
nano scripts/assign_all_to_new_server.py
```

**تغییرات مورد نیاز:**
```python
# خط 35 و 36 را تغییر دهید:
NEW_SERVER_NAME = "Poland"   # ← نام دقیق سرور (همان SERVER_3_NAME)
INBOUND_ID = 4               # ← ID inbound در پنل X-UI
```

#### مرحله 5: اختصاص سرور به تمام کاربران

```bash
# اجرای اسکریپت انتساب
python scripts/assign_all_to_new_server.py
```

**خروجی مورد انتظار:**
```
12:34:56  abc123-def4-5678-9abc-def123456789  ✓
12:34:57  def456-abc7-8901-2def-abc456789012  ✓
12:34:58  ghi789-def0-1234-5ghi-def789012345  ✗
...
Summary: 245/250 accounts assigned to Poland.
```

#### مرحله 6: تست و تایید

```bash
# تست یکی از لینک‌های اشتراک کاربران
# باید کانفیگ سرور جدید در آن موجود باشد

# بررسی لاگ‌ها
tail -f logs/bot.log

# تست اتصال به سرور جدید
python -c "
from services.server_manager import server_manager
import asyncio
async def test():
    servers = await server_manager.get_active_servers()
    print([s.name for s in servers])
asyncio.run(test())
"
```

**نتیجه:** همه کاربران موجود اکنون کانفیگ سرور لهستان را در لینک اشتراک خود دارند.

---

## 3️⃣ اضافه کردن پروتکل جدید به تمام کاربران

### 🎯 هدف
اضافه کردن پروتکل جدید (مثل Reality) به همه کاربران موجود تا در لینک اشتراک آن‌ها نمایش داده شود.

### ⚠️ پیش‌نیازها
- آشنایی با تنظیمات پروتکل جدید
- دسترسی به پنل X-UI سرورها
- دانش پایه JSON و تنظیمات X-UI

### 📝 مراحل تفصیلی

#### مرحله 1: تعریف پروتکل در تنظیمات

```bash
# ویرایش فایل تنظیمات
nano config/settings.py
```

**پیدا کردن بخش PROTOCOL_TEMPLATES و اضافه کردن:**
```python
PROTOCOL_TEMPLATES = {
    # ... سایر پروتکل‌های موجود
    
    "reality": {
        "name": "Reality VLESS",
        "protocol": "vless",
        "allowed_servers": ["Iran", "Poland"],  # سرورهای مجاز (خالی = همه)
        "config_template": {
            "v": "2",
            "ps": "{server_name} - Reality",
            "add": "{server_host}",
            "port": "443",
            "id": "{user_uuid}",
            "net": "tcp",
            "type": "none",
            "host": "",
            "path": "/",
            "tls": "reality",
            "sni": "www.google.com",
            "fp": "chrome",
            "pbk": "your_public_key_here",
            "sid": "your_short_id_here"
        }
    }
}
```

**نکات مهم:**
- `allowed_servers`: فقط سرورهای مشخص شده این پروتکل را دریافت می‌کنند
- اگر `allowed_servers` خالی باشد، همه سرورها این پروتکل را دریافت می‌کنند
- مقادیر `pbk` و `sid` باید از تنظیمات Reality X-UI کپی شوند

#### مرحله 2: ایجاد inbound جدید در X-UI

**برای هر سرور که می‌خواهید Reality داشته باشد:**

1. **وارد پنل X-UI شوید:**
   ```
   http://server-ip:port/panel
   ```

2. **ایجاد inbound جدید:**
   - Protocol: `VLESS`
   - Port: `443` (یا پورت دلخواه)
   - Network: `tcp`
   - Security: `reality`
   - uTLS: `chrome`
   - Dest: `www.google.com:443`
   - ServerNames: `www.google.com`
   - PrivateKey: (کلید خصوصی تولید شده)
   - ShortIds: (ID کوتاه تولید شده)

3. **یادداشت کردن اطلاعات:**
   - Inbound ID (مثلاً 5)
   - Public Key
   - Short ID

#### مرحله 3: به‌روزرسانی تنظیمات با اطلاعات واقعی

```bash
# ویرایش مجدد فایل تنظیمات
nano config/settings.py
```

**به‌روزرسانی اطلاعات Reality:**
```python
"reality": {
    "name": "Reality VLESS",
    "protocol": "vless", 
    "allowed_servers": ["Iran", "Poland"],
    "config_template": {
        # ... سایر تنظیمات
        "pbk": "actual_public_key_from_xui",      # ← از پنل X-UI کپی کنید
        "sid": "actual_short_id_from_xui"        # ← از پنل X-UI کپی کنید
    }
}
```

#### مرحله 4: ویرایش اسکریپت اضافه کردن پروتکل

```bash
# ویرایش اسکریپت
nano scripts/add_new_protocol_to_all.py
```

**تغییرات مورد نیاز:**
```python
# خط‌های 28-30 را تغییر دهید:
NEW_PROTOCOL_NAME = "reality"              # نام پروتکل (همان کلید در PROTOCOL_TEMPLATES)
TARGET_SERVERS = ["Iran", "Poland"]       # سرورهای هدف (خالی = همه سرورهای فعال)
INBOUND_ID = 5                             # ID inbound Reality در X-UI
```

#### مرحله 5: اجرای اسکریپت اضافه کردن پروتکل

```bash
# اجرای اسکریپت
python scripts/add_new_protocol_to_all.py
```

**سوال‌های تایید:**
```
🔄 Adding new protocol to all existing accounts...
⚠️  Make sure you have:
   1. Added your protocol to PROTOCOL_TEMPLATES in settings.py
   2. Created the target inbound on all servers  
   3. Updated the configuration variables in this script

Continue? [y/N]:
```
- پاسخ: `y` + Enter

**خروجی مورد انتظار:**
```
🚀 Adding protocol 'reality' to all accounts...
📋 Target servers: ['Iran', 'Poland']
🔗 Target inbound ID: 5
✅ Found 2 target servers
📊 Processing 250 accounts...

[1/250] Processing account: VPN12345abc12
✅ Account VPN12345abc12 updated successfully

[2/250] Processing account: VPN67890def67  
✅ Account VPN67890def67 updated successfully

...

🎉 Process completed!
📊 Summary:
   - Total accounts: 250
   - Successfully updated: 245
   - Failed: 5
   - Errors: 2
```

#### مرحله 6: تست و تایید

```bash
# تست لینک اشتراک یکی از کاربران
curl "https://subs.prvprt.com/sub/VPN12345abc12" | base64 -d

# باید خروجی شامل کانفیگ Reality باشد:
# vless://uuid@server:443?type=tcp&security=reality&sni=www.google.com#Iran%20-%20Reality
```

**نتیجه:** همه کاربران موجود اکنون کانفیگ Reality را در لینک اشتراک خود دارند.

---

## 4️⃣ عیب‌یابی و نکات مهم

### 🚨 مشکلات رایج و راه‌حل‌ها

#### مشکل 1: خطای "Database locked"
```bash
# راه‌حل:
sudo pkill -f "python.*bot"  # متوقف کردن تمام نمونه‌های ربات
rm -f vpn_bot.db-wal vpn_bot.db-shm  # حذف فایل‌های lock
python start_bot.py  # راه‌اندازی مجدد
```

#### مشکل 2: خطای "Server not found"
```bash
# بررسی تنظیمات سرور
python -c "
from config.settings import settings
print([s.name for s in settings.servers])
"

# همگام‌سازی مجدد
python sync_templates.py
```

#### مشکل 3: خطای "Protocol not found in templates"
```bash
# بررسی PROTOCOL_TEMPLATES
python -c "
from config.settings import PROTOCOL_TEMPLATES
print(list(PROTOCOL_TEMPLATES.keys()))
"

# اطمینان از صحت نام پروتکل در اسکریپت
```

#### مشکل 4: کانفیگ‌ها در لینک اشتراک نمایش داده نمی‌شوند
```bash
# تست تولید کانفیگ
python -c "
import asyncio
from services.account_manager import AccountManager
async def test():
    am = AccountManager()
    configs = await am.generate_config_urls('account-uuid-here')
    print(configs)
asyncio.run(test())
"

# ریستارت سرویس subscription
sudo systemctl restart subs-api
```

### 📊 بررسی سلامت سیستم

#### تست کامل عملکرد
```bash
# اسکریپت تست سریع
cat > test_system.py << 'EOF'
import asyncio
from database.database import db_manager
from database.models import User, Account, Server
from services.account_manager import AccountManager

async def test_system():
    print("🔍 Testing system health...")
    
    # تست دیتابیس
    db = db_manager.get_session()
    user_count = db.query(User).count()
    account_count = db.query(Account).count()  
    server_count = db.query(Server).count()
    db.close()
    
    print(f"👥 Users: {user_count}")
    print(f"🔐 Accounts: {account_count}")
    print(f"🖥️  Servers: {server_count}")
    
    # تست account manager
    am = AccountManager()
    servers = await am.server_manager.get_active_servers()
    print(f"✅ Active servers: {[s.name for s in servers]}")
    
    print("🎉 System healthy!")

if __name__ == "__main__":
    asyncio.run(test_system())
EOF

python test_system.py
```

### 💾 بک‌آپ دوره‌ای

#### راه‌اندازی بک‌آپ خودکار
```bash
# ایجاد اسکریپت بک‌آپ روزانه
cat > daily_backup.sh << 'EOF'
#!/bin/bash
cd /path/to/your/bot
python scripts/migrate_to_new_server.py --backup-only

# نگهداری فقط 7 بک‌آپ اخیر
cd migration_backup
ls -t | tail -n +8 | xargs rm -rf
EOF

chmod +x daily_backup.sh

# اضافه کردن به cron (بک‌آپ روزانه 2 شب)
echo "0 2 * * * /path/to/daily_backup.sh" | crontab -
```

### 🔒 نکات امنیتی

1. **محافظت از فایل .env:**
   ```bash
   chmod 600 .env
   ```

2. **استفاده از کلیدهای SSH:**
   ```bash
   ssh-keygen -t rsa -b 4096
   ssh-copy-id user@server
   ```

3. **رمزگذاری بک‌آپ‌ها:**
   ```bash
   # رمزگذاری بک‌آپ قبل از انتقال
   gpg -c backup_file.tar.gz
   ```

### 📞 چک‌لیست نهایی

#### قبل از هر عملیات:
- [ ] بک‌آپ کامل گرفته شده
- [ ] تست در محیط آزمایشی انجام شده
- [ ] تمام وابستگی‌ها نصب شده
- [ ] دسترسی‌های لازم تایید شده

#### بعد از هر عملیات:
- [ ] ربات پاسخگو است
- [ ] تعداد کاربران حفظ شده
- [ ] لینک‌های اشتراک کار می‌کنند
- [ ] سیستم پرداخت فعال است
- [ ] نظارت و لاگ‌ها عادی هستند

---

## 📞 تماس و پشتیبانی

در صورت بروز مشکل:

1. بررسی لاگ‌ها: `tail -f logs/bot.log`
2. بررسی وضعیت دیتابیس: `python setup_database.py`
3. تست اتصالات: `python test_system.py`
4. بازگشت به بک‌آپ قبلی در صورت لزوم

**⚠️ هرگز فایل‌های اصلی را بدون بک‌آپ تغییر ندهید!**

---

*راهنما آخرین‌بار در تاریخ تولید به‌روزرسانی شده است. همیشه قبل از اعمال تغییرات، بک‌آپ کامل تهیه کنید.*