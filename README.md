# 🚀 VPN Telegram Bot

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

یک ربات تلگرام پیشرفته و کامل برای مدیریت و فروش سرویس‌های VPN با پشتیبانی از پنل X-UI و قابلیت‌های پیشرفته مدیریت چندسرور.

## ✨ ویژگی‌ها

### 🎯 ویژگی‌های کلیدی

- **🔗 مدیریت چندسرور**: پشتیبانی از چندین سرور X-UI با تعادل بار خودکار
- **💳 سیستم پرداخت**: پرداخت کارت به کارت و کیف پول داخلی
- **🎁 سیستم دعوت**: پاداش ۵GB + ۵ روز برای هر دعوت موفق
- **🧪 اکانت تست**: اکانت تست ۱GB برای ۲۴ ساعت (یک بار برای هر کاربر)
- **🔌 سیستم پلاگین**: افزودن آسان پروتکل‌های جدید
- **🛡️ نظارت و هشدار**: بررسی مداوم سلامت سرورها و ارسال هشدار
- **📊 پنل مدیریت**: پنل جامع برای مدیریت سفارشات، کاربران و سرورها

### 🔧 پروتکل‌های پشتیبانی شده

- **VMess**: WebSocket + TCP
- **VLESS**: WebSocket + TCP  
- **Trojan**: WebSocket
- **سایر پروتکل‌ها**: قابلیت افزودن آسان از طریق سیستم پلاگین

### 💰 پلن‌های سرویس

- **🥉 پایه**: ۳۰GB - ۳۰ روز - ۵۰,۰۰۰ تومان
- **🥈 متوسط**: ۶۰GB - ۳۰ روز - ۸۰,۰۰۰ تومان
- **🥇 پیشرفته**: ۱۰۰GB - ۳۰ روز - ۱۲۰,۰۰۰ تومان
- **💎 نامحدود**: نامحدود - ۳۰ روز - ۲۰۰,۰۰۰ تومان

## 📋 پیش‌نیازها

