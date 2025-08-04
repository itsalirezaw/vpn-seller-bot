#!/bin/bash

# 🚀 اسکریپت راه‌اندازی Systemd Services برای ربات VPN
# این اسکریپت تمام سرویس‌های مورد نیاز را ایجاد و فعال می‌کند

set -e  # خروج در صورت خطا

# رنگ‌ها برای نمایش بهتر
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# تابع نمایش پیام‌ها
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# بررسی اجرا با دسترسی root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "این اسکریپت باید با دسترسی root اجرا شود"
        print_error "لطفاً با sudo اجرا کنید: sudo $0"
        exit 1
    fi
}

# تشخیص مسیر ربات
detect_bot_directory() {
    local current_dir=$(pwd)
    
    # بررسی فایل‌های کلیدی
    if [[ -f "$current_dir/start_bot.py" && -f "$current_dir/requirements.txt" && -d "$current_dir/bot" ]]; then
        echo "$current_dir"
        return 0
    fi
    
    # بررسی مسیرهای محتمل
    local possible_paths=(
        "/opt/vpn-bot"
        "/home/*/vpn-bot"
        "/root/vpn-bot"
        "/var/www/vpn-bot"
    )
    
    for path in "${possible_paths[@]}"; do
        if [[ -f "$path/start_bot.py" ]]; then
            echo "$path"
            return 0
        fi
    done
    
    return 1
}

# پاک کردن سرویس‌های موجود
cleanup_existing_services() {
    print_status "پاک کردن سرویس‌های موجود..."
    
    # متوقف کردن سرویس‌ها
    for service in vpn-bot vpn-monitoring subscription-api; do
        if systemctl is-active --quiet $service 2>/dev/null; then
            print_status "متوقف کردن $service..."
            systemctl stop $service
        fi
    done
    
    # غیرفعال کردن سرویس‌ها
    for service in vpn-bot vpn-monitoring subscription-api; do
        if systemctl is-enabled --quiet $service 2>/dev/null; then
            print_status "غیرفعال کردن $service..."
            systemctl disable $service
        fi
    done
    
    # حذف فایل‌های سرویس
    for service in vpn-bot vpn-monitoring subscription-api xui-backup; do
        if [[ -f "/etc/systemd/system/$service.service" ]]; then
            print_status "حذف $service.service..."
            rm -f "/etc/systemd/system/$service.service"
        fi
    done
    
    # حذف timer
    if [[ -f "/etc/systemd/system/xui-backup.timer" ]]; then
        print_status "حذف xui-backup.timer..."
        rm -f "/etc/systemd/system/xui-backup.timer"
    fi
    
    # بارگذاری مجدد systemd
    systemctl daemon-reload
    
    print_success "سرویس‌های موجود پاک شدند"
}

