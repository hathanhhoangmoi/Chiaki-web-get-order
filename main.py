import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from database import engine, get_db
from models import Base, Order, ShopMeta
from scheduler import start_scheduler, sync_all_shops
from shops_config import get_shops_map
from fetcher import sync_shop
from sqlalchemy import func, or_
from shops_config import get_shops_map, RESTRICTED_SHOPS, RESTRICTED_PASS
from datetime import datetime, timedelta
from io import BytesIO
import urllib.parse
from shops_config import get_shops_map, RESTRICTED_SHOPS, RESTRICTED_PASS, SELLER_ID, SELLER_TOKEN

from database import engine, get_db, migrate
Base.metadata.create_all(bind=engine)
migrate()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Sync ngay khi khởi động
    asyncio.create_task(sync_all_shops())
    start_scheduler()
    yield

app = FastAPI(title="Chiaki Order Dashboard", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ── API Endpoints ──────────────────────────────────────────
def serialize_order(o, mask=False):
    M = "••••••••"
    return {
        "order_code":    M if mask else o.order_code,
        "order_date":    M if mask else o.order_date,
        "shop_id":       o.shop_id,
        "shop_name":     o.shop_name,   # ✅ luôn hiện tên shop
        "buyer_name":    M if mask else o.buyer_name,
        "customer_name": M if mask else o.customer_name,
        "phone":         M if mask else o.phone,
        "address":       M if mask else o.address,
        "product":       M if mask else o.product,
        "quantity":      M if mask else o.quantity,
        "total":         None if mask else o.total,
        "status":        M if mask else o.status,
        "fetched_at":    o.fetched_at.isoformat() if o.fetched_at else None,
        "restricted":    mask,
    }


@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html", encoding="utf-8") as f:
        return f.read()

@app.get("/api/summary")
def get_summary(db: Session = Depends(get_db)):
    shops = db.query(ShopMeta).all()
    total = db.query(Order).count()
    return {
        "total_orders": total,
        "total_shops":  len(shops),
        "shops": [
            {
                "shop_id":    s.shop_id,
                "shop_name":  s.shop_name,
                "order_count": s.order_count,
                "last_sync":  s.last_sync.isoformat() if s.last_sync else None,
            }
            for s in shops
        ]
    }

@app.get("/api/orders")
def get_orders(
    shop_id: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db)
):
    q = db.query(Order)
    if shop_id:
        q = q.filter(Order.shop_id == shop_id)
    total  = q.count()
    orders = q.order_by(desc(Order.fetched_at)).offset((page-1)*limit).limit(limit).all()
    return {
        "total": total,
        "page":  page,
        "data":  [serialize_order(o, mask=o.shop_id in RESTRICTED_SHOPS) for o in orders]
    }



@app.post("/api/sync")
async def manual_sync(db: Session = Depends(get_db)):
    """Kích hoạt sync thủ công"""
    asyncio.create_task(sync_all_shops())
    return {"message": "Đang sync... Vui lòng chờ 1-2 phút rồi reload."}

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    by_status = db.query(Order.status, func.count(Order.id)).group_by(Order.status).all()
    by_shop   = db.query(Order.shop_name, func.count(Order.id)).group_by(Order.shop_name).all()
    return {
        "by_status": [{"status": s, "count": c} for s, c in by_status],
        "by_shop":   [{"shop": s, "count": c} for s, c in by_shop],
    }
@app.get("/api/test-shopname")
async def test_shopname(url: str = Query(...)):
    from fetcher import fetch_shop_name
    name = await fetch_shop_name(url)
    return {"url": url, "name": name}
@app.post("/api/update-shopname")
def update_shopname(body: dict, db: Session = Depends(get_db)):
    shop_id   = body.get("shop_id")
    shop_name = body.get("shop_name")
    if not shop_id or not shop_name:
        return {"ok": False}
    meta = db.query(ShopMeta).filter(ShopMeta.shop_id == shop_id).first()
    if meta:
        meta.shop_name = shop_name
        db.query(Order).filter(Order.shop_id == shop_id).update({"shop_name": shop_name})
        db.commit()
    return {"ok": True, "shop_id": shop_id, "shop_name": shop_name}
@app.post("/api/admin/clear-orders")
def clear_orders(body: dict, db: Session = Depends(get_db)):
    if body.get("admin_secret") != ADMIN_SECRET:
        return {"ok": False}
    count = db.query(Order).delete()
    db.commit()
    return {"ok": True, "deleted": count}
