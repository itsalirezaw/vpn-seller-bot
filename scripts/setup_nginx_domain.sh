#!/bin/bash

# 🌐 اسکریپت نصب و کانفیگ Nginx با دامنه دلخواه
# این اسکریپت Nginx را نصب و دامنه subscription را تنظیم می‌کند

set -e  # خروج در صورت خطا

# رنگ‌ها برای نمایش بهتر
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

print_header() {
    echo -e "${CYAN}=== $1 ===${NC}"
}

# بررسی اجرا با دسترسی root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "این اسکریپت باید با دسترسی root اجرا شود"
        print_error "لطفاً با sudo اجرا کنید: sudo $0"
        exit 1
    fi
}

# دریافت اطلاعات دامنه و SSL از کاربر
get_domain_info() {
    print_header "تنظیمات دامنه و SSL"
    
    # دریافت نام دامنه
    while true; do
        read -p "نام دامنه subscription (مثال: subs.example.com): " DOMAIN
        if [[ -n "$DOMAIN" ]]; then
            # بررسی فرمت دامنه
            if [[ $DOMAIN =~ ^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$ ]]; then
                break
            else
                print_error "فرمت دامنه صحیح نیست. لطفاً مجدداً وارد کنید"
            fi
        else
            print_error "نام دامنه نمی‌تواند خالی باشد"
        fi
    done
    
    # تنظیمات SSL
    echo ""
    print_status "تنظیمات SSL Certificate:"
    echo "1) استفاده از فایل‌های SSL موجود"
    echo "2) ایجاد SSL خودامضا (Self-signed)"
    echo "3) استفاده از Let's Encrypt (Certbot)"
    echo "4) بدون SSL (فقط HTTP)"
    
    while true; do
        read -p "انتخاب کنید [1-4]: " SSL_CHOICE
        case $SSL_CHOICE in
            1|2|3|4) break ;;
            *) print_error "گزینه نامعتبر، لطفاً 1 تا 4 را انتخاب کنید" ;;
        esac
    done
    
    # تنظیمات بر اساس انتخاب SSL
    case $SSL_CHOICE in
        1)
            SSL_MODE="existing"
            get_existing_ssl_paths
            ;;
        2)
            SSL_MODE="selfsigned"
            ;;
        3)
            SSL_MODE="letsencrypt"
            get_letsencrypt_info
            ;;
        4)
            SSL_MODE="none"
            print_warning "بدون SSL، ارتباط ایمن نخواهد بود"
            ;;
    esac
    
    # تنظیمات FastAPI
    echo ""
    read -p "پورت FastAPI (پیش‌فرض: 8000): " FASTAPI_PORT
    FASTAPI_PORT=${FASTAPI_PORT:-8000}
    
    read -p "IP FastAPI (پیش‌فرض: 127.0.0.1): " FASTAPI_HOST
    FASTAPI_HOST=${FASTAPI_HOST:-127.0.0.1}
    
    # تنظیمات Rate Limiting
    echo ""
    print_status "تنظیمات Rate Limiting:"
    read -p "محدودیت درخواست در دقیقه (پیش‌فرض: 10): " RATE_LIMIT
    RATE_LIMIT=${RATE_LIMIT:-10}
    
    read -p "حداکثر درخواست همزمان (پیش‌فرض: 5): " RATE_BURST
    RATE_BURST=${RATE_BURST:-5}
    
    # نمایش خلاصه
    echo ""
    print_header "خلاصه تنظیمات"
    echo "دامنه: $DOMAIN"
    echo "SSL: $SSL_MODE"
    echo "FastAPI: $FASTAPI_HOST:$FASTAPI_PORT"
    echo "Rate Limit: $RATE_LIMIT/min, Burst: $RATE_BURST"
    
    if [[ $SSL_MODE == "existing" ]]; then
        echo "SSL Certificate: $SSL_CERT_PATH"
        echo "SSL Key: $SSL_KEY_PATH"
    fi
    
    echo ""
    read -p "آیا تنظیمات صحیح است؟ [Y/n]: " confirm
    if [[ $confirm =~ ^[Nn]$ ]]; then
        print_error "عملیات لغو شد"
        exit 0
    fi
}

