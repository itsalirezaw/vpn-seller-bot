import asyncio
from services.xui_api import XUIManager
from config.settings import settings

async def main():
    uuid = input("لطفاً uuid اکانت را وارد کنید: ")
    xui_manager = XUIManager(settings.servers)
    # ابتدا سرورهای فعال را شناسایی کن
    await xui_manager.get_active_servers()
    result = await xui_manager.get_client_traffic_from_all_servers(uuid)
    print("خروجی خام ترافیک از سرورها:")
    print(result)

if __name__ == "__main__":
    asyncio.run(main()) 