# دریافت اطلاعات از کاربر
get_user_input() {
    print_status "دریافت اطلاعات پیکربندی..."
    
    # تشخیص مسیر ربات
    if BOT_DIR=$(detect_bot_directory); then
        print_success "مسیر ربات تشخیص داده شد: $BOT_DIR"
        read -p "آیا این مسیر صحیح است؟ [Y/n]: " confirm
        if [[ $confirm =~ ^[Nn]$ ]]; then
            read -p "مسیر کامل ربات را وارد کنید: " BOT_DIR
        fi
    else
        read -p "مسیر کامل ربات را وارد کنید: " BOT_DIR
    fi
    
    # بررسی وجود مسیر
    if [[ ! -d "$BOT_DIR" ]]; then
        print_error "مسیر وارد شده وجود ندارد: $BOT_DIR"
        exit 1
    fi
    
    if [[ ! -f "$BOT_DIR/start_bot.py" ]]; then
        print_error "فایل start_bot.py در مسیر وارد شده یافت نشد"
        exit 1
    fi
    
    # تشخیص Python path
    PYTHON_PATH=$(which python3)
    if [[ -z "$PYTHON_PATH" ]]; then
        PYTHON_PATH="/usr/bin/python3"
        print_warning "Python3 یافت نشد، از مسیر پیش‌فرض استفاده می‌شود: $PYTHON_PATH"
    else
        print_success "Python3 یافت شد: $PYTHON_PATH"
    fi
    
    # تنظیمات منابع سیستم
    echo ""
    print_status "تنظیمات منابع سیستم:"
    read -p "حافظه محدود برای ربات (پیش‌فرض: 512M): " BOT_MEMORY
    BOT_MEMORY=${BOT_MEMORY:-512M}
    
    read -p "CPU محدود برای ربات (پیش‌فرض: 50%): " BOT_CPU
    BOT_CPU=${BOT_CPU:-50%}
    
    read -p "حافظه محدود برای نظارت (پیش‌فرض: 256M): " MONITOR_MEMORY
    MONITOR_MEMORY=${MONITOR_MEMORY:-256M}
    
    read -p "CPU محدود برای نظارت (پیش‌فرض: 25%): " MONITOR_CPU
    MONITOR_CPU=${MONITOR_CPU:-25%}
    
    read -p "حافظه محدود برای FastAPI (پیش‌فرض: 256M): " API_MEMORY
    API_MEMORY=${API_MEMORY:-256M}
    
    read -p "CPU محدود برای FastAPI (پیش‌فرض: 30%): " API_CPU
    API_CPU=${API_CPU:-30%}
    
    # کاربر اجرا
    echo ""
    read -p "کاربر اجرای سرویس‌ها (پیش‌فرض: root): " SERVICE_USER
    SERVICE_USER=${SERVICE_USER:-root}
    
    # نمایش خلاصه
    echo ""
    print_status "خلاصه تنظیمات:"
    echo "مسیر ربات: $BOT_DIR"
    echo "Python Path: $PYTHON_PATH"
    echo "کاربر سرویس: $SERVICE_USER"
    echo "منابع ربات: $BOT_MEMORY RAM, $BOT_CPU CPU"
    echo "منابع نظارت: $MONITOR_MEMORY RAM, $MONITOR_CPU CPU"
    echo "منابع FastAPI: $API_MEMORY RAM, $API_CPU CPU"
    echo ""
    
    read -p "آیا تنظیمات صحیح است؟ [Y/n]: " confirm
    if [[ $confirm =~ ^[Nn]$ ]]; then
        print_error "عملیات لغو شد"
        exit 0
    fi
}

# ایجاد سرویس ربات اصلی
create_bot_service() {
    print_status "ایجاد سرویس ربات تلگرام..."
    
    cat > /etc/systemd/system/vpn-bot.service << EOF
[Unit]
Description=VPN Telegram Bot
Documentation=https://github.com/your-repo/vpn-bot
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$BOT_DIR
Environment=PATH=/usr/bin:/usr/local/bin:/bin
Environment=PYTHONPATH=$BOT_DIR
ExecStartPre=/bin/sleep 5
ExecStart=$PYTHON_PATH start_bot.py
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10
TimeoutStartSec=30
TimeoutStopSec=10

# لاگینگ
StandardOutput=journal
StandardError=journal
SyslogIdentifier=vpn-bot

# محدودیت منابع
MemoryMax=$BOT_MEMORY
CPUQuota=$BOT_CPU

# امنیت (تنظیم شده برای دسترسی به /root)
NoNewPrivileges=true
ProtectSystem=no
ProtectHome=no
ReadWritePaths=$BOT_DIR
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

    print_success "سرویس ربات ایجاد شد"
}

# ایجاد سرویس نظارت
create_monitoring_service() {
    print_status "ایجاد سرویس نظارت..."
    
    # ایجاد فایل جداگانه برای monitoring
    cat > $BOT_DIR/start_monitoring.py << 'MONITOR_SCRIPT'
#!/usr/bin/env python3
"""
Monitoring service starter script
"""

import asyncio
import sys
import os

# Add the bot directory to Python path
sys.path.insert(0, '/root/v3')

from services.monitoring import monitoring_service

async def main():
    try:
        print("Starting monitoring service...")
        await monitoring_service.start_monitoring()
        print("Monitoring service started successfully")
        
        # Keep the service running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("Stopping monitoring service...")
        await monitoring_service.stop_monitoring()
    except Exception as e:
        print(f'Monitoring error: {e}')
        raise

if __name__ == '__main__':
    asyncio.run(main())
MONITOR_SCRIPT

    # اعطای مجوز اجرا
    chmod +x $BOT_DIR/start_monitoring.py
    
    cat > /etc/systemd/system/vpn-monitoring.service << EOF
[Unit]
Description=VPN Bot Monitoring Service
Documentation=https://github.com/your-repo/vpn-bot
After=network.target vpn-bot.service
Wants=vpn-bot.service
PartOf=vpn-bot.service

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$BOT_DIR
Environment=PATH=/usr/bin:/usr/local/bin:/bin
Environment=PYTHONPATH=$BOT_DIR
ExecStart=$PYTHON_PATH $BOT_DIR/start_monitoring.py
Restart=always
RestartSec=15
TimeoutStartSec=60
TimeoutStopSec=20

# لاگینگ
StandardOutput=journal
StandardError=journal
SyslogIdentifier=vpn-monitoring

# محدودیت منابع
MemoryMax=$MONITOR_MEMORY
CPUQuota=$MONITOR_CPU

# امنیت (تنظیم شده برای دسترسی به /root)
NoNewPrivileges=true
ProtectSystem=no
ProtectHome=no
ReadWritePaths=$BOT_DIR
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

    print_success "سرویس نظارت ایجاد شد"
}