# دریافت مسیر فایل‌های SSL موجود
get_existing_ssl_paths() {
    echo ""
    print_status "مسیر فایل‌های SSL موجود:"
    
    # پیشنهاد مسیرهای محتمل
    echo "مسیرهای محتمل:"
    echo "• /etc/ssl/subs/"
    echo "• /etc/nginx/ssl/"
    echo "• /root/"
    echo "• /etc/letsencrypt/live/$DOMAIN/"
    
    while true; do
        read -p "مسیر فایل Certificate (.crt یا .pem): " SSL_CERT_PATH
        if [[ -f "$SSL_CERT_PATH" ]]; then
            break
        else
            print_error "فایل یافت نشد: $SSL_CERT_PATH"
        fi
    done
    
    while true; do
        read -p "مسیر فایل Private Key (.key): " SSL_KEY_PATH
        if [[ -f "$SSL_KEY_PATH" ]]; then
            break
        else
            print_error "فایل یافت نشد: $SSL_KEY_PATH"
        fi
    done
    
    # تنظیم مجوزها
    chmod 644 "$SSL_CERT_PATH"
    chmod 600 "$SSL_KEY_PATH"
    chown root:root "$SSL_CERT_PATH" "$SSL_KEY_PATH"
}

# دریافت اطلاعات Let's Encrypt
get_letsencrypt_info() {
    echo ""
    read -p "ایمیل برای Let's Encrypt: " LETSENCRYPT_EMAIL
    
    if [[ ! $LETSENCRYPT_EMAIL =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        print_error "فرمت ایمیل صحیح نیست"
        exit 1
    fi
    
    print_warning "اطمینان حاصل کنید که دامنه $DOMAIN به این سرور اشاره می‌کند"
    read -p "ادامه می‌دهید؟ [y/N]: " continue_le
    if [[ ! $continue_le =~ ^[Yy]$ ]]; then
        print_error "عملیات لغو شد"
        exit 0
    fi
}

# نصب Nginx
install_nginx() {
    print_header "نصب Nginx"
    
    # بررسی نصب قبلی
    if command -v nginx &> /dev/null; then
        print_success "Nginx قبلاً نصب شده است"
        NGINX_VERSION=$(nginx -v 2>&1 | cut -d' ' -f3)
        print_status "نسخه: $NGINX_VERSION"
    else
        print_status "نصب Nginx..."
        apt update
        apt install -y nginx
        print_success "Nginx نصب شد"
    fi
    
    # فعال‌سازی و شروع
    systemctl enable nginx
    if ! systemctl is-active --quiet nginx; then
        systemctl start nginx
        print_success "Nginx شروع شد"
    fi
}

# ایجاد فایل‌های SSL خودامضا
create_selfsigned_ssl() {
    print_header "ایجاد SSL خودامضا"
    
    SSL_DIR="/etc/ssl/nginx"
    mkdir -p "$SSL_DIR"
    
    SSL_CERT_PATH="$SSL_DIR/$DOMAIN.crt"
    SSL_KEY_PATH="$SSL_DIR/$DOMAIN.key"
    
    print_status "ایجاد کلید و گواهی..."
    
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$SSL_KEY_PATH" \
        -out "$SSL_CERT_PATH" \
        -subj "/C=IR/ST=Tehran/L=Tehran/O=VPN Bot/CN=$DOMAIN"
    
    chmod 600 "$SSL_KEY_PATH"
    chmod 644 "$SSL_CERT_PATH"
    
    print_success "SSL خودامضا ایجاد شد"
    print_warning "گواهی خودامضا امن نیست و مرورگرها هشدار نمایش می‌دهند"
}

# نصب و کانفیگ Let's Encrypt
setup_letsencrypt() {
    print_header "راه‌اندازی Let's Encrypt"
    
    # نصب Certbot
    if ! command -v certbot &> /dev/null; then
        print_status "نصب Certbot..."
        apt install -y certbot python3-certbot-nginx
    fi
    
    # ایجاد گواهی
    print_status "دریافت گواهی SSL..."
    certbot --nginx -d "$DOMAIN" --email "$LETSENCRYPT_EMAIL" --agree-tos --non-interactive
    
    # تنظیم تمدید خودکار
    if ! crontab -l 2>/dev/null | grep -q certbot; then
        (crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | crontab -
        print_success "تمدید خودکار SSL تنظیم شد"
    fi
    
    SSL_CERT_PATH="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
    SSL_KEY_PATH="/etc/letsencrypt/live/$DOMAIN/privkey.pem"
}

# ایجاد کانفیگ Nginx
create_nginx_config() {
    print_header "ایجاد کانفیگ Nginx"
    
    CONFIG_FILE="/etc/nginx/sites-available/vpn-subscriptions"
    
    # شروع کانفیگ
    cat > "$CONFIG_FILE" << EOF
# VPN Subscription Service Configuration
# Domain: $DOMAIN
# Generated: $(date)

# Rate limiting zones
limit_req_zone \$binary_remote_addr zone=subscription:10m rate=${RATE_LIMIT}r/m;
limit_req_zone \$binary_remote_addr zone=api:10m rate=30r/m;

# Upstream FastAPI
upstream fastapi_backend {
    server $FASTAPI_HOST:$FASTAPI_PORT;
    keepalive 32;
}
EOF

    # HTTP server (redirect به HTTPS یا serve کردن)
    if [[ $SSL_MODE != "none" ]]; then
        cat >> "$CONFIG_FILE" << EOF

# HTTP server - Redirect to HTTPS
server {
    listen 80;
    server_name $DOMAIN;
    
    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    
    # Let's Encrypt challenge location
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    
    # Redirect all other traffic to HTTPS
    location / {
        return 301 https://\$server_name\$request_uri;
    }
}
EOF
    fi

    # HTTPS server یا HTTP server
    if [[ $SSL_MODE != "none" ]]; then
        cat >> "$CONFIG_FILE" << EOF

# HTTPS server
server {
    listen 443 ssl http2;
    server_name $DOMAIN;

    # SSL Configuration
    ssl_certificate $SSL_CERT_PATH;
    ssl_certificate_key $SSL_KEY_PATH;
    
    # SSL Security Settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_stapling on;
    ssl_stapling_verify on;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
EOF
    else
        cat >> "$CONFIG_FILE" << EOF

# HTTP server
server {
    listen 80;
    server_name $DOMAIN;
EOF
    fi

    # ادامه کانفیگ مشترک
    cat >> "$CONFIG_FILE" << EOF
    
    # Security Headers
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Remove server signature
    server_tokens off;
    
    # Main subscription endpoint
    location / {
        # Rate limiting
        limit_req zone=subscription burst=$RATE_BURST nodelay;
        
        # Proxy to FastAPI
        proxy_pass http://fastapi_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_set_header X-Forwarded-Port \$server_port;
        
        # Timeouts
        proxy_connect_timeout 10s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        
        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
        
        # Handle errors
        proxy_intercept_errors on;
        error_page 502 503 504 /error.html;
    }
    
    # Health check endpoint (no rate limiting)
    location /health {
        limit_req zone=api burst=10 nodelay;
        proxy_pass http://fastapi_backend/health;
        access_log off;
    }
    
    # API endpoints with higher rate limit
    location /api/ {
        limit_req zone=api burst=15 nodelay;
        proxy_pass http://fastapi_backend;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    # Block access to sensitive files
    location ~ /\.(ht|env|git) {
        deny all;
        access_log off;
        log_not_found off;
        return 404;
    }
    
    # Static error page
    location = /error.html {
        root /var/www/html;
        internal;
    }
    
    # Robots.txt
    location = /robots.txt {
        add_header Content-Type text/plain;
        return 200 "User-agent: *\nDisallow: /\n";
    }
    
    # Logging
    access_log /var/log/nginx/${DOMAIN}_access.log;
    error_log /var/log/nginx/${DOMAIN}_error.log warn;
}
EOF

    print_success "کانفیگ Nginx ایجاد شد: $CONFIG_FILE"
}

# ایجاد صفحه خطا
create_error_page() {
    print_status "ایجاد صفحه خطا..."
    
    mkdir -p /var/www/html
    
    cat > /var/www/html/error.html << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Service Temporarily Unavailable</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
        .error { color: #e74c3c; }
        .info { color: #3498db; margin-top: 20px; }
    </style>
</head>
<body>
    <h1 class="error">🚧 Service Temporarily Unavailable</h1>
    <p>The subscription service is currently undergoing maintenance.</p>
    <p class="info">Please try again in a few minutes.</p>
</body>
</html>
EOF
}

# فعال‌سازی سایت
enable_site() {
    print_header "فعال‌سازی سایت"
    
    # حذف سایت پیش‌فرض
    if [[ -f /etc/nginx/sites-enabled/default ]]; then
        rm -f /etc/nginx/sites-enabled/default
        print_status "سایت پیش‌فرض حذف شد"
    fi
    
    # فعال‌سازی سایت جدید
    ln -sf /etc/nginx/sites-available/vpn-subscriptions /etc/nginx/sites-enabled/
    print_success "سایت فعال شد"
    
    # تست کانفیگ
    print_status "تست کانفیگ Nginx..."
    if nginx -t; then
        print_success "کانفیگ Nginx صحیح است"
    else
        print_error "کانفیگ Nginx دارای خطا است"
        exit 1
    fi
    
    # ریلود Nginx
    print_status "ریلود Nginx..."
    systemctl reload nginx
    print_success "Nginx ریلود شد"
}

# راه‌اندازی Firewall
setup_firewall() {
    print_header "تنظیم Firewall"
    
    if command -v ufw &> /dev/null; then
        print_status "تنظیم UFW..."
        
        # اجازه پورت‌های HTTP/HTTPS
        ufw allow 'Nginx Full'
        ufw allow 22/tcp
        
        # فعال‌سازی firewall
        ufw --force enable
        
        print_success "Firewall تنظیم شد"
        ufw status
    else
        print_warning "UFW نصب نیست، firewall تنظیم نشد"
    fi
}

# تست نهایی
test_setup() {
    print_header "تست راه‌اندازی"
    
    # تست HTTP
    print_status "تست HTTP..."
    if curl -I "http://$DOMAIN" -m 10 &>/dev/null; then
        print_success "HTTP پاسخ می‌دهد"
    else
        print_warning "HTTP پاسخ نمی‌دهد"
    fi
    
    # تست HTTPS
    if [[ $SSL_MODE != "none" ]]; then
        print_status "تست HTTPS..."
        if curl -I "https://$DOMAIN" -k -m 10 &>/dev/null; then
            print_success "HTTPS پاسخ می‌دهد"
        else
            print_warning "HTTPS پاسخ نمی‌دهد"
        fi
    fi
    
    # تست health endpoint
    print_status "تست Health Check..."
    local protocol="http"
    if [[ $SSL_MODE != "none" ]]; then
        protocol="https"
    fi
    
    if curl -s "$protocol://$DOMAIN/health" -m 10 | grep -q "healthy\|status" 2>/dev/null; then
        print_success "Health Check کار می‌کند"
    else
        print_warning "Health Check پاسخ نمی‌دهد (ممکن است FastAPI خاموش باشد)"
    fi
}

# ایجاد اسکریپت مدیریت دامنه
create_domain_manager() {
    print_status "ایجاد اسکریپت مدیریت دامنه..."
    
    cat > /usr/local/bin/nginx-domain-manager << EOF
#!/bin/bash

# اسکریپت مدیریت دامنه Nginx برای ربات VPN

DOMAIN="$DOMAIN"
CONFIG_FILE="/etc/nginx/sites-available/vpn-subscriptions"

show_help() {
    echo "استفاده: nginx-domain-manager [COMMAND]"
    echo ""
    echo "دستورات:"
    echo "  status    - نمایش وضعیت Nginx و دامنه"
    echo "  test      - تست کانفیگ و اتصال"
    echo "  reload    - ریلود کانفیگ Nginx"
    echo "  logs      - نمایش لاگ‌های Nginx"
    echo "  ssl       - بررسی وضعیت SSL"
    echo "  backup    - بک‌آپ کانفیگ"
}

show_status() {
    echo "🌐 وضعیت Nginx و دامنه: \$DOMAIN"
    echo "=================================="
    
    if systemctl is-active --quiet nginx; then
        echo "✅ Nginx: فعال"
    else
        echo "❌ Nginx: غیرفعال"
    fi
    
    if [[ -f "\$CONFIG_FILE" ]]; then
        echo "✅ کانفیگ: موجود"
    else
        echo "❌ کانفیگ: موجود نیست"
    fi
    
    echo ""
    echo "📊 آمار درخواست‌ها (24 ساعت اخیر):"
    if [[ -f "/var/log/nginx/\${DOMAIN}_access.log" ]]; then
        total=\$(grep "\$(date +'%d/%b/%Y')" "/var/log/nginx/\${DOMAIN}_access.log" | wc -l)
        echo "کل درخواست‌ها: \$total"
    else
        echo "لاگ در دسترس نیست"
    fi
}

test_connection() {
    echo "🧪 تست اتصال به \$DOMAIN"
    echo "========================"
    
    # تست HTTP
    if curl -I "http://\$DOMAIN" -m 10 &>/dev/null; then
        echo "✅ HTTP: پاسخ می‌دهد"
    else
        echo "❌ HTTP: پاسخ نمی‌دهد"
    fi
    
    # تست HTTPS
    if curl -I "https://\$DOMAIN" -k -m 10 &>/dev/null; then
        echo "✅ HTTPS: پاسخ می‌دهد"
    else
        echo "❌ HTTPS: پاسخ نمی‌دهد"
    fi
    
    # تست Health
    if curl -s "https://\$DOMAIN/health" -k -m 10 | grep -q "healthy" 2>/dev/null; then
        echo "✅ Health Check: کار می‌کند"
    else
        echo "❌ Health Check: پاسخ نمی‌دهد"
    fi
}

reload_nginx() {
    echo "🔄 ریلود Nginx..."
    nginx -t && systemctl reload nginx
    echo "✅ انجام شد"
}

show_logs() {
    echo "📋 لاگ‌های Nginx (Ctrl+C برای خروج)..."
    tail -f /var/log/nginx/\${DOMAIN}_access.log /var/log/nginx/\${DOMAIN}_error.log
}

check_ssl() {
    echo "🔒 بررسی وضعیت SSL"
    echo "=================="
    
    if openssl s_client -connect "\$DOMAIN:443" -servername "\$DOMAIN" </dev/null 2>/dev/null | openssl x509 -noout -dates 2>/dev/null; then
        echo ""
        echo "📅 اطلاعات گواهی:"
        openssl s_client -connect "\$DOMAIN:443" -servername "\$DOMAIN" </dev/null 2>/dev/null | openssl x509 -noout -subject -issuer 2>/dev/null
    else
        echo "❌ SSL گواهی در دسترس نیست"
    fi
}

backup_config() {
    backup_file="/root/nginx_backup_\$(date +%Y%m%d_%H%M%S).tar.gz"
    tar -czf "\$backup_file" /etc/nginx/sites-available/vpn-subscriptions /etc/ssl/nginx/ 2>/dev/null
    echo "✅ بک‌آپ ایجاد شد: \$backup_file"
}

case "\$1" in
    status) show_status ;;
    test) test_connection ;;
    reload) reload_nginx ;;
    logs) show_logs ;;
    ssl) check_ssl ;;
    backup) backup_config ;;
    *) show_help ;;
esac
EOF

    chmod +x /usr/local/bin/nginx-domain-manager
    print_success "اسکریپت مدیریت در /usr/local/bin/nginx-domain-manager ایجاد شد"
}

