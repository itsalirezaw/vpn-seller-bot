# راهنمای پیکربندی بات VPN

## مرحله 1: ایجاد فایل .env

در پوشه پروژه، فایل `.env` ایجاد کن و موارد زیر را در آن قرار بده:

```env
# =================================
# VPN BOT CONFIGURATION
# =================================

# Bot Token (از @BotFather بگیر)
BOT_TOKEN=your_bot_token_here

# Admin Chat IDs (از @userinfobot بگیر - با کاما جدا کن)
ADMIN_IDS=your_admin_chat_id_here

# Payment Information
PAYMENT_CARD_NUMBER=6037-9977-0000-0000
PAYMENT_CARD_OWNER=نام صاحب کارت

# Subscription Base URL (سرویس FastAPI)
SUBS_BASE_URL=https://subs.example.com

# Database Configuration
DATABASE_URL=sqlite:///./vpn_bot.db
DATABASE_ECHO=false

# =================================
# SERVER CONFIGURATION
# =================================

# Number of servers
SERVER_COUNT=1

# Server 1 Configuration
SERVER_0_NAME=Main Server
SERVER_0_HOST=your_server_ip
SERVER_0_PORT=54321
SERVER_0_WEB_BASE_PATH=/
SERVER_0_USERNAME=admin
SERVER_0_PASSWORD=your_xui_password
SERVER_0_ACTIVE=true

# Server 2 Configuration (اگر سرور دوم داری)
# SERVER_1_NAME=Backup Server
# SERVER_1_HOST=your_second_server_ip
# SERVER_1_PORT=54321
# SERVER_1_WEB_BASE_PATH=/
# SERVER_1_USERNAME=admin
# SERVER_1_PASSWORD=your_second_xui_password
# SERVER_1_ACTIVE=true
```

## مرحله 2: تنظیمات مورد نیاز

### 1. دریافت Bot Token
1. به @BotFather در تلگرام برو
2. `/newbot` را ارسال کن
3. نام و یوزرنیم بات را وارد کن
4. توکن دریافتی را در `BOT_TOKEN` قرار بده

### 2. دریافت Chat ID
1. به @userinfobot در تلگرام برو
2. `/start` را ارسال کن
3. Chat ID خودت را کپی کن و در `ADMIN_IDS` قرار بده

### 3. تنظیمات سرور
- `SERVER_0_HOST`: IP آدرس سرور X-UI
- `SERVER_0_PASSWORD`: پسورد پنل X-UI
- `SERVER_0_PORT`: پورت پنل X-UI (معمولاً 54321)

### 4. تنظیمات کارت بانکی
- `PAYMENT_CARD_NUMBER`: شماره کارت برای پرداخت
- `PAYMENT_CARD_OWNER`: نام صاحب کارت

## مرحله 3: راه‌اندازی دیتابیس

```bash
# اجرای اسکریپت راه‌اندازی
python setup_database.py

# یا استفاده از فایل Batch در ویندوز
database_commands.bat
```

## مرحله 4: اجرای بات (همه چیز خودکار)

```bash
# اجرای اسکریپت راه‌اندازی خودکار
python start_bot.py
# اسکریپت مراحل زیر را خودکار انجام می‌دهد:
#   • بررسی .env و پکیج‌ها
#   • ساخت یا به‌روزرسانی دیتابیس (init_db + default data)
#   • اجرای سرویس FastAPI (اگر با systemd ست شده باشد)
#   • اجرای ربات
```

## مرحله 5: تست بات

1. به بات خودت در تلگرام برو
2. `/start` را ارسال کن
3. باید منوی اصلی نمایش داده شود

## ابزارهای مدیریتی (اسکریپت‌ها)

### 1. همگام‌سازی سرورها و تمپلیت‌ها

پس از هر تغییری در فایل‌های `.env` یا `config/settings.py` این دستور را اجرا کن تا جدول‌های `servers` و `config_templates` با مقادیر جدید **UPSERT** شوند:

```bash
python sync_templates.py
```

- اگر سرور جدید اضافه شده باشد، رکورد آن ساخته می‌شود.
- اگر پورت یا `allowed_servers` تمپلیتی را تغییر دهی، رکورد قدیمی به‌روز می‌شود.
- بعد از آن `systemctl restart subs-api` را بزن تا لینک سابسکرایب کاربران محتوای تازه را تحویل دهد.

### 2. افزودن همهٔ اکانت‌ها به یک سرور تازه

اگر روی سرور جدید (مثلاً `New Server`) به‌‌صورت دستی یک Inbound ساختی و می‌خواهی **تمام اکانت‌های فعلی** را نیز به آن سرور اختصاص دهی تا مصرف حجم‌شان محاسبه شود، اسکریپت زیر را استفاده کن:

```bash
python scripts/assign_all_to_new_server.py
```

در ابتدای فایل می‌توانی دو ثابت را ویرایش کنی:

```python
NEW_SERVER_NAME = "New Server"   # نام دقیق سرور در جدول servers
INBOUND_ID      = 4              # شمارهٔ inbound در پنل X-UI
```

اسکریپت برای هر اکانت:
1. کلاینت را روی سرور جدید می‌سازد (از طریق API)
2. رکورد `server_accounts` را اضافه می‌کند → بنابراین
   • کانفیگ کاربر در Subscription به‌صورت خودکار اضافه می‌شود (پس از ری‌استارت subs-api)
   • مصرف ترافیک روی این سرور در sync_usage ثبت می‌شود و محدودیت حجم درست عمل می‌کند.

> نکته: کانفیگ‌ها و سرورهای قبلی کاربران دست‌نخورده باقی می‌مانند؛ فقط یک ورودی جدید به آن‌ها افزوده می‌شود.

## نکات مهم

- حتماً پورت 54321 را در فایروال سرور باز کن
- X-UI باید قبلاً نصب شده باشد
- برای چندین سرور، `SERVER_COUNT` را افزایش بده
- فایل `.env` را در گیت commit نکن (امنیتی)
- فایل `start_bot.py` اکنون پیش از اجرای ربات، دیتابیس را **به‌صورت خودکار** ایجاد یا همگام می‌کند؛ بنابراین اجرای `setup_database.py` الزامی نیست (مگر مهاجرت دستی).
- در صورت تغییر سرورها یا تمپلیت‌ها، لینک سابسکرایب کاربران در لحظهٔ درخواست به‌روز می‌شود.

## مثال کامل .env

```env
BOT_TOKEN=1234567890:AABBCCDDEEFFGGHHIIJJKKLLMMNNOOPPQQRRss
ADMIN_IDS=123456789,987654321
PAYMENT_CARD_NUMBER=6037-9977-1234-5678
PAYMENT_CARD_OWNER=علی احمدی
DATABASE_URL=sqlite:///./vpn_bot.db
DATABASE_ECHO=false
SERVER_COUNT=2
SERVER_0_NAME=Iran Server
SERVER_0_HOST=185.1.2.3
SERVER_0_PORT=54321
SERVER_0_WEB_BASE_PATH=/
SERVER_0_USERNAME=admin
SERVER_0_PASSWORD=mypassword123
SERVER_0_ACTIVE=true
SERVER_1_NAME=Germany Server
SERVER_1_HOST=194.5.6.7
SERVER_1_PORT=54321
SERVER_1_WEB_BASE_PATH=/
SERVER_1_USERNAME=admin
SERVER_1_PASSWORD=mypassword456
SERVER_1_ACTIVE=true
``` 