# ایجاد سرویس FastAPI
create_fastapi_service() {
    print_status "ایجاد سرویس FastAPI..."
    
    # بررسی نصب uvicorn
    if ! command -v uvicorn &> /dev/null; then
        print_warning "uvicorn نصب نیست، نصب می‌شود..."
        pip3 install uvicorn
    fi
    
    cat > /etc/systemd/system/subscription-api.service << EOF
[Unit]
Description=VPN Subscription API Service
Documentation=https://github.com/your-repo/vpn-bot
After=network.target
Wants=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$BOT_DIR
Environment=PATH=/usr/bin:/usr/local/bin:/bin
Environment=PYTHONPATH=$BOT_DIR
ExecStart=$PYTHON_PATH -m uvicorn services.subscription_service:app --host 127.0.0.1 --port 8000 --workers 2 --access-log
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=5
TimeoutStartSec=30
TimeoutStopSec=10

# لاگینگ
StandardOutput=journal
StandardError=journal
SyslogIdentifier=subscription-api

# محدودیت منابع
MemoryMax=$API_MEMORY
CPUQuota=$API_CPU

# امنیت (تنظیم شده برای دسترسی به /root)
NoNewPrivileges=true
ProtectSystem=no
ProtectHome=no
ReadWritePaths=$BOT_DIR
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

    print_success "سرویس FastAPI ایجاد شد"
}

# ایجاد سرویس بک‌آپ X-UI
create_xui_backup_service() {
    print_status "ایجاد سرویس بک‌آپ X-UI..."
    
    # سرویس اصلی
    cat > /etc/systemd/system/xui-backup.service << EOF
[Unit]
Description=X-UI Database Backup Service
Documentation=https://github.com/your-repo/vpn-bot
After=network.target

[Service]
Type=oneshot
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$BOT_DIR
Environment=PATH=/usr/bin:/usr/local/bin:/bin
Environment=PYTHONPATH=$BOT_DIR
ExecStartPre=/bin/mkdir -p $BOT_DIR/x-ui_dbs
ExecStart=$PYTHON_PATH sync_xui_databases.py
ExecStartPost=/bin/bash -c 'find $BOT_DIR/x-ui_dbs -name "*.db" -mtime +30 -delete'
TimeoutStartSec=300

# لاگینگ
StandardOutput=journal
StandardError=journal
SyslogIdentifier=xui-backup

# امنیت (تنظیم شده برای دسترسی به /root)
NoNewPrivileges=true
ProtectSystem=no
ProtectHome=no
ReadWritePaths=$BOT_DIR
PrivateTmp=true
EOF

    # Timer برای اجرای روزانه
    cat > /etc/systemd/system/xui-backup.timer << EOF
[Unit]
Description=Run X-UI backup daily at 3 AM
Documentation=https://github.com/your-repo/vpn-bot
Requires=xui-backup.service

[Timer]
OnCalendar=daily
Persistent=true
RandomizedDelaySec=300
AccuracySec=1m

[Install]
WantedBy=timers.target
EOF

    print_success "سرویس و Timer بک‌آپ X-UI ایجاد شد"
}

# ایجاد سرویس پاک کردن سفارشات ناقص
create_cleanup_service() {
    print_status "ایجاد سرویس پاک کردن سفارشات ناقص..."
    
    # ایجاد دایرکتوری لاگ
    mkdir -p /var/log/vpn_bot
    
    # سرویس اصلی
    cat > /etc/systemd/system/vpn-bot-cleanup.service << EOF
[Unit]
Description=VPN Bot Cleanup Service
Description=Cleans up incomplete orders every 3 minutes
After=network.target

[Service]
Type=oneshot
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$BOT_DIR
Environment=PYTHONPATH=$BOT_DIR
ExecStart=$PYTHON_PATH $BOT_DIR/scripts/cleanup_incomplete_orders.py
StandardOutput=journal
StandardError=journal
SyslogIdentifier=vpn-bot-cleanup

# امنیت
NoNewPrivileges=true
ProtectSystem=no
ProtectHome=no
ReadWritePaths=$BOT_DIR /var/log/vpn_bot
PrivateTmp=true
EOF

    # Timer برای اجرای هر 3 دقیقه
    cat > /etc/systemd/system/vpn-bot-cleanup.timer << EOF
[Unit]
Description=VPN Bot Cleanup Timer
Description=Run cleanup service every 3 minutes
Requires=vpn-bot-cleanup.service

[Timer]
Unit=vpn-bot-cleanup.service
OnBootSec=1min
OnUnitActiveSec=3min
AccuracySec=30s

[Install]
WantedBy=timers.target
EOF

    print_success "سرویس و Timer پاک کردن سفارشات ناقص ایجاد شد"
}

