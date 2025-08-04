import asyncio
from services.account_manager import account_manager

async def main():
    account_uuid = input("لطفاً uuid اکانت را وارد کنید: ")
    # اطمینان از اینکه سرورهای فعال شناسایی شده باشند
    from services.server_manager import server_manager
    await server_manager.initialize()

    result = await account_manager.sync_account_usage(account_uuid)
    print("نتیجه همگام‌سازی مصرف:", result)

    # نمایش مجموع مصرف در دیتابیس برای اطمینان
    total_after = await account_manager.get_account_total_usage(account_uuid)
    print("مجموع مصرف ذخیره شده در DB:", total_after)

if __name__ == "__main__":
    asyncio.run(main()) 