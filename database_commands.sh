#!/bin/bash
# 🗄️ دستورات سریع دیتابیس SQLite - VPN Telegram Bot

# رنگ‌ها
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${PURPLE}🗄️  دستورات سریع دیتابیس SQLite${NC}"
echo "=================================="

# تابع نمایش منو
show_menu() {
    echo ""
    echo -e "${CYAN}انتخاب کنید:${NC}"
    echo -e "${GREEN}1)${NC} راه‌اندازی اولیه دیتابیس"
    echo -e "${GREEN}2)${NC} بک‌آپ از دیتابیس"
    echo -e "${GREEN}3)${NC} بازیابی از بک‌آپ"
    echo -e "${GREEN}4)${NC} نمایش آمار دیتابیس"
    echo -e "${GREEN}5)${NC} پاک کردن دیتابیس"
    echo -e "${GREEN}6)${NC} صادرات SQL"
    echo -e "${GREEN}7)${NC} ورود به SQLite shell"
    echo -e "${GREEN}8)${NC} همگام‌سازی تمپلیت‌ها (settings → DB)"
    echo -e "${GREEN}0)${NC} خروج"
    echo ""
    read -p "شماره را وارد کنید: " choice
}

# راه‌اندازی اولیه
setup_database() {
    echo -e "${BLUE}🚀 راه‌اندازی اولیه دیتابیس...${NC}"
    python3 setup_database.py
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ دیتابیس با موفقیت راه‌اندازی شد${NC}"
    else
        echo -e "${RED}❌ خطا در راه‌اندازی دیتابیس${NC}"
    fi
}

# بک‌آپ
backup_database() {
    if [ ! -f "vpn_bot.db" ]; then
        echo -e "${RED}❌ فایل دیتابیس یافت نشد${NC}"
        return 1
    fi
    
    echo -e "${BLUE}💾 ایجاد بک‌آپ...${NC}"
    
    # ایجاد پوشه بک‌آپ
    mkdir -p backups
    
    # نام فایل بک‌آپ
    timestamp=$(date +"%Y%m%d_%H%M%S")
    backup_file="backups/vpn_bot_backup_${timestamp}.db"
    
    # کپی فایل
    cp vpn_bot.db "$backup_file"
    
    echo -e "${GREEN}✅ بک‌آپ ایجاد شد: $backup_file${NC}"
    echo -e "${CYAN}📊 اندازه فایل: $(du -h "$backup_file" | cut -f1)${NC}"
}