# ایجاد اسکریپت کمکی مدیریت
create_management_script() {
    print_status "ایجاد اسکریپت مدیریت سرویس‌ها..."
    
    cat > /usr/local/bin/vpn-manage << 'EOF'
#!/bin/bash

# اسکریپت مدیریت سرویس‌های ربات VPN

SERVICES=("vpn-bot" "vpn-monitoring" "subscription-api")
TIMERS=("xui-backup.timer" "vpn-bot-cleanup.timer")

show_help() {
    echo "استفاده: vpn-manage [COMMAND]"
    echo ""
    echo "دستورات:"
    echo "  status    - نمایش وضعیت همه سرویس‌ها"
    echo "  start     - شروع همه سرویس‌ها"
    echo "  stop      - توقف همه سرویس‌ها"
    echo "  restart   - راه‌اندازی مجدد همه سرویس‌ها"
    echo "  logs      - نمایش لاگ‌های زنده"
    echo "  enable    - فعال‌سازی همه سرویس‌ها"
    echo "  disable   - غیرفعال‌سازی همه سرویس‌ها"
    echo "  health    - بررسی سلامت سیستم"
}

show_status() {
    echo "🚀 وضعیت سرویس‌های ربات VPN"
    echo "================================"
    
    for service in "${SERVICES[@]}"; do
        if systemctl is-active --quiet "$service"; then
            echo "✅ $service: فعال"
        else
            echo "❌ $service: غیرفعال"
        fi
    done
    
    echo ""
    echo "⏰ وضعیت Timer ها:"
    for timer in "${TIMERS[@]}"; do
        if systemctl is-active --quiet "$timer"; then
            echo "✅ $timer: فعال"
            systemctl list-timers "$timer" --no-pager | tail -n +2
        else
            echo "❌ $timer: غیرفعال"
        fi
    done
}

start_services() {
    echo "🚀 شروع سرویس‌ها..."
    for service in "${SERVICES[@]}"; do
        echo "شروع $service..."
        systemctl start "$service"
    done
    
    for timer in "${TIMERS[@]}"; do
        echo "شروع $timer..."
        systemctl start "$timer"
    done
    
    echo "✅ همه سرویس‌ها شروع شدند"
}

stop_services() {
    echo "⏹️ توقف سرویس‌ها..."
    for service in "${SERVICES[@]}"; do
        echo "توقف $service..."
        systemctl stop "$service"
    done
    
    for timer in "${TIMERS[@]}"; do
        echo "توقف $timer..."
        systemctl stop "$timer"
    done
    
    echo "✅ همه سرویس‌ها متوقف شدند"
}

restart_services() {
    echo "🔄 راه‌اندازی مجدد سرویس‌ها..."
    for service in "${SERVICES[@]}"; do
        echo "راه‌اندازی مجدد $service..."
        systemctl restart "$service"
    done
    
    echo "✅ همه سرویس‌ها راه‌اندازی مجدد شدند"
}

show_logs() {
    echo "📋 نمایش لاگ‌های زنده (Ctrl+C برای خروج)..."
    journalctl -u vpn-bot.service -u vpn-monitoring.service -u subscription-api.service -u xui-backup.service -u vpn-bot-cleanup.service -f
}

enable_services() {
    echo "🔧 فعال‌سازی سرویس‌ها..."
    for service in "${SERVICES[@]}"; do
        systemctl enable "$service"
    done
    
    for timer in "${TIMERS[@]}"; do
        systemctl enable "$timer"
    done
    
    echo "✅ همه سرویس‌ها فعال شدند"
}

disable_services() {
    echo "🔧 غیرفعال‌سازی سرویس‌ها..."
    for service in "${SERVICES[@]}"; do
        systemctl disable "$service"
    done
    
    for timer in "${TIMERS[@]}"; do
        systemctl disable "$timer"
    done
    
    echo "✅ همه سرویس‌ها غیرفعال شدند"
}

health_check() {
    echo "🏥 بررسی سلامت سیستم"
    echo "====================="
    
    # بررسی سرویس‌ها
    failed_services=0
    for service in "${SERVICES[@]}"; do
        if ! systemctl is-active --quiet "$service"; then
            echo "❌ $service: غیرفعال"
            ((failed_services++))
        fi
    done
    
    if [ $failed_services -eq 0 ]; then
        echo "✅ همه سرویس‌ها فعال هستند"
    else
        echo "⚠️ $failed_services سرویس غیرفعال"
    fi
    
    # بررسی فضای دیسک
    disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ "$disk_usage" -gt 85 ]; then
        echo "⚠️ فضای دیسک کم: ${disk_usage}%"
    else
        echo "✅ فضای دیسک مناسب: ${disk_usage}%"
    fi
    
    # بررسی حافظه
    memory_usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    if [ "$memory_usage" -gt 90 ]; then
        echo "⚠️ حافظه کم: ${memory_usage}%"
    else
        echo "✅ حافظه مناسب: ${memory_usage}%"
    fi
}

