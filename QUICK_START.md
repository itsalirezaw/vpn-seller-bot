# 🚀 راهنمای شروع سریع - VPN Telegram Bot

راه‌اندازی کامل ربات VPN در کمتر از 10 دقیقه!

## ⚡ راه‌اندازی فوری

### 1️⃣ آماده‌سازی (2 دقیقه)

```bash
# کلون پروژه
git clone https://github.com/yourusername/vpn-telegram-bot.git
cd vpn-telegram-bot

# نصب وابستگی‌ها
pip install -r requirements.txt

# ایجاد پوشه‌های مورد نیاز
mkdir -p logs backups dumps
```

### 2️⃣ راه‌اندازی دیتابیس (1 دقیقه)

```bash
# Linux/Mac
chmod +x database_commands.sh
python3 setup_database.py

# Windows
python setup_database.py
```

### 3️⃣ تنظیم فایل .env (3 دقیقه)

فایل `.env` را ایجاد کنید:

```env
# ==========================================
# 🤖 اطلاعات ربات تلگرام
# ==========================================
BOT_TOKEN=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefg
ADMIN_IDS=123456789,987654321

# ==========================================
# 💳 اطلاعات پرداخت
# ==========================================
PAYMENT_CARD_NUMBER=6037-9977-1234-5678
PAYMENT_CARD_OWNER=نام شما

# ==========================================
# 🗄️ دیتابیس
# ==========================================
DATABASE_URL=sqlite:///./vpn_bot.db
DATABASE_ECHO=false

# ==========================================
# 🖥️ سرورهای X-UI
# ==========================================
SERVER_COUNT=2

# سرور اول
SERVER_0_NAME=Germany Server
SERVER_0_HOST=185.123.45.67
SERVER_0_PORT=54321
SERVER_0_WEB_BASE_PATH=/
SERVER_0_USERNAME=admin
SERVER_0_PASSWORD=YourPassword123
SERVER_0_ACTIVE=true

# سرور دوم
SERVER_1_NAME=Netherlands Server
SERVER_1_HOST=194.87.65.43
SERVER_1_PORT=54321
SERVER_1_WEB_BASE_PATH=/
SERVER_1_USERNAME=admin
SERVER_1_PASSWORD=YourPassword456
SERVER_1_ACTIVE=true
```

### 4️⃣ اجرای ربات (1 دقیقه)

```bash
python main.py
```

اگر همه چیز درست باشد، باید این پیام‌ها را ببینید:
```
INFO - Bot started successfully
INFO - All services initialized successfully
INFO - Monitoring service started
```

## 🔧 راهنمای گام به گام تنظیمات

### 📱 دریافت Bot Token

