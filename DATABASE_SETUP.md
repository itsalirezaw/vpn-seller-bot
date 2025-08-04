# 🗄️ راهنمای راه‌اندازی دیتابیس SQLite

این راهنما برای راه‌اندازی سریع و آسان دیتابیس SQLite در پروژه VPN Telegram Bot طراحی شده است.

## 🚀 راه‌اندازی فوری (1 دقیقه)

### برای Linux/Mac:
```bash
# دادن مجوز اجرا
chmod +x database_commands.sh

# اجرای منوی تعاملی
./database_commands.sh

# یا راه‌اندازی مستقیم
python3 setup_database.py
```

### برای Windows:
```cmd
# کلیک دوبار روی فایل یا:
database_commands.bat

# یا راه‌اندازی مستقیم
python setup_database.py
```

## 📁 ساختار فایل‌های دیتابیس

```
📁 پروژه/
├── 📄 setup_database.py       # اسکریپت راه‌اندازی
├── 📄 database_commands.sh    # منوی Linux/Mac
├── 📄 database_commands.bat   # منوی Windows
├── 📄 vpn_bot.db              # فایل دیتابیس اصلی
├── 📁 backups/                # بک‌آپ‌های خودکار
│   ├── vpn_bot_backup_20240115_120000.db
│   └── vpn_bot_backup_20240115_140000.db
└── 📁 dumps/                  # فایل‌های SQL صادراتی
    └── vpn_bot_dump_20240115_120000.sql
```

## 🏗️ جدول‌های ایجاد شده

### 👤 users - کاربران
```sql
id              - شناسه یکتا
chat_id         - آیدی تلگرام (یکتا)
username        - نام کاربری تلگرام
full_name       - نام کامل
wallet_balance  - موجودی کیف پول (تومان)
invite_code     - کد دعوت (یکتا)
gift_data       - حجم هدیه (بایت)
gift_days       - روزهای هدیه
test_used       - استفاده از اکانت تست
is_active       - وضعیت فعال/غیرفعال
created_at      - تاریخ ایجاد
```

### 🖥️ servers - سرورها
```sql
id                  - شناسه یکتا
name               - نام سرور
host               - آی‌پی سرور
port               - پورت X-UI
web_base_path      - مسیر پایه وب
username           - نام کاربری X-UI
password           - رمز عبور X-UI
location           - موقعیت جغرافیایی
max_users          - حداکثر کاربران
current_users      - کاربران فعلی
is_active          - وضعیت فعال/غیرفعال
last_health_check  - آخرین بررسی سلامت
config             - تنظیمات JSON
```

### 🔗 accounts - اکانت‌های VPN
```sql
id                - شناسه یکتا
user_id           - شناسه کاربر (FK)
uuid              - UUID اکانت (یکتا)
email             - ایمیل اکانت (یکتا)
total_data_limit  - محدودیت کل حجم (بایت)
expire_time       - زمان انقضا
is_active         - وضعیت فعال/غیرفعال
created_at        - تاریخ ایجاد
```

### 📊 server_accounts - مصرف هر سرور
```sql
id          - شناسه یکتا
account_id  - شناسه اکانت (FK)
server_id   - شناسه سرور (FK)
inbound_id  - شناسه inbound در X-UI
data_used   - حجم مصرف شده (بایت)
last_sync   - آخرین همگام‌سازی
```

### 💳 orders - سفارشات
```sql
id             - شناسه یکتا
user_id        - شناسه کاربر (FK)
type           - نوع سفارش (purchase/wallet_charge/renewal)
service_plan   - پلن انتخابی
amount         - مبلغ (تومان)
account_id     - شناسه اکانت (FK)
status         - وضعیت (pending/approved/rejected)
receipt_file_id - شناسه فایل رسید
admin_note     - یادداشت ادمین
admin_id       - شناسه ادمین تایید کننده
created_at     - تاریخ ایجاد
processed_at   - تاریخ پردازش
```

### 🔌 config_templates - تمپلیت‌های کانفیگ
```sql
id            - شناسه یکتا
name          - نام تمپلیت (یکتا)
protocol      - نوع پروتکل (vmess/vless/trojan)
description   - توضیحات
template_data - داده‌های JSON تمپلیت
is_active     - وضعیت فعال/غیرفعال
```

### 🎁 invitations - دعوت‌نامه‌ها
```sql
id             - شناسه یکتا
inviter_id     - شناسه دعوت کننده (FK)
invited_id     - شناسه دعوت شده (FK)
is_used        - استفاده شده یا نه
reward_claimed - پاداش دریافت شده
created_at     - تاریخ ایجاد
```