case "$1" in
    status) show_status ;;
    start) start_services ;;
    stop) stop_services ;;
    restart) restart_services ;;
    logs) show_logs ;;
    enable) enable_services ;;
    disable) disable_services ;;
    health) health_check ;;
    *) show_help ;;
esac
EOF

    chmod +x /usr/local/bin/vpn-manage
    print_success "اسکریپت مدیریت در /usr/local/bin/vpn-manage ایجاد شد"
}

# فعال‌سازی سرویس‌ها
enable_and_start_services() {
    print_status "بارگذاری مجدد systemd..."
    systemctl daemon-reload
    
    print_status "فعال‌سازی سرویس‌ها..."
    systemctl enable vpn-bot.service
    systemctl enable vpn-monitoring.service
    systemctl enable subscription-api.service
    systemctl enable xui-backup.timer
    systemctl enable vpn-bot-cleanup.timer
    
    echo ""
    read -p "آیا می‌خواهید سرویس‌ها را الان شروع کنید؟ [Y/n]: " start_now
    
    if [[ ! $start_now =~ ^[Nn]$ ]]; then
        print_status "شروع سرویس‌ها..."
        systemctl start vpn-bot.service
        sleep 5
        systemctl start vpn-monitoring.service
        systemctl start subscription-api.service
        systemctl start xui-backup.timer
        systemctl start vpn-bot-cleanup.timer
        
        print_success "همه سرویس‌ها شروع شدند"
        
        echo ""
        print_status "بررسی وضعیت نهایی..."
        /usr/local/bin/vpn-manage status
    else
        print_warning "سرویس‌ها فعال شدند اما شروع نشدند"
        print_warning "برای شروع: vpn-manage start"
    fi
}

# نمایش خلاصه نهایی
show_final_summary() {
    echo ""
    print_success "🎉 راه‌اندازی سرویس‌ها کامل شد!"
    echo ""
    echo "📋 دستورات مفید:"
    echo "• vpn-manage status    - وضعیت سرویس‌ها"
    echo "• vpn-manage logs      - مشاهده لاگ‌ها"
    echo "• vpn-manage restart   - راه‌اندازی مجدد"
    echo "• vpn-manage health    - بررسی سلامت"
    echo ""
    echo "📂 فایل‌های سرویس:"
    echo "• /etc/systemd/system/vpn-bot.service"
    echo "• /etc/systemd/system/vpn-monitoring.service"
    echo "• /etc/systemd/system/subscription-api.service"
    echo "• /etc/systemd/system/xui-backup.service"
    echo "• /etc/systemd/system/xui-backup.timer"
    echo "• /etc/systemd/system/vpn-bot-cleanup.service"
    echo "• /etc/systemd/system/vpn-bot-cleanup.timer"
    echo ""
    echo "🔍 برای بررسی وضعیت: vpn-manage status"
}

# اجرای اصلی
main() {
    echo "🚀 راه‌اندازی Systemd Services برای ربات VPN"
    echo "============================================="
    echo ""
    
    check_root
    get_user_input
    
    echo ""
    print_status "شروع ایجاد سرویس‌ها..."
    
    cleanup_existing_services
    create_bot_service
    create_monitoring_service
    create_fastapi_service
    create_xui_backup_service
    create_cleanup_service
    create_management_script
    
    enable_and_start_services
    show_final_summary
}

# اجرا
main "$@"