# نمایش خلاصه نهایی
show_final_summary() {
    echo ""
    print_success "🎉 راه‌اندازی Nginx و دامنه کامل شد!"
    echo ""
    echo "🌐 دامنه: $DOMAIN"
    echo "🔒 SSL: $SSL_MODE"
    
    if [[ $SSL_MODE != "none" ]]; then
        echo "🔗 URL: https://$DOMAIN"
    else
        echo "🔗 URL: http://$DOMAIN"
    fi
    
    echo ""
    echo "📋 دستورات مفید:"
    echo "• nginx-domain-manager status  - وضعیت سیستم"
    echo "• nginx-domain-manager test    - تست اتصال"
    echo "• nginx-domain-manager logs    - مشاهده لاگ‌ها"
    echo "• nginx-domain-manager ssl     - بررسی SSL"
    echo ""
    echo "📂 فایل‌های مهم:"
    echo "• کانفیگ: /etc/nginx/sites-available/vpn-subscriptions"
    echo "• لاگ‌ها: /var/log/nginx/${DOMAIN}_*.log"
    
    if [[ $SSL_MODE == "existing" || $SSL_MODE == "selfsigned" ]]; then
        echo "• SSL Cert: $SSL_CERT_PATH"
        echo "• SSL Key: $SSL_KEY_PATH"
    elif [[ $SSL_MODE == "letsencrypt" ]]; then
        echo "• SSL: /etc/letsencrypt/live/$DOMAIN/"
    fi
    
    echo ""
    print_warning "برای فعال شدن کامل، اطمینان حاصل کنید:"
    echo "1. DNS record دامنه به این سرور اشاره کند"
    echo "2. سرویس FastAPI در حال اجرا باشد"
    echo "3. Firewall پورت‌های 80 و 443 را اجازه دهد"
}

# اجرای اصلی
main() {
    echo "🌐 راه‌اندازی Nginx و تنظیم دامنه"
    echo "=================================="
    echo ""
    
    check_root
    get_domain_info
    
    echo ""
    print_status "شروع راه‌اندازی..."
    
    install_nginx
    
    case $SSL_MODE in
        existing)
            # فایل‌های SSL از قبل موجود هستند
            ;;
        selfsigned)
            create_selfsigned_ssl
            ;;
        letsencrypt)
            setup_letsencrypt
            ;;
    esac
    
    create_nginx_config
    create_error_page
    enable_site
    setup_firewall
    create_domain_manager
    
    test_setup
    show_final_summary
}

# اجرا
main "$@"