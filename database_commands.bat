@echo off
chcp 65001 > nul
:: 🗄️ دستورات سریع دیتابیس SQLite - VPN Telegram Bot (Windows)

title VPN Bot Database Manager

:main_menu
cls
echo ================================
echo 🗄️  دستورات سریع دیتابیس SQLite
echo ================================
echo.
echo انتخاب کنید:
echo 1) راه‌اندازی اولیه دیتابیس
echo 2) بک‌آپ از دیتابیس
echo 3) بازیابی از بک‌آپ
echo 4) نمایش آمار دیتابیس
echo 5) پاک کردن دیتابیس
echo 6) صادرات SQL
echo 7) ورود به SQLite shell
echo 0) خروج
echo.
set /p choice="شماره را وارد کنید: "

if "%choice%"=="1" goto setup_database
if "%choice%"=="2" goto backup_database
if "%choice%"=="3" goto restore_database
if "%choice%"=="4" goto show_stats
if "%choice%"=="5" goto clean_database
if "%choice%"=="6" goto export_sql
if "%choice%"=="7" goto sqlite_shell
if "%choice%"=="0" goto exit
goto invalid_choice

:setup_database
echo.
echo 🚀 راه‌اندازی اولیه دیتابیس...
python setup_database.py
if %errorlevel% equ 0 (
    echo ✅ دیتابیس با موفقیت راه‌اندازی شد
) else (
    echo ❌ خطا در راه‌اندازی دیتابیس
)
goto pause_and_continue

:backup_database
echo.
if not exist "vpn_bot.db" (
    echo ❌ فایل دیتابیس یافت نشد
    goto pause_and_continue
)

echo 💾 ایجاد بک‌آپ...

:: ایجاد پوشه بک‌آپ
if not exist "backups" mkdir backups

:: نام فایل بک‌آپ
for /f "tokens=1-4 delims=/ " %%i in ('date /t') do set mydate=%%k%%j%%i
for /f "tokens=1-2 delims=: " %%i in ('time /t') do set mytime=%%i%%j
set mytime=%mytime: =0%
set timestamp=%mydate%_%mytime%
set backup_file=backups\vpn_bot_backup_%timestamp%.db

:: کپی فایل
copy vpn_bot.db "%backup_file%" > nul

echo ✅ بک‌آپ ایجاد شد: %backup_file%
for %%A in ("%backup_file%") do echo 📊 اندازه فایل: %%~zA bytes
goto pause_and_continue

:restore_database
echo.
echo 📂 فایل‌های بک‌آپ موجود:
if not exist "backups" (
    echo ❌ هیچ بک‌آپی یافت نشد
    goto pause_and_continue
)

dir /b backups\*.db 2>nul | findstr . >nul
if %errorlevel% neq 0 (
    echo ❌ هیچ بک‌آپی یافت نشد
    goto pause_and_continue
)

:: نمایش فایل‌ها
setlocal enabledelayedexpansion
set count=0
for %%f in (backups\*.db) do (
    set /a count+=1
    echo !count!) %%f
)

echo.
set /p backup_num="شماره فایل بک‌آپ را وارد کنید: "

:: پیدا کردن فایل انتخاب شده
set count=0
for %%f in (backups\*.db) do (
    set /a count+=1
    if !count! equ %backup_num% set selected_file=%%f
)

if not defined selected_file (
    echo ❌ فایل بک‌آپ نامعتبر
    goto pause_and_continue
)

echo.
set /p confirm="⚠️  آیا از بازیابی %selected_file% اطمینان دارید؟ [y/N]: "
if /i "%confirm%"=="y" (
    copy "%selected_file%" vpn_bot.db > nul
    echo ✅ دیتابیس بازیابی شد
) else (
    echo ℹ️  عملیات لغو شد
)
goto pause_and_continue

:show_stats
echo.
if not exist "vpn_bot.db" (
    echo ❌ فایل دیتابیس یافت نشد
    goto pause_and_continue
)

echo 📊 آمار دیتابیس:
echo ==================

:: اطلاعات فایل
for %%A in ("vpn_bot.db") do (
    echo 📁 اندازه فایل: %%~zA bytes
    echo 🕐 تاریخ تغییر: %%~tA
)

