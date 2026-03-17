import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_
from database import engine, get_db, migrate
from models import Base, Order, ShopMeta
from scheduler import start_scheduler, sync_all_shops
from shops_config import get_shops_map, BLOCKED_SHOPS, SELLER_ID, SELLER_TOKEN
from fetcher import sync_shop
from datetime import datetime, timedelta
from io import BytesIO
import urllib.parse
import httpx
import openpyxl
from fastapi import Request


# Database setup
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

# ── Helper functions ───────────────────────────────────────
def serialize_order(o, mask=False):
    """Serialize order với mask nếu cần"""
    M = "••••••••"
    return {
        "order_code":    M if mask else o.order_code,
        "order_date":    M if mask else o.order_date,
        "shop_id":       o.shop_id,
        "shop_name":     o.shop_name,  # ✅ luôn hiện tên shop
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
        "total_shops": len(shops),
        "shops": [
            {
                "shop_id": s.shop_id,
                "shop_name": s.shop_name,
                "order_count": s.order_count,
                "last_sync": s.last_sync.isoformat() if s.last_sync else None,
            }
            for s in shops
        ]
    }

@app.get("/api/orders")
def get_orders(
    request: Request,
    shop_id: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db)
):
    user_id = request.headers.get('X-User-ID', '')
    
    # ✅ Block nếu không phải Chang2000
    if shop_id and shop_id in BLOCKED_SHOPS and user_id != 'Chang2000':
        return {
            "total": 0,
            "page": page,
            "data": [],
            "blocked": True,
            "message": "Shop này bị chặn trích xuất đơn hàng"
        }
    
    q = db.query(Order)
    if shop_id:
        q = q.filter(Order.shop_id == shop_id)
    total = q.count()
    orders = q.order_by(desc(Order.fetched_at)).offset((page-1)*limit).limit(limit).all()

    def serialize_order(o):
        # ✅ Chỉ mask nếu shop bị chặn VÀ user không phải Chang2000
        mask = o.shop_id in BLOCKED_SHOPS and user_id != 'Chang2000'
        M = "••••••••"
        return {
            "order_code":    M if mask else o.order_code,
            "shop_name":     o.shop_name,
            "shop_id":       o.shop_id,
            "buyer_name":    M if mask else o.buyer_name,
            "customer_name": M if mask else o.customer_name,
            "phone":         M if mask else o.phone,
            "address":       M if mask else o.address,
            "product":       M if mask else o.product,
            "quantity":      M if mask else o.quantity,
            "total":         M if mask else o.total,
            "status":        M if mask else o.status,
            "order_date":    M if mask else o.order_date,
            "fetched_at":    o.fetched_at.isoformat() if o.fetched_at else None,
            "restricted":    mask,
        }

    return {
        "total": total,
        "page": page,
        "data": [serialize_order(o) for o in orders]
    }


@app.post("/api/sync")
async def manual_sync():
    """Kích hoạt sync thủ công"""
    asyncio.create_task(sync_all_shops())
    return {"message": "Đang sync... Vui lòng chờ 1-2 phút rồi reload."}

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    by_status = db.query(Order.status, func.count(Order.id)).group_by(Order.status).all()
    by_shop = db.query(Order.shop_name, func.count(Order.id)).group_by(Order.shop_name).all()
    return {
        "by_status": [{"status": s, "count": c} for s, c in by_status],
        "by_shop": [{"shop": s, "count": c} for s, c in by_shop],
    }

@app.get("/api/test-shopname")
async def test_shopname(url: str = Query(...)):
    from fetcher import fetch_shop_name
    name = await fetch_shop_name(url)
    return {"url": url, "name": name}

@app.post("/api/update-shopname")
def update_shopname(body: dict, db: Session = Depends(get_db)):
    shop_id = body.get("shop_id")
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
    # ✅ Tạm thời disable để tránh xóa nhầm
    return {"ok": False, "message": "Admin endpoint disabled"}