- Python 3.8+
- PostgreSQL یا SQLite
- سرور(های) X-UI راه‌اندازی شده
- Bot Token از [@BotFather](https://t.me/BotFather)
- دسترسی API به سرور(های) X-UI

## 🛠️ نصب و راه‌اندازی

### 1. کلون کردن پروژه

```bash
git clone https://github.com/yourusername/vpn-telegram-bot.git
cd vpn-telegram-bot
```

### 2. نصب وابستگی‌ها

```bash
pip install -r requirements.txt
```

### 3. تنظیم متغیرهای محیط

فایل `.env` را ایجاد کنید:

```env
# Bot Configuration
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=123456789,987654321
BOT_USERNAME=your_bot_username

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/vpn_bot
# یا برای SQLite:
# DATABASE_URL=sqlite:///vpn_bot.db

# Server Configuration
SERVERS_CONFIG='[
    {
        "name": "Server 1",
        "host": "your-server-ip",
        "port": 54321,
        "username": "admin",
        "password": "admin_password",
        "location": "Germany",
        "max_users": 100,
        "is_active": true
    },
    {
        "name": "Server 2", 
        "host": "your-server2-ip",
        "port": 54321,
        "username": "admin",
        "password": "admin_password",
        "location": "Netherlands",
        "max_users": 150,
        "is_active": true
    }
]'

# Payment Configuration
PAYMENT_METHODS='[
    {
        "name": "کارت بانک ملی",
        "card_number": "6037-9919-1234-5678",
        "account_holder": "نام دارنده حساب",
        "is_active": true
    }
]'

# Service Plans (اختیاری - پیش‌فرض از config/settings.py استفاده می‌شود)
SERVICE_PLANS='{
    "basic": {
        "name": "پایه",
        "price": 50000,
        "data_limit": 30,
        "expire_days": 30
    }
}'
```

### 4. راه‌اندازی دیتابیس

```bash
# برای PostgreSQL
createdb vpn_bot

# برای SQLite (خودکار ایجاد می‌شود)
```

### 5. اجرای ربات

```bash
python main.py
```

## 🎮 استفاده از ربات

### 👤 کاربران

1. **شروع کار**: `/start` - شروع کار با ربات
2. **مشاهده سرویس‌ها**: مشاهده اکانت‌های فعال و تاریخچه
3. **خرید سرویس**: انتخاب پلن و پرداخت
4. **شارژ کیف پول**: شارژ کیف پول برای خریدهای آینده
5. **دعوت دوستان**: دریافت لینک دعوت و پاداش
6. **اکانت تست**: دریافت اکانت تست رایگان

### 🔧 ادمین‌ها

دسترسی به پنل مدیریت با دستور `/admin`:

- **📋 مدیریت سفارشات**: بررسی و تایید/رد سفارشات
- **👥 مدیریت کاربران**: مشاهده آمار و مدیریت کاربران
- **🖥️ مدیریت سرورها**: نظارت بر سرورها و وضعیت سلامت
- **📊 آمار سیستم**: مشاهده آمار کلی و درآمد

## 📊 معماری سیستم

### 🏗️ ساختار پروژه

```
vpn-telegram-bot/
├── bot/                    # ربات تلگرام
│   ├── handlers/          # هندلرهای مختلف
│   ├── keyboards.py       # کیبوردهای اینلاین
│   ├── states.py          # وضعیت‌های مکالمه
│   └── bot.py            # کلاس اصلی ربات
├── config/                # تنظیمات
│   └── settings.py       # تنظیمات اصلی
├── database/              # دیتابیس
│   ├── models.py         # مدل‌های دیتابیس
│   └── database.py       # مدیریت دیتابیس
├── services/              # سرویس‌ها
│   ├── xui_api.py        # API سرور X-UI
│   ├── server_manager.py # مدیریت سرورها
│   ├── account_manager.py # مدیریت اکانت‌ها
│   ├── protocol_plugins.py # پلاگین پروتکل‌ها
│   ├── config_templates.py # تمپلیت‌های کانفیگ
│   └── monitoring.py     # نظارت و هشدار
├── requirements.txt       # وابستگی‌ها
├── main.py               # نقطه شروع برنامه
└── README.md            # مستندات
```

### 🔄 جریان کار

```mermaid
graph TD
    A[کاربر انتخاب سرویس] --> B[انتخاب روش پرداخت]
    B --> C[بارگذاری رسید]
    C --> D[ارسال به ادمین]
    D --> E{بررسی ادمین}
    E -->|تایید| F[ایجاد اکانت]
    E -->|رد| G[اطلاع به کاربر]
    F --> H[ارسال کانفیگ]
    H --> I[فعال‌سازی در سرور]
```

## 🔐 امنیت

- **🛡️ احراز هویت**: تمام API ها با username/password محافظت شده
- **🔒 رمزگذاری**: اتصالات HTTPS و SSL
- **👤 کنترل دسترسی**: سطوح دسترسی مختلف (کاربر/ادمین)
- **📝 لاگ‌گذاری**: ثبت کامل فعالیت‌ها
- **🔍 اعتبارسنجی**: اعتبارسنجی کامل ورودی‌ها

## 🚀 ویژگی‌های پیشرفته

### 🎯 تعادل بار خودکار

سیستم به طور خودکار سرور بهینه را برای هر کاربر انتخاب می‌کند:

- بررسی تعداد کاربران فعال
- بررسی وضعیت سلامت سرور
- انتخاب سرور با کمترین بار

### 📊 سیستم نظارت

- **🔍 بررسی سلامت**: هر دقیقه بررسی وضعیت سرورها
- **⚠️ هشدارهای هوشمند**: اطلاع‌رسانی مشکلات
- **📈 آمار عملکرد**: نظارت بر CPU، RAM، و ترافیک
- **🔄 بازیابی خودکار**: تلاش برای بازیابی خودکار

### 🎁 سیستم پاداش

- **دعوت دوستان**: ۵GB + ۵ روز برای هر دعوت موفق
- **اکانت تست**: ۱GB برای ۲۴ ساعت (یک بار)
- **پاداش وفاداری**: قابلیت تعریف پاداش‌های سفارشی

## 🔧 سفارشی‌سازی

### ➕ افزودن پروتکل جدید

```python
from services.protocol_plugins import ProtocolPlugin, register_protocol

@register_protocol("new_protocol")
class NewProtocolPlugin(ProtocolPlugin):
    def generate_config(self, client_data):
        # پیاده‌سازی منطق کانفیگ
        return config_string
```

### 🎨 تغییر رابط کاربری

کیبوردها و پیام‌ها در فایل‌های `keyboards.py` و handlers قابل تغییر هستند.

### 💰 تغییر پلن‌های قیمت

در `config/settings.py`:

```python
SERVICE_PLANS = {
    'custom': {
        'name': 'پلن سفارشی',
        'price': 100000,
        'data_limit': 50,  # GB
        'expire_days': 30
    }
}
```

## 🐛 عیب‌یابی

### مشکلات رایج

1. **ربات پاسخ نمی‌دهد**
   - بررسی TOKEN ربات
   - بررسی اتصال اینترنت

2. **سرور متصل نمی‌شود**
   - بررسی IP و پورت سرور
   - بررسی username/password

3. **دیتابیس خطا می‌دهد**
   - بررسی DATABASE_URL
   - بررسی مجوزهای دیتابیس

### 📝 لاگ‌ها

لاگ‌ها در پوشه `logs/` ذخیره می‌شوند:

```bash
tail -f logs/bot.log  # مشاهده لاگ‌های زنده
```

## 🔄 بروزرسانی

```bash
git pull origin main
pip install -r requirements.txt
python main.py
```

## 🤝 مشارکت

1. Fork کنید
2. Feature branch ایجاد کنید (`git checkout -b feature/AmazingFeature`)
3. تغییرات را commit کنید (`git commit -m 'Add AmazingFeature'`)
4. Push کنید (`git push origin feature/AmazingFeature`)
5. Pull Request باز کنید

## 📄 مجوز

این پروژه تحت مجوز MIT منتشر شده است - فایل [LICENSE](LICENSE) را برای جزئیات مشاهده کنید.

## 🆘 پشتیبانی

- **📫 ایمیل**: support@yourproject.com
- **💬 تلگرام**: [@YourSupportBot](https://t.me/YourSupportBot)
- **🐛 گزارش باگ**: [GitHub Issues](https://github.com/yourusername/vpn-telegram-bot/issues)

## 🌟 تشکر

از تمام کسانی که در توسعه این پروژه مشارکت کرده‌اند، تشکر می‌کنیم.

---

⭐ اگر این پروژه برای شما مفید بود، لطفاً ستاره بدهید!

**ساخته شده با ❤️ در ایران** 