echo.
echo 📊 تعداد رکوردها:

:: آمار جدول‌ها (اگر sqlite3 نصب باشد)
where sqlite3 >nul 2>nul
if %errorlevel% equ 0 (
    echo جدول^|تعداد
    echo ---------------
    sqlite3 vpn_bot.db "SELECT 'کاربران', COUNT(*) FROM users UNION ALL SELECT 'سرورها', COUNT(*) FROM servers UNION ALL SELECT 'اکانت‌ها', COUNT(*) FROM accounts UNION ALL SELECT 'سفارشات', COUNT(*) FROM orders UNION ALL SELECT 'دعوت‌نامه‌ها', COUNT(*) FROM invitations;"
) else (
    echo ℹ️  برای نمایش آمار کامل، sqlite3 را نصب کنید
    echo      https://sqlite.org/download.html
)
goto pause_and_continue

:clean_database
echo.
set /p confirm="⚠️  آیا از پاک کردن دیتابیس اطمینان دارید؟ [y/N]: "
if /i "%confirm%"=="y" (
    if exist "vpn_bot.db" (
        :: بک‌آپ اولیه
        call :backup_database_silent
        del vpn_bot.db
        echo ✅ دیتابیس پاک شد
    ) else (
        echo ℹ️  فایل دیتابیس وجود ندارد
    )
) else (
    echo ℹ️  عملیات لغو شد
)
goto pause_and_continue

:export_sql
echo.
if not exist "vpn_bot.db" (
    echo ❌ فایل دیتابیس یافت نشد
    goto pause_and_continue
)

echo 📜 صادرات SQL...

:: بررسی وجود sqlite3
where sqlite3 >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ sqlite3 یافت نشد. لطفاً از https://sqlite.org/download.html نصب کنید
    goto pause_and_continue
)

:: ایجاد پوشه dumps
if not exist "dumps" mkdir dumps

:: نام فایل
for /f "tokens=1-4 delims=/ " %%i in ('date /t') do set mydate=%%k%%j%%i
for /f "tokens=1-2 delims=: " %%i in ('time /t') do set mytime=%%i%%j
set mytime=%mytime: =0%
set timestamp=%mydate%_%mytime%
set dump_file=dumps\vpn_bot_dump_%timestamp%.sql

:: صادرات
sqlite3 vpn_bot.db .dump > "%dump_file%"

echo ✅ فایل SQL ایجاد شد: %dump_file%
for %%A in ("%dump_file%") do echo 📊 اندازه فایل: %%~zA bytes
echo 💡 برای بازیابی: sqlite3 new_db.db ^< %dump_file%
goto pause_and_continue

:sqlite_shell
echo.
if not exist "vpn_bot.db" (
    echo ❌ فایل دیتابیس یافت نشد
    goto pause_and_continue
)

:: بررسی وجود sqlite3
where sqlite3 >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ sqlite3 یافت نشد. لطفاً از https://sqlite.org/download.html نصب کنید
    goto pause_and_continue
)

echo 🔧 ورود به SQLite shell...
echo 💡 دستورات مفید:
echo   .tables    - نمایش جدول‌ها
echo   .schema    - ساختار جدول‌ها
echo   .quit      - خروج
echo.
pause
sqlite3 vpn_bot.db
goto main_menu

:backup_database_silent
:: بک‌آپ بدون نمایش پیام (برای استفاده داخلی)
if not exist "vpn_bot.db" exit /b 1
if not exist "backups" mkdir backups
for /f "tokens=1-4 delims=/ " %%i in ('date /t') do set mydate=%%k%%j%%i
for /f "tokens=1-2 delims=: " %%i in ('time /t') do set mytime=%%i%%j
set mytime=%mytime: =0%
set timestamp=%mydate%_%mytime%
set backup_file=backups\vpn_bot_backup_%timestamp%.db
copy vpn_bot.db "%backup_file%" > nul
exit /b 0

:invalid_choice
echo ❌ انتخاب نامعتبر
goto pause_and_continue

:pause_and_continue
echo.
pause
goto main_menu

:exit
echo 👋 خداحافظ!
pause
exit /b 0 