@app.get("/api/orders/hanoi")
async def get_hanoi_orders(request: Request, db: Session = Depends(get_db)):
    user_id = request.headers.get('X-User-ID', '')
    keywords = ["hà nội", "ha noi", " hn", "hanoi", "Hà Nội"]
    filters = [func.lower(Order.address).contains(kw.lower()) for kw in keywords]
    orders = db.query(Order).filter(or_(*filters))\
              .order_by(Order.order_date.desc()).all()
    
    def serialize_with_user(o):
        mask = o.shop_id in BLOCKED_SHOPS and user_id != 'Chang2000'
        return serialize_order(o, mask=mask)
    
    return [serialize_with_user(o) for o in orders]


@app.get("/api/orders/nuochoa")
async def get_nuochoa_orders(db: Session = Depends(get_db)):
    keywords = ["nước hoa", "nuoc hoa", "nươc hoa", "nước  hoa"]
    filters = [func.lower(Order.product).contains(kw.lower()) for kw in keywords]
    orders = db.query(Order).filter(or_(*filters))\
              .order_by(Order.order_date.desc()).all()
    def serialize_with_user(o):
        mask = o.shop_id in BLOCKED_SHOPS and user_id != 'Chang2000'
        return serialize_order(o, mask=mask)
    
    return [serialize_order(o, mask=o.shop_id in BLOCKED_SHOPS) for o in orders]

@app.get("/api/chart-data")
def get_chart_data(db: Session = Depends(get_db)):
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

@app.get("/api/revenue")
async def get_revenue():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    date_range = f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}"
    encoded_range = urllib.parse.quote(date_range)

    shops = get_shops_map()
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

                content_type = resp.headers.get("content-type", "")
                if "html" in content_type or len(resp.content) < 100:
                    print(f"[revenue] {shop_id} không phải Excel")
                    continue

                wb = openpyxl.load_workbook(BytesIO(resp.content))
                ws = wb.active

                def get_val(key_text):
                    for row in ws.iter_rows():
                        for i, cell in enumerate(row):
                            if cell.value and key_text.lower() in str(cell.value).lower():
                                if i + 1 < len(row) and row[i + 1].value is not None:
                                    return row[i + 1].value
                    return None

                def to_float(val):
                    if val is None:
                        return 0
                    try:
                        return float(val)
                    except:
                        return 0

                ten_shop = get_val("Người Bán") or shop_name
                chu_tk = get_val("Tên chủ tài khoản") or "—"
                ngan_hang = get_val("Tên ngân hàng") or "—"
                stk = get_val("Tài khoản ngân hàng") or "—"

                # Doanh thu gộp
                gia_goc = to_float(get_val("Giá gốc"))
                hoan_lai = to_float(get_val("Số tiền hoàn lại"))
                tro_gia = to_float(get_val("Sản phẩm được trợ giá từ Chiaki"))
                ma_uu_dai = to_float(get_val("Mã ưu đãi do Người Bán chịu"))
                doanh_thu_gop = gia_goc + hoan_lai + tro_gia + ma_uu_dai

                # Phí + thuế
                phi_co_dinh = to_float(get_val("Phí cố định"))
                phi_dich_vu = to_float(get_val("Phí Dịch Vụ"))
                phi_thanh_toan = to_float(get_val("Phí thanh toán"))
                phi_san = phi_co_dinh + phi_dich_vu + phi_thanh_toan
                phi_quang_cao = to_float(get_val("Phí quảng cáo"))
                thue_gtgt = to_float(get_val("Thuế GTGT"))
                thue_tncn = to_float(get_val("Thuế TNCN"))
                tong_thue = thue_gtgt + thue_tncn
                tong_khau_tru = phi_san + phi_quang_cao + tong_thue

                # Doanh thu thuần = gộp + khấu trừ (khấu trừ là số âm)
                doanh_thu_thuan = doanh_thu_gop + tong_khau_tru

                results.append({
                    "ten_shop": ten_shop,
                    "chu_tk": chu_tk,
                    "ngan_hang": ngan_hang,
                    "stk": str(stk) if stk else "—",
                    "doanh_thu_gop": doanh_thu_gop,
                    "tong_khau_tru": tong_khau_tru,
                    "doanh_thu_thuan": doanh_thu_thuan,
                    "_shop_id": shop_id,
                })

            except Exception as e:
                print(f"[revenue] {shop_id} lỗi: {e}")

    return {
        "date_range": date_range,
        "data": results,
    }
