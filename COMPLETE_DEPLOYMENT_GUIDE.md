# 🚀 راهنمای کامل نصب و راه‌اندازی ربات VPN

این راهنما تمام سرویس‌ها، کانفیگ‌ها و systemd service های مورد نیاز برای اجرای کامل ربات را پوشش می‌دهد.

## 📋 فهرست مطالب

1. [تست و اجرای سیستم بک‌آپ X-UI](#1️⃣-سیستم-بک‌آپ-x-ui)
2. [راه‌اندازی Systemd Services](#2️⃣-راه‌اندازی-systemd-services)
3. [نصب و کانفیگ Nginx](#3️⃣-نصب-و-کانفیگ-nginx)
4. [راه‌اندازی FastAPI Subscription Service](#4️⃣-راه‌اندازی-fastapi-subscription-service)
5. [نظارت و لاگ‌ها](#5️⃣-نظارت-و-لاگ‌ها)
6. [بک‌آپ خودکار](#6️⃣-بک‌آپ-خودکار)

---

## 1️⃣ سیستم بک‌آپ X-UI

### 🔍 تست سیستم بک‌آپ X-UI

سیستم بک‌آپ X-UI موجود است و کار می‌کند. بیایید آن را تست کنیم:

```bash
# تست دستی سیستم بک‌آپ
python sync_xui_databases.py
```

**خروجی مورد انتظار:**
```
INFO:xui_db_sync:Saved DB from Iran -> x-ui_dbs/Iran/2024-01-15_14-30.db
INFO:xui_db_sync:Saved DB from Germany -> x-ui_dbs/Germany/2024-01-15_14-30.db
✅ Iran
✅ Germany
```

### 📁 ساختار فایل‌های بک‌آپ

```
x-ui_dbs/
├── Iran/
│   ├── 2024-01-15_14-30.db
│   ├── 2024-01-14_03-00.db
│   └── ...
├── Germany/
│   ├── 2024-01-15_14-30.db
│   ├── 2024-01-14_03-00.db
│   └── ...
```

### ⚙️ راه‌اندازی Cron Job برای بک‌آپ خودکار

```bash
# ایجاد اسکریپت بک‌آپ
cat > /usr/local/bin/xui_backup.sh << 'EOF'
#!/bin/bash
cd /path/to/your/bot/directory
/usr/bin/python3 sync_xui_databases.py

# نگهداری فقط 30 بک‌آپ اخیر برای هر سرور
find x-ui_dbs/ -name "*.db" -type f | sort | head -n -30 | xargs rm -f

echo "$(date): XUI backup completed" >> /var/log/xui_backup.log
EOF

# اعطای مجوز اجرا
chmod +x /usr/local/bin/xui_backup.sh

# اضافه کردن به crontab (هر روز ساعت 3 شب)
crontab -e
```

**اضافه کردن این خط به crontab:**
```cron
0 3 * * * /usr/local/bin/xui_backup.sh >> /var/log/xui_backup.log 2>&1
```

---

## 2️⃣ راه‌اندازی Systemd Services

### 🤖 سرویس اصلی ربات تلگرام

```bash
# ایجاد فایل service
sudo tee /etc/systemd/system/vpn-bot.service > /dev/null << 'EOF'
[Unit]
Description=VPN Telegram Bot
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/your/bot/directory
Environment=PATH=/usr/bin:/usr/local/bin
ExecStart=/usr/bin/python3 start_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# محدودیت منابع
MemoryMax=512M
CPUQuota=50%

# امنیت
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/path/to/your/bot/directory

[Install]
WantedBy=multi-user.target
EOF
```

### 📊 سرویس نظارت (Monitoring)

```bash
# ایجاد فایل service برای نظارت
sudo tee /etc/systemd/system/vpn-monitoring.service > /dev/null << 'EOF'
[Unit]
Description=VPN Bot Monitoring Service
After=network.target vpn-bot.service
Wants=vpn-bot.service

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/your/bot/directory
Environment=PATH=/usr/bin:/usr/local/bin
ExecStart=/usr/bin/python3 -c "
import asyncio
from services.monitoring import monitoring_service
async def main():
    await monitoring_service.start_monitoring()
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await monitoring_service.stop_monitoring()
asyncio.run(main())
"
Restart=always
RestartSec=15
StandardOutput=journal
StandardError=journal

# محدودیت منابع
MemoryMax=256M
CPUQuota=25%

[Install]
WantedBy=multi-user.target
EOF
```

### 🔄 سرویس همگام‌سازی XUI

```bash
# ایجاد timer برای بک‌آپ XUI
sudo tee /etc/systemd/system/xui-backup.service > /dev/null << 'EOF'
[Unit]
Description=X-UI Database Backup
After=network.target

[Service]
Type=oneshot
User=root
WorkingDirectory=/path/to/your/bot/directory
ExecStart=/usr/bin/python3 sync_xui_databases.py
StandardOutput=journal
StandardError=journal
EOF

# ایجاد timer
sudo tee /etc/systemd/system/xui-backup.timer > /dev/null << 'EOF'
[Unit]
Description=Run X-UI backup daily
Requires=xui-backup.service

[Timer]
OnCalendar=daily
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
EOF
```

### 🗂️ فعال‌سازی و مدیریت سرویس‌ها

```bash
# بارگذاری مجدد systemd
sudo systemctl daemon-reload

# فعال‌سازی سرویس‌ها
sudo systemctl enable vpn-bot.service
sudo systemctl enable vpn-monitoring.service
sudo systemctl enable xui-backup.timer

# شروع سرویس‌ها
sudo systemctl start vpn-bot.service
sudo systemctl start vpn-monitoring.service
sudo systemctl start xui-backup.timer

# بررسی وضعیت
sudo systemctl status vpn-bot.service
sudo systemctl status vpn-monitoring.service
sudo systemctl list-timers xui-backup.timer
```

### 📝 دستورات مفید مدیریت سرویس

```bash
# مشاهده لاگ‌ها
sudo journalctl -u vpn-bot.service -f
sudo journalctl -u vpn-monitoring.service -f
sudo journalctl -u xui-backup.service -f

# ریستارت سرویس‌ها
sudo systemctl restart vpn-bot.service
sudo systemctl restart vpn-monitoring.service

# متوقف کردن سرویس‌ها
sudo systemctl stop vpn-bot.service
sudo systemctl stop vpn-monitoring.service

# غیرفعال کردن سرویس‌ها
sudo systemctl disable vpn-bot.service
sudo systemctl disable vpn-monitoring.service
```

---

## 3️⃣ نصب و کانفیگ Nginx

### 📦 نصب Nginx

```bash
# نصب Nginx
sudo apt update
sudo apt install nginx -y

# فعال‌سازی و شروع
sudo systemctl enable nginx
sudo systemctl start nginx
```

### 🔐 راه‌اندازی SSL Certificate

```bash
# ایجاد دایرکتوری SSL
sudo mkdir -p /etc/ssl/subs

# کپی کردن فایل‌های SSL (فایل‌های شما)
sudo cp /root/subsprivate.key /etc/ssl/subs/subs.key
sudo cp /root/subscert.crt /etc/ssl/subs/subs.crt

# تنظیم مجوزها
sudo chmod 600 /etc/ssl/subs/subs.key
sudo chmod 644 /etc/ssl/subs/subs.crt
sudo chown root:root /etc/ssl/subs/subs.*
```

### ⚙️ کانفیگ Nginx برای Subscription Service

```bash
# ایجاد کانفیگ سایت
sudo tee /etc/nginx/sites-available/vpn-subscriptions > /dev/null << 'EOF'
server {
    listen 80;
    server_name subs.prvprt.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name subs.prvprt.com;

    # SSL Configuration
    ssl_certificate /etc/ssl/subs/subs.crt;
    ssl_certificate_key /etc/ssl/subs/subs.key;
    
    # SSL Security Settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-SHA256:ECDHE-RSA-AES256-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Security Headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    
    # Rate Limiting
    limit_req_zone $binary_remote_addr zone=subscription:10m rate=10r/m;
    
    # Main location for subscription service
    location / {
        limit_req zone=subscription burst=5 nodelay;
        
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }
    
    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        access_log off;
    }
    
    # Block access to sensitive paths
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
    
    # Logging
    access_log /var/log/nginx/subscriptions_access.log;
    error_log /var/log/nginx/subscriptions_error.log;
}
EOF

# فعال‌سازی سایت
sudo ln -sf /etc/nginx/sites-available/vpn-subscriptions /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# تست کانفیگ
sudo nginx -t

# ریلود Nginx
sudo systemctl reload nginx
```

### 🛡️ راه‌اندازی Firewall

```bash
# اجازه پورت‌های HTTP/HTTPS
sudo ufw allow 'Nginx Full'
sudo ufw allow 22/tcp
sudo ufw --force enable

# بررسی وضعیت
sudo ufw status
```

---

## 4️⃣ راه‌اندازی FastAPI Subscription Service

### 🔧 سرویس FastAPI

```bash
# ایجاد فایل service برای FastAPI
sudo tee /etc/systemd/system/subscription-api.service > /dev/null << 'EOF'
[Unit]
Description=VPN Subscription API Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/your/bot/directory
Environment=PATH=/usr/bin:/usr/local/bin
ExecStart=/usr/bin/python3 -m uvicorn services.subscription_service:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# محدودیت منابع
MemoryMax=256M
CPUQuota=30%

# امنیت
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/path/to/your/bot/directory

[Install]
WantedBy=multi-user.target
EOF

# فعال‌سازی و شروع
sudo systemctl daemon-reload
sudo systemctl enable subscription-api.service
sudo systemctl start subscription-api.service

# بررسی وضعیت
sudo systemctl status subscription-api.service
```

### 🧪 تست FastAPI Service

```bash
# تست محلی
curl -I http://127.0.0.1:8000/

# تست از طریق Nginx
curl -I https://subs.prvprt.com/

# تست subscription endpoint
curl "https://subs.prvprt.com/sub/VPN12345abc12"
```

### 📊 Health Check Endpoint

```bash
# اضافه کردن health check به FastAPI
cat >> services/subscription_service.py << 'EOF'

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "subscription-api"
    }
EOF
```

---

## 5️⃣ نظارت و لاگ‌ها

### 📋 اسکریپت نظارت جامع

```bash
# ایجاد اسکریپت نظارت
cat > /usr/local/bin/vpn_status.sh << 'EOF'
#!/bin/bash

echo "🚀 VPN Bot System Status - $(date)"
echo "=================================="

# بررسی سرویس‌ها
echo "📊 Services Status:"
for service in vpn-bot vpn-monitoring subscription-api nginx; do
    if systemctl is-active --quiet $service; then
        echo "✅ $service: Running"
    else
        echo "❌ $service: Stopped"
    fi
done

echo ""
echo "🕒 Timers Status:"
systemctl list-timers xui-backup.timer --no-pager

echo ""
echo "💾 Disk Usage:"
df -h | grep -E '/$|/var'

echo ""
echo "🧠 Memory Usage:"
free -h

echo ""
echo "📈 Recent Subscription Requests (last 10):"
tail -10 /var/log/nginx/subscriptions_access.log | awk '{print $4, $5, $7, $9}' | column -t

echo ""
echo "❌ Recent Errors (last 5):"
journalctl -u vpn-bot.service --since "1 hour ago" -p err --no-pager -n 5

echo ""
echo "🔄 XUI Backup Status:"
ls -la x-ui_dbs/*/$(date +%Y-%m-%d)* 2>/dev/null || echo "No backups today"

EOF

chmod +x /usr/local/bin/vpn_status.sh
```

### 📊 راه‌اندازی Logrotate

```bash
# کانفیگ logrotate برای لاگ‌های کاستوم
sudo tee /etc/logrotate.d/vpn-bot > /dev/null << 'EOF'
/var/log/xui_backup.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 root root
}

/var/log/nginx/subscriptions_*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 644 www-data www-data
    postrotate
        systemctl reload nginx
    endscript
}
EOF
```

### 🔔 راه‌اندازی اعلانات سیستم

```bash
# اسکریپت چک سلامت و ارسال اعلان
cat > /usr/local/bin/health_alert.sh << 'EOF'
#!/bin/bash

WEBHOOK_URL="YOUR_TELEGRAM_WEBHOOK_OR_DISCORD_URL"

# بررسی سرویس‌های حیاتی
FAILED_SERVICES=""
for service in vpn-bot subscription-api nginx; do
    if ! systemctl is-active --quiet $service; then
        FAILED_SERVICES="$FAILED_SERVICES $service"
    fi
done

# ارسال اعلان در صورت مشکل
if [ -n "$FAILED_SERVICES" ]; then
    MESSAGE="🚨 Alert: Services down on $(hostname):$FAILED_SERVICES"
    curl -X POST "$WEBHOOK_URL" -H "Content-Type: application/json" \
         -d "{\"text\":\"$MESSAGE\"}"
fi

# بررسی فضای دیسک
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 85 ]; then
    MESSAGE="🚨 Alert: Disk usage is ${DISK_USAGE}% on $(hostname)"
    curl -X POST "$WEBHOOK_URL" -H "Content-Type: application/json" \
         -d "{\"text\":\"$MESSAGE\"}"
fi
EOF

chmod +x /usr/local/bin/health_alert.sh

# اضافه کردن به cron (هر 5 دقیقه)
echo "*/5 * * * * /usr/local/bin/health_alert.sh" | crontab -
```

---

## 6️⃣ بک‌آپ خودکار

### 💾 اسکریپت بک‌آپ جامع

```bash
# ایجاد اسکریپت بک‌آپ کامل
cat > /usr/local/bin/complete_backup.sh << 'EOF'
#!/bin/bash

BACKUP_DIR="/backups/vpn-bot"
DATE=$(date +%Y%m%d_%H%M%S)
BOT_DIR="/path/to/your/bot/directory"

# ایجاد دایرکتوری بک‌آپ
mkdir -p "$BACKUP_DIR"

echo "🚀 Starting complete backup - $DATE"

# بک‌آپ دیتابیس ربات
echo "💾 Backing up bot database..."
cd "$BOT_DIR"
python scripts/migrate_to_new_server.py --backup-only

# بک‌آپ X-UI دیتابیس‌ها
echo "🗂️ Backing up X-UI databases..."
python sync_xui_databases.py

# آرشیو کردن همه چیز
echo "📦 Creating archive..."
tar -czf "$BACKUP_DIR/complete_backup_$DATE.tar.gz" \
    migration_backup/ \
    x-ui_dbs/ \
    .env \
    --exclude='*.pyc' \
    --exclude='__pycache__'

# حذف بک‌آپ‌های قدیمی (نگهداری 7 روز اخیر)
find "$BACKUP_DIR" -name "complete_backup_*.tar.gz" -mtime +7 -delete

echo "✅ Backup completed: $BACKUP_DIR/complete_backup_$DATE.tar.gz"

# ارسال به سرور بک‌آپ خارجی (اختیاری)
# rsync -av "$BACKUP_DIR/complete_backup_$DATE.tar.gz" user@backup-server:/backups/
EOF

chmod +x /usr/local/bin/complete_backup.sh

# اضافه کردن به cron (بک‌آپ کامل هفتگی)
echo "0 2 * * 0 /usr/local/bin/complete_backup.sh >> /var/log/complete_backup.log 2>&1" | crontab -
```

---

## 🎯 خلاصه دستورات نصب

### ⚡ اسکریپت نصب سریع

```bash
# ایجاد اسکریپت نصب همه چیز
cat > install_complete_system.sh << 'EOF'
#!/bin/bash

echo "🚀 Installing VPN Bot Complete System"
echo "====================================="

# متغیرها (تغییر دهید)
BOT_DIR="/opt/vpn-bot"
DOMAIN="subs.prvprt.com"

# نصب وابستگی‌ها
apt update
apt install -y nginx python3 python3-pip git systemd

# نصب Python packages
pip3 install -r requirements.txt

# راه‌اندازی SSL
mkdir -p /etc/ssl/subs
cp /root/subsprivate.key /etc/ssl/subs/subs.key
cp /root/subscert.crt /etc/ssl/subs/subs.crt
chmod 600 /etc/ssl/subs/subs.key

# کانفیگ Nginx
# (کد کانفیگ Nginx از بالا)

# ایجاد systemd services
# (کدهای service از بالا)

# فعال‌سازی سرویس‌ها
systemctl daemon-reload
systemctl enable vpn-bot vpn-monitoring subscription-api nginx xui-backup.timer
systemctl start vpn-bot vpn-monitoring subscription-api nginx xui-backup.timer

echo "✅ Installation completed!"
echo "🔍 Check status: /usr/local/bin/vpn_status.sh"
EOF

chmod +x install_complete_system.sh
```

---

## 📞 تست نهایی سیستم

```bash
# تست همه بخش‌ها
/usr/local/bin/vpn_status.sh

# تست subscription
curl "https://subs.prvprt.com/sub/VPN12345abc12"

# تست بک‌آپ X-UI
python sync_xui_databases.py

# بررسی لاگ‌ها
journalctl -u vpn-bot.service -f
```

**🎉 سیستم شما اکنون کاملاً راه‌اندازی شده و آماده استفاده است!**

---

*این راهنما شامل تمام جزئیات فنی و دستورات مورد نیاز برای راه‌اندازی کامل سیستم است.*