@app.get("/api/orders/hanoi")
async def get_hanoi_orders(db: Session = Depends(get_db)):
    keywords = ["hà nội", "ha noi", " hn", "hanoi", "Hà Nội"]
    filters  = [func.lower(Order.address).contains(kw.lower()) for kw in keywords]
    orders   = db.query(Order).filter(or_(*filters))\
                 .order_by(Order.order_date.desc()).all()
    return [serialize_order(o, mask=o.shop_id in RESTRICTED_SHOPS) for o in orders]

@app.get("/api/orders/nuochoa")
async def get_nuochoa_orders(db: Session = Depends(get_db)):
    keywords = ["nước hoa", "nuoc hoa", "nươc hoa", "nước  hoa"]
    filters  = [func.lower(Order.product).contains(kw.lower()) for kw in keywords]
    orders   = db.query(Order).filter(or_(*filters))\
                 .order_by(Order.order_date.desc()).all()
    return [serialize_order(o, mask=o.shop_id in RESTRICTED_SHOPS) for o in orders]


@app.get("/api/chart-data")
def get_chart_data(db: Session = Depends(get_db)):
    # ✅ Dùng substr để lấy đúng 10 ký tự đầu (YYYY-MM-DD)
    date_col = func.substr(Order.order_date, 1, 10)
    by_date = (
        db.query(date_col, func.count(Order.id))
        .filter(Order.order_date != None, Order.order_date != '')
        .group_by(date_col)
        .order_by(date_col)
        .all()
    )
    by_shop = (
        db.query(Order.shop_name, func.count(Order.id))
        .filter(Order.shop_name != None, Order.shop_name != '')
        .group_by(Order.shop_name)
        .order_by(func.count(Order.id).desc())
        .all()
    )
    return {
        "by_date": [{"date": d, "count": c} for d, c in by_date if d],
        "by_shop": [{"shop": s, "count": c} for s, c in by_shop if s],
    }
@app.get("/api/orders/private")
def get_private_orders(
    shop_id: str = Query(...),
    password: str = Query(...),
    page: int = Query(1, ge=1),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db)
):
    if password != RESTRICTED_PASS or shop_id not in RESTRICTED_SHOPS:
        return JSONResponse(status_code=403, content={"error": "Sai mật khẩu hoặc không có quyền"})
    q = db.query(Order).filter(Order.shop_id == shop_id)
    total = q.count()
    orders = q.order_by(desc(Order.fetched_at)).offset((page - 1) * limit).limit(limit).all()
    return {
        "total": total,
        "page":  page,
        "data": [{
            "order_code":    o.order_code,
            "shop_name":     o.shop_name,
            "shop_id":       o.shop_id,
            "buyer_name":    o.buyer_name,
            "customer_name": o.customer_name,
            "phone":         o.phone,
            "address":       o.address,
            "product":       o.product,
            "quantity":      o.quantity,
            "total":         o.total,
            "status":        o.status,
            "order_date":    o.order_date,
            "fetched_at":    o.fetched_at.isoformat() if o.fetched_at else None,
        } for o in orders]
    }
@app.get("/api/revenue")
async def get_revenue():
    # ✅ Tự động tính 30 ngày gần nhất
    end_date   = datetime.now()
    start_date = end_date - timedelta(days=30)
    date_range = f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}"
    encoded_range = urllib.parse.quote(date_range)

    shops   = get_shops_map()
    results = []

    async with httpx.AsyncClient(timeout=30) as client:
        for shop_id, (shop_url, shop_name) in shops.items():
            api_url = (
                f"https://api.chiaki.vn/api/{shop_id}"
                f"/export-excel-summary-amount-order"
                f"?source=seller&page_index=1&page_size=500"
                f"&status=all&range_date={encoded_range}"
                f"&date_type=created_at&order=create-desc"
                f"&Seller_id={SELLER_ID}&Seller_token={SELLER_TOKEN}"
            )
            try:
                resp = await client.get(api_url)
                if resp.status_code != 200:
                    print(f"[revenue] {shop_id} HTTP {resp.status_code}")
                    continue

                wb = openpyxl.load_workbook(BytesIO(resp.content))
                ws = wb.active

                # Đọc header từ dòng 1
                headers = [str(cell.value).strip() if cell.value else f"col_{i}"
                           for i, cell in enumerate(ws[1])]

                for row in ws.iter_rows(min_row=2, values_only=True):
                    if not any(v is not None for v in row):
                        continue
                    row_dict = dict(zip(headers, row))
                    row_dict["_shop_name"] = shop_name
                    row_dict["_shop_id"]   = shop_id
                    row_dict["_restricted"] = shop_id in RESTRICTED_SHOPS
                    results.append(row_dict)

            except Exception as e:
                print(f"[revenue] {shop_id} lỗi: {e}")

    return {
        "date_range": date_range,
        "data":       results,
    }