@app.post("/api/order-info")
async def get_order_info(body: dict):
    order_code = body.get("order_code", "").strip()
    session_cookie = body.get("session_cookie", "").strip()

    if not order_code or not session_cookie:
        return JSONResponse({"error": "Thiếu mã đơn hàng hoặc session cookie"}, status_code=400)

    if len(order_code) < 9:
        return JSONResponse({"error": "Mã đơn hàng không hợp lệ"}, status_code=400)

    input_id = order_code[2:9]
    url = f"https://ec.megaads.vn/service/inoutput/find-promotion-codes-api?inoutputId={input_id}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(url, headers={
                "Accept": "application/json, text/plain, */*",
                "platform": "ios",
                "Cookie": f"laravel_session={session_cookie}",
                "User-Agent": "chiakiApp/3.6.2"
            })
        data = res.json()

        d = data.get("result") or data.get("data") or {}
        if isinstance(d, list):
            d = d[0] if d else {}

        def g(*keys):
            for k in keys:
                v = d.get(k)
                if v: return str(v)
            return "—"

        # ✅ Gán vào biến trước, rồi dùng trong return
        phone = next((x for x in d.get("search", "").split() if x.isdigit() and len(x) >= 9), "—")

        return {
            "order_code":    g("code"),
            "shop_name":     g("store_code", "creator_name"),
            "order_date":    g("verified_time", "create_time"),
            "customer_name": g("related_user_name", "receiver_name"),
            "phone":         phone,
            "email":         g("email_id"),
            "address":       g("delivery_address"),
            "source":        g("source", "from"),
            "_raw":          data
        }

    except Exception as e:
        return JSONResponse({"error": f"Lỗi khi gọi API: {str(e)}"}, status_code=500)
@app.get("/api/shop-info")
async def get_shop_info(request: Request, shop_id: str = Query(...)):
    user_id = request.headers.get('X-User-ID', '')
    BLOCKED = {"4647", "4732", "5112"}
    if shop_id in BLOCKED and user_id != 'Chang2000':
        return JSONResponse({"error": "Bạn không có quyền xem thông tin gian hàng này."}, status_code=403)

    url = f"https://api.chiaki.vn/seller/{shop_id}/profile?&Seller_id={SELLER_ID}&Seller_token={SELLER_TOKEN}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(url)
        data = res.json()
        if data.get("status") != "successful":
            return JSONResponse({"error": "Không tìm thấy gian hàng."}, status_code=404)

        s = data.get("seller", {})
        meta = {}
        try:
            import json as _json
            meta = _json.loads(s.get("meta_data", "{}"))
        except: pass

        bank = {}
        try:
            import json as _json
            bank = _json.loads(s.get("bank_info", "{}"))
        except: pass

        warehouses = meta.get("warehouses", [])

        return {
            "id":           s.get("id"),
            "code":         s.get("code"),
            "name":         s.get("name"),
            "email":        s.get("email"),
            "phone":        s.get("phone"),
            "address":      s.get("address"),
            "name_organization": s.get("name_organization"),
            "create_time":  s.get("create_time"),
            "bank_account_number": bank.get("bank_account_number"),
            "bank_account_holder": bank.get("bank_account_holder"),
            "bank_name":    bank.get("bank_name"),
            "cccd_front":   s.get("citizen_identification_front_files", [{}])[0].get("value") if s.get("citizen_identification_front_files") else None,
            "cccd_back":    s.get("citizen_identification_back_files", [{}])[0].get("value") if s.get("citizen_identification_back_files") else None,
            "warehouses":   warehouses,
        }
    except Exception as e:
        return JSONResponse({"error": f"Lỗi: {str(e)}"}, status_code=500)
