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
    total = q.count()
    orders = q.order_by(desc(Order.fetched_at)).offset((page - 1) * limit).limit(limit).all()
    return {
        "total": total,
        "page":  page,
        "data": [
            {
                "order_code": o.order_code,
                "shop_name":  o.shop_name,
                "shop_id":    o.shop_id,
                "buyer_name": o.buyer_name,
                "customer_name": o.customer_name,
                "phone":      o.phone,
                "address":    o.address,
                "product":    o.product,
                "quantity":   o.quantity,
                "total":      o.total,
                "status":     o.status,
                "order_date": o.order_date,
                "fetched_at": o.fetched_at.isoformat() if o.fetched_at else None,
            }
            for o in orders
        ]
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
    filters = [
        func.lower(Order.address).contains(kw.lower())   # ✅ address, không phải shipping_address
        for kw in keywords
    ]
    orders = db.query(Order).filter(or_(*filters))\
               .order_by(Order.order_date.desc()).all()   # ✅ order_date, không phải created_at
    return [
        {
            "order_code":    o.order_code,
            "order_date":    o.order_date,
            "shop_id":       o.shop_id,
            "shop_name":     o.shop_name,
            "customer_name": o.customer_name,
            "buyer_name":    o.buyer_name,
            "phone":         o.phone,
            "address":       o.address,
            "product":       o.product,
            "quantity":      o.quantity,
            "total":         o.total,
            "status":        o.status,
        }
        for o in orders
    ]
@app.get("/api/orders/nuochoa")
async def get_nuochoa_orders(db: Session = Depends(get_db)):
    keywords = ["nước hoa", "nuoc hoa", "nươc hoa", "nước  hoa"]
    filters = [
        func.lower(Order.product).contains(kw.lower())
        for kw in keywords
    ]
    orders = db.query(Order).filter(or_(*filters))\
               .order_by(Order.order_date.desc()).all()
    return [
        {
            "order_code":    o.order_code,
            "order_date":    o.order_date,
            "shop_id":       o.shop_id,
            "shop_name":     o.shop_name,
            "customer_name": o.customer_name,
            "buyer_name":    o.buyer_name,
            "phone":         o.phone,
            "address":       o.address,
            "product":       o.product,
            "quantity":      o.quantity,
            "total":         o.total,
            "status":        o.status,
        }
        for o in orders
    ]