## 🔧 دستورات مفید SQLite

### بررسی سریع:
```sql
-- نمایش جدول‌ها
.tables

-- ساختار جدول
.schema users

-- تعداد کاربران
SELECT COUNT(*) FROM users;

-- تعداد اکانت‌های فعال
SELECT COUNT(*) FROM accounts WHERE is_active = 1;

-- آمار سفارشات
SELECT status, COUNT(*) FROM orders GROUP BY status;
```

### کوئری‌های پیشرفته:
```sql
-- کاربران با بیشترین موجودی
SELECT username, wallet_balance 
FROM users 
ORDER BY wallet_balance DESC 
LIMIT 10;

-- اکانت‌هایی که به انقضا نزدیک‌اند
SELECT u.username, a.email, a.expire_time
FROM accounts a
JOIN users u ON a.user_id = u.id
WHERE a.expire_time BETWEEN datetime('now') 
  AND datetime('now', '+7 days');

-- مصرف کل هر کاربر
SELECT u.username, 
       SUM(sa.data_used) as total_usage,
       a.total_data_limit
FROM users u
JOIN accounts a ON u.id = a.user_id
JOIN server_accounts sa ON a.id = sa.account_id
GROUP BY u.id;
```

## 🛠️ عملیات نگهداری

### بک‌آپ دستی:
```bash
# Linux/Mac
cp vpn_bot.db backups/manual_backup_$(date +%Y%m%d_%H%M%S).db

# Windows
copy vpn_bot.db backups\manual_backup_%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%.db
```

### صادرات SQL:
```bash
sqlite3 vpn_bot.db .dump > export.sql
```

### بازیابی از SQL:
```bash
sqlite3 new_database.db < export.sql
```

### پاک‌سازی داده‌های قدیمی:
```sql
-- حذف سشن‌های منقضی
DELETE FROM user_sessions 
WHERE expires_at < datetime('now');

-- حذف اکانت‌های منقضی شده بیش از 30 روز
DELETE FROM accounts 
WHERE expire_time < datetime('now', '-30 days');
```

## 📊 مانیتورینگ و بهینه‌سازی

### بررسی اندازه دیتابیس:
```sql
-- اندازه هر جدول
SELECT name, 
       COUNT(*) as rows,
       (SELECT COUNT(*) FROM pragma_table_info(name)) as columns
FROM sqlite_master 
WHERE type='table';
```

### بهینه‌سازی:
```sql
-- تجزیه و تحلیل برای بهینه‌سازی
ANALYZE;

-- فشرده‌سازی دیتابیس
VACUUM;

-- بررسی یکپارچگی
PRAGMA integrity_check;
```

## 🚨 عیب‌یابی مشکلات رایج

### دیتابیس قفل شده:
```bash
# بستن تمام اتصالات
pkill -f python
# یا در Windows
taskkill /f /im python.exe

# سپس دوباره تلاش کنید
```

### فساد دیتابیس:
```sql
-- بررسی فساد
PRAGMA integrity_check;

-- بازیابی از بک‌آپ
cp backups/latest_backup.db vpn_bot.db
```

### کمبود فضا:
```bash
# بررسی فضای دیسک
df -h .

# پاک‌سازی بک‌آپ‌های قدیمی
find backups/ -name "*.db" -mtime +30 -delete
```

## 🔐 امنیت

### تنظیمات امنیتی:
```sql
-- فعال‌سازی WAL mode برای کارایی بهتر
PRAGMA journal_mode=WAL;

-- فعال‌سازی foreign keys
PRAGMA foreign_keys=ON;

-- تنظیم timeout
PRAGMA busy_timeout=30000;
```

### مجوزهای فایل:
```bash
# تنظیم مجوزهای مناسب
chmod 600 vpn_bot.db
chmod 700 backups/
```

## 📞 پشتیبانی

در صورت بروز مشکل:

1. **بررسی لاگ‌ها:** `logs/bot.log`
2. **اجرای تست:** `python3 setup_database.py`
3. **بازیابی از بک‌آپ:** از منوی دستورات استفاده کنید
4. **ایجاد issue:** در GitHub پروژه

---

**💡 نکته:** این فایل‌ها برای راه‌اندازی سریع طراحی شده‌اند. برای محیط production حتماً تنظیمات امنیتی اضافی اعمال کنید. 