# بازیابی از بک‌آپ
restore_database() {
    echo -e "${BLUE}📂 فایل‌های بک‌آپ موجود:${NC}"
    
    if [ ! -d "backups" ] || [ -z "$(ls -A backups 2>/dev/null)" ]; then
        echo -e "${RED}❌ هیچ بک‌آپی یافت نشد${NC}"
        return 1
    fi
    
    # نمایش فایل‌های بک‌آپ
    ls -la backups/ | grep "\.db$" | nl
    
    echo ""
    read -p "شماره فایل بک‌آپ را وارد کنید: " backup_num
    
    backup_file=$(ls backups/*.db | sed -n "${backup_num}p")
    
    if [ -z "$backup_file" ]; then
        echo -e "${RED}❌ فایل بک‌آپ نامعتبر${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}⚠️  آیا از بازیابی $backup_file اطمینان دارید؟ [y/N]${NC}"
    read -p "" confirm
    
    if [[ $confirm =~ ^[Yy]$ ]]; then
        cp "$backup_file" vpn_bot.db
        echo -e "${GREEN}✅ دیتابیس بازیابی شد${NC}"
    else
        echo -e "${CYAN}ℹ️  عملیات لغو شد${NC}"
    fi
}

# نمایش آمار
show_stats() {
    if [ ! -f "vpn_bot.db" ]; then
        echo -e "${RED}❌ فایل دیتابیس یافت نشد${NC}"
        return 1
    fi
    
    echo -e "${BLUE}📊 آمار دیتابیس:${NC}"
    echo "=================="
    
    # اطلاعات فایل
    echo -e "${CYAN}📁 اندازه فایل:${NC} $(du -h vpn_bot.db | cut -f1)"
    echo -e "${CYAN}🕐 تاریخ ایجاد:${NC} $(stat -c %y vpn_bot.db 2>/dev/null || stat -f %SB vpn_bot.db 2>/dev/null)"
    
    echo ""
    echo -e "${CYAN}📊 تعداد رکوردها:${NC}"
    
    # آمار جدول‌ها
    sqlite3 vpn_bot.db <<EOF
.mode column
.headers on
.width 20 10
SELECT 
    'کاربران' as 'جدول',
    COUNT(*) as 'تعداد'
FROM users
UNION ALL
SELECT 'سرورها', COUNT(*) FROM servers
UNION ALL  
SELECT 'اکانت‌ها', COUNT(*) FROM accounts
UNION ALL
SELECT 'سفارشات', COUNT(*) FROM orders
UNION ALL
SELECT 'دعوت‌نامه‌ها', COUNT(*) FROM invitations;
EOF
}

# پاک کردن دیتابیس
clean_database() {
    echo -e "${YELLOW}⚠️  آیا از پاک کردن دیتابیس اطمینان دارید؟ [y/N]${NC}"
    read -p "" confirm
    
    if [[ $confirm =~ ^[Yy]$ ]]; then
        if [ -f "vpn_bot.db" ]; then
            # بک‌آپ اولیه
            backup_database
            rm vpn_bot.db
            echo -e "${GREEN}✅ دیتابیس پاک شد${NC}"
        else
            echo -e "${CYAN}ℹ️  فایل دیتابیس وجود ندارد${NC}"
        fi
    else
        echo -e "${CYAN}ℹ️  عملیات لغو شد${NC}"
    fi
}

# صادرات SQL
export_sql() {
    if [ ! -f "vpn_bot.db" ]; then
        echo -e "${RED}❌ فایل دیتابیس یافت نشد${NC}"
        return 1
    fi
    
    echo -e "${BLUE}📜 صادرات SQL...${NC}"
    
    # ایجاد پوشه dumps
    mkdir -p dumps
    
    # نام فایل
    timestamp=$(date +"%Y%m%d_%H%M%S")
    dump_file="dumps/vpn_bot_dump_${timestamp}.sql"
    
    # صادرات
    sqlite3 vpn_bot.db .dump > "$dump_file"
    
    echo -e "${GREEN}✅ فایل SQL ایجاد شد: $dump_file${NC}"
    echo -e "${CYAN}📊 اندازه فایل: $(du -h "$dump_file" | cut -f1)${NC}"
    echo -e "${CYAN}💡 برای بازیابی: sqlite3 new_db.db < $dump_file${NC}"
}

# ورود به SQLite shell
sqlite_shell() {
    if [ ! -f "vpn_bot.db" ]; then
        echo -e "${RED}❌ فایل دیتابیس یافت نشد${NC}"
        return 1
    fi
    
    echo -e "${BLUE}🔧 ورود به SQLite shell...${NC}"
    echo -e "${CYAN}💡 دستورات مفید:${NC}"
    echo "  .tables    - نمایش جدول‌ها"
    echo "  .schema    - ساختار جدول‌ها"
    echo "  .quit      - خروج"
    echo ""
    
    sqlite3 vpn_bot.db
}

# حلقه اصلی
while true; do
    show_menu
    
    case $choice in
        1)
            setup_database
            ;;
        2)
            backup_database
            ;;
        3)
            restore_database
            ;;
        4)
            show_stats
            ;;
        5)
            clean_database
            ;;
        6)
            export_sql
            ;;
        7)
            sqlite_shell
            ;;
        8)
            echo -e "${BLUE}🔄 همگام‌سازی تمپلیت‌ها...${NC}"
            python3 sync_templates.py
            ;;
        0)
            echo -e "${GREEN}👋 خداحافظ!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ انتخاب نامعتبر${NC}"
            ;;
    esac
    
    echo ""
    read -p "برای ادامه Enter بزنید..."
done 