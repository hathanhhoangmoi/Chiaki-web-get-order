import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import SessionLocal
from fetcher import sync_shop
from shops_config import get_shops_map

scheduler = AsyncIOScheduler(timezone="Asia/Ho_Chi_Minh")

async def sync_all_shops():
    print("[scheduler] Bắt đầu quét toàn bộ gian hàng...")
    shops = get_shops_map()

    async def sync_one(sid, url, name):
        db = SessionLocal()
        try:
            return await sync_shop(sid, url, name, db)
        finally:
            db.close()

    tasks = [sync_one(sid, url, name) for sid, (url, name) in shops.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total_new = sum(r for r in results if isinstance(r, int))
    print(f"[scheduler] Hoàn tất: +{total_new} đơn mới từ {len(shops)} gian hàng")


def start_scheduler():
    scheduler.add_job(sync_all_shops, "interval", minutes=30, id="sync_all")
    scheduler.start()