1. به [@BotFather](https://t.me/BotFather) برید
2. `/newbot` بفرستید  
3. نام ربات را وارد کنید (مثل: `My VPN Bot`)
4. Username ربات را وارد کنید (باید با `_bot` تمام شود)
5. Token دریافتی را کپی کنید

### 👤 پیدا کردن Chat ID

1. به [@userinfobot](https://t.me/userinfobot) برید
2. `/start` بفرستید
3. عدد `Id` را کپی کنید

### 🖥️ تنظیم سرور X-UI

اطلاعات مورد نیاز:
- **HOST**: آی‌پی سرور شما
- **PORT**: پورت وب پنل (معمولاً 54321)
- **USERNAME**: نام کاربری پنل
- **PASSWORD**: رمز عبور پنل

## 🧪 تست سیستم

### تست دیتابیس:
```bash
python3 -c "
from database.database import test_database
test_database()
"
```

### تست ربات:
```bash
python3 -c "
from config.settings import settings
print('Bot Token:', settings.bot.token[:10] + '...')
print('Admins:', settings.bot.ADMIN_IDS)
print('Servers:', len(settings.servers))
"
```

### تست اتصال سرور:
```bash
python3 -c "
from services.server_manager import server_manager
import asyncio
asyncio.run(server_manager.check_all_servers_health())
"
```

## 📋 چک‌لیست راه‌اندازی

- [ ] ✅ Python 3.8+ نصب شده
- [ ] ✅ وابستگی‌ها نصب شدند (`pip install -r requirements.txt`)
- [ ] ✅ فایل `.env` ایجاد و تکمیل شد
- [ ] ✅ دیتابیس راه‌اندازی شد (`python setup_database.py`)
- [ ] ✅ سرور X-UI در دسترس است
- [ ] ✅ Bot Token معتبر است
- [ ] ✅ Admin Chat ID درست است
- [ ] ✅ ربات اجرا شد (`python main.py`)

## 🔍 عیب‌یابی مشکلات رایج

### ❌ خطای "Bot Token invalid"
```
راه‌حل: Bot Token را از BotFather دوباره بگیرید
```

### ❌ خطای "Module not found"
```bash
# نصب دوباره وابستگی‌ها
pip install -r requirements.txt --upgrade
```

### ❌ خطای "Server connection failed"
```
راه‌حل:
1. IP و Port سرور را چک کنید
2. Username/Password را چک کنید  
3. فایروال سرور را چک کنید
```

### ❌ خطای "Database locked"
```bash
# بستن پروسه‌های پایتون
pkill -f python  # Linux/Mac
taskkill /f /im python.exe  # Windows
```

## 📊 مانیتورینگ اولیه

### لاگ‌ها:
```bash
# مشاهده لاگ‌های زنده
tail -f logs/bot.log

# آخرین خطاها
grep ERROR logs/bot.log | tail -10
```

### آمار دیتابیس:
```bash
# Linux/Mac
./database_commands.sh

# Windows
database_commands.bat
```

### وضعیت سرورها:
- از ربات: دستور `/admin` → مدیریت سرورها → وضعیت سرورها

## 🎯 تست عملکرد

### تست کاربر عادی:
1. پیام `/start` به ربات بفرستید
2. "خرید سرویس" را انتخاب کنید
3. یک پلن انتخاب کنید
4. رسید تست آپلود کنید

### تست ادمین:
1. پیام `/admin` بفرستید
2. "مدیریت سفارشات" → "سفارشات در انتظار"
3. سفارش تست را تایید کنید
4. کانفیگ ایجاد شده را بررسی کنید

## 🚀 بهینه‌سازی برای Production

### امنیت:
```bash
# تنظیم مجوزهای فایل
chmod 600 .env vpn_bot.db
chmod 700 logs/ backups/
```

### Performance:
```env
# در فایل .env
DATABASE_URL=postgresql://user:pass@localhost:5432/vpn_bot  # برای حجم بالا
```

### مانیتورینگ:
```bash
# اجرا با systemd (Linux)
sudo cp vpn-bot.service /etc/systemd/system/
sudo systemctl enable vpn-bot
sudo systemctl start vpn-bot
```

## 📁 فایل‌های نمونه

### systemd service (Linux):
```ini
# /etc/systemd/system/vpn-bot.service
[Unit]
Description=VPN Telegram Bot
After=network.target

[Service]
Type=simple
User=vpnbot
WorkingDirectory=/path/to/vpn-telegram-bot
ExecStart=/usr/bin/python3 main.py
Restart=always
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

### logrotate (Linux):
```
# /etc/logrotate.d/vpn-bot
/path/to/vpn-telegram-bot/logs/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    copytruncate
}
```

## 🆘 پشتیبانی

در صورت مشکل:

1. **لاگ‌ها را بررسی کنید**: `logs/bot.log`
2. **دیتابیس را تست کنید**: `python setup_database.py`
3. **GitHub Issues**: [ایجاد issue جدید](https://github.com/yourusername/vpn-telegram-bot/issues)
4. **تلگرام**: [@YourSupportBot](https://t.me/YourSupportBot)

## 📈 مراحل بعدی

پس از راه‌اندازی موفق:

1. **تنظیم بک‌آپ خودکار**
2. **مانیتورینگ سرورها**  
3. **تنظیم SSL برای X-UI**
4. **افزودن سرورهای بیشتر**
5. **سفارشی‌سازی پیام‌ها**

---

🎉 **تبریک! ربات VPN شما آماده است!**

**آخرین بروزرسانی:** $(date)
**نسخه:** 1.0.0 