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
from fastapi.responses import StreamingResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import simpleSplit
import io
from fastapi.responses import StreamingResponse
from fastapi.responses import HTMLResponse


# ── Key management cho order-info ─────────────────────────
VALID_KEYS = {
    "KEYPHONE-74821-593847-12093": 0,
    "KEYPHONE-38472-915630-74219": 0,
    "KEYPHONE-92715-483029-61584": 0,
    "KEYPHONE-56029-771843-20936": 0,
    "KEYPHONE-71384-602915-88420": 0,
    "KEYPHONE-24890-394761-53018": 0,
    "KEYPHONE-67531-820947-16359": 0,
    "KEYPHONE-10928-573640-82941": 0,
    "KEYPHONE-84276-315098-47025": 0,
    "KEYPHONE-39610-748235-92164": 0,
    "KEYPHONE-51873-269104-65782": 0,
    "KEYPHONE-73105-984260-31279": 0,
    "KEYPHONE-26489-507318-94621": 0,
    "KEYPHONE-89017-431265-70834": 0,
    "KEYPHONE-47260-915384-62318": 0,
    "KEYPHONE-63918-280745-15492": 0,
    "KEYPHONE-20574-639182-87031": 0,
    "KEYPHONE-91834-752609-44126": 0,
    "KEYPHONE-37481-596203-78540": 0,
    "KEYPHONE-68209-413875-26914": 0,
    "KEYPHONE-15738-904261-83275": 0,
    "KEYPHONE-42068-735914-50923": 0,
    "KEYPHONE-76325-108479-64290": 0,
    "KEYPHONE-98104-652738-31589": 0,
    "KEYPHONE-54673-219804-77831": 0,
    "KEYPHONE-83017-467295-19064": 0,
    "KEYPHONE-29460-873512-65918": 0,
    "KEYPHONE-71529-364087-92810": 0,
    "KEYPHONE-40816-529743-17638": 0,
    "KEYPHONE-96253-187640-83592": 0,
    "KEYPHONE-13784-690215-47286": 0,
    "HOANG-UNLIMITED": 0,
    "HIEU-UNLIMITED": 0,
}
KEY_LIMIT = 20
# Lưu lịch sử tra cứu: {key: [{"order_code": ..., "time": ...}]}
KEY_HISTORY: dict = {k: [] for k in VALID_KEYS}
# Lưu lịch sử đăng nhập: {key: [{"event": "login/logout", "time": ...}]}
LOGIN_HISTORY: list = []  # [{key, event, time}]
# Database setup
Base.metadata.create_all(bind=engine)
migrate()
UNLIMITED_KEYS = {"HOANG-UNLIMITED", "HIEU-UNLIMITED"} 
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
@app.get("/phone", response_class=HTMLResponse)
async def phone_page():
    with open("static/phone.html", encoding="utf-8") as f:
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
    limit: int = Query(200, le=200),
    sort: str = Query("default"),
    db: Session = Depends(get_db)
):
    user_id = request.headers.get('X-User-ID', '')

    if shop_id and shop_id in BLOCKED_SHOPS and user_id != 'Chang2000':
        return {
            "total": 0, "page": page, "data": [],
            "blocked": True,
            "message": "Shop này bị chặn trích xuất đơn hàng"
        }

    q = db.query(Order)
    if shop_id:
        q = q.filter(Order.shop_id == shop_id)
    total = q.count()

    # Sắp xếp
    if sort == "total_desc":
        q = q.order_by(desc(Order.total))
    elif sort == "total_asc":
        q = q.order_by(Order.total)
    elif sort == "date_desc":
        q = q.order_by(desc(Order.order_date))
    elif sort == "date_asc":
        q = q.order_by(Order.order_date)
    else:
        q = q.order_by(desc(Order.fetched_at))

    orders = q.offset((page - 1) * limit).limit(limit).all()

    def serialize(o):
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
        "data": [serialize(o) for o in orders]
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
async def get_order_info(body: dict, db: Session = Depends(get_db)):
    order_code = body.get("order_code", "").strip()
    key        = body.get("key", "").strip()

    if not order_code or not key:
        return JSONResponse({"error": "Thiếu mã đơn hàng hoặc key."}, status_code=400)

    if key not in VALID_KEYS:
        return JSONResponse({"error": "Key không hợp lệ."}, status_code=403)

    if key not in UNLIMITED_KEYS and VALID_KEYS[key] >= KEY_LIMIT:
        return JSONResponse({"error": f"Key đã hết lượt sử dụng ({KEY_LIMIT}/{KEY_LIMIT})."}, status_code=403)

    if len(order_code) < 9:
        return JSONResponse({"error": "Mã đơn hàng không hợp lệ."}, status_code=400)

    VALID_KEYS[key] += 1
    remaining = -1 if key in UNLIMITED_KEYS else KEY_LIMIT - VALID_KEYS[key]

    from datetime import timezone as _tz
    now_vn = datetime.now(_tz(timedelta(hours=7))).strftime("%d/%m/%Y %H:%M")
    if key not in KEY_HISTORY:
        KEY_HISTORY[key] = []
    KEY_HISTORY[key].append({"order_code": order_code, "time": now_vn})

    input_id = order_code[2:9]

    url = f"https://ec.megaads.vn/service/inoutput/find-promotion-codes-api?inoutputId={input_id}"
    session = "eyJpdiI6ImIra2pmWitCVVRRTlp2K3pRUUZOZ1E9PSIsInZhbHVlIjoibXpYaFhkQmVZU1VMRFRKWWhEcXRCdnBFSWdycVNzNFlSVHpGWjVYT0hTVDFpdlErVWxDSWhEaVdcL3JyT2RvSjZIcDNkMVJSYTllZDJMMTlsR2ZIQ3BnPT0iLCJtYWMiOiI2MDc2MTFlNDg0MTg4M2IyNDBiNDAzMDE4ZWE0MTk0ZTFkNDdlNGU3MjQ0ZjA3ODFkYTlkYzZiMjcyOTEyMzNmIn0%3D"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(url, headers={
                "Accept": "application/json, text/plain, */*",
                "platform": "ios",
                "Cookie": f"laravel_session={session}",
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

        phone = next((x for x in d.get("search", "").split() if x.isdigit() and len(x) >= 9), "—")

        payment_type   = d.get("payment_type", "")
        prepaid_amount = d.get("prepaid_amount")
        is_approved    = d.get("is_approved_prepaid", "0")
        prepaid_time   = d.get("prepaid_time")

        if payment_type in ("home", "cod"):
            payment_status = "💵 COD — Thu tiền khi nhận hàng"
        elif payment_type in ("atm", "online", "bank") and is_approved == "1":
            payment_status = f"✅ Đã thanh toán online ({payment_type.upper()})"
            if prepaid_time:
                payment_status += f" lúc {prepaid_time}"
        elif payment_type in ("atm", "online", "bank") and is_approved != "1":
            payment_status = f"⏳ Chờ xác nhận thanh toán ({payment_type.upper()})"
        else:
            payment_status = f"— ({payment_type or 'Không rõ'})"
        db_order = db.query(Order).filter(
            Order.order_code.like(f"%_{order_code}")
        ).first()
        db_product = db_order.product if db_order else "—"
        db_total   = f"{int(db_order.total):,} đ".replace(",", ".") if db_order and db_order.total else "—"
        return {
    "order_code":           g("code"),
    "shop_name":            g("store_code", "creator_name"),
    "order_date":           g("verified_time", "create_time"),
    "customer_name":        g("related_user_name", "receiver_name"),
    "phone":                phone,
    "email":                g("email_id"),
    "address":              g("delivery_address"),
    "source":               g("source", "from"),
    "payment":              payment_status,
    "prepaid_amount":       db_total,            # ← lấy từ DB thay vì API
    "shipping_code":        g("shipping_code"),
    "delivery_status":      g("delivery_status"),
    "shipper_receive_time": g("shipper_receive_time"),
    "product":              db_product,          # ← thêm mới
    "remaining":            remaining,
}
    except Exception as e:
        VALID_KEYS[key] -= 1
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
@app.get("/api/customer-info")
async def get_customer_info(customer_id: str = Query(...)):
    url = f"https://chat-crm.megaads.vn/users/{customer_id}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(url)
        data = res.json()
        if not data.get("_id"):
            return JSONResponse({"error": "Không tìm thấy khách hàng."}, status_code=404)
        return {
            "username":   data.get("username"),
            "phone":      data.get("phone"),
            "api_token":  data.get("apiToken"),
            "created_at": data.get("createdAt"),
        }
    except Exception as e:
        return JSONResponse({"error": f"Lỗi: {str(e)}"}, status_code=500)
@app.get("/api/revenue/shop")
async def get_revenue_single(shop_id: str = Query(...)):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    date_range = f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}"
    encoded_range = urllib.parse.quote(date_range)

    shops = get_shops_map()
    if shop_id not in shops:
        return JSONResponse({"error": "Không tìm thấy gian hàng."}, status_code=404)

    shop_url, shop_name = shops[shop_id]
    api_url = (
        f"https://api.chiaki.vn/api/{shop_id}"
        f"/export-excel-summary-amount-order"
        f"?source=seller&page_index=1&page_size=500"
        f"&status=all&range_date={encoded_range}"
        f"&date_type=created_at&order=create-desc"
        f"&Seller_id={SELLER_ID}&Seller_token={SELLER_TOKEN}"
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(api_url)
        if resp.status_code != 200:
            return JSONResponse({"error": f"API lỗi HTTP {resp.status_code}"}, status_code=500)
        content_type = resp.headers.get("content-type", "")
        if "html" in content_type or len(resp.content) < 100:
            return JSONResponse({"error": "Không nhận được file Excel từ Chiaki."}, status_code=500)

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
            if val is None: return 0
            try: return float(val)
            except: return 0

        ten_shop        = get_val("Người Bán") or shop_name
        chu_tk          = get_val("Tên chủ tài khoản") or "—"
        ngan_hang       = get_val("Tên ngân hàng") or "—"
        stk             = get_val("Tài khoản ngân hàng") or "—"
        gia_goc         = to_float(get_val("Giá gốc"))
        hoan_lai        = to_float(get_val("Số tiền hoàn lại"))
        tro_gia         = to_float(get_val("Sản phẩm được trợ giá từ Chiaki"))
        ma_uu_dai       = to_float(get_val("Mã ưu đãi do Người Bán chịu"))
        doanh_thu_gop   = gia_goc + hoan_lai + tro_gia + ma_uu_dai
        phi_co_dinh     = to_float(get_val("Phí cố định"))
        phi_dich_vu     = to_float(get_val("Phí Dịch Vụ"))
        phi_thanh_toan  = to_float(get_val("Phí thanh toán"))
        phi_san         = phi_co_dinh + phi_dich_vu + phi_thanh_toan
        phi_quang_cao   = to_float(get_val("Phí quảng cáo"))
        thue_gtgt       = to_float(get_val("Thuế GTGT"))
        thue_tncn       = to_float(get_val("Thuế TNCN"))
        tong_khau_tru   = phi_san + phi_quang_cao + thue_gtgt + thue_tncn
        doanh_thu_thuan = doanh_thu_gop + tong_khau_tru

        return {
            "date_range":       date_range,
            "ten_shop":         ten_shop,
            "chu_tk":           chu_tk,
            "ngan_hang":        ngan_hang,
            "stk":              str(stk) if stk else "—",
            "gia_goc":          gia_goc,
            "hoan_lai":         hoan_lai,
            "tro_gia":          tro_gia,
            "ma_uu_dai":        ma_uu_dai,
            "doanh_thu_gop":    doanh_thu_gop,
            "phi_san":          phi_san,
            "phi_quang_cao":    phi_quang_cao,
            "thue_gtgt":        thue_gtgt,
            "thue_tncn":        thue_tncn,
            "tong_khau_tru":    tong_khau_tru,
            "doanh_thu_thuan":  doanh_thu_thuan,
        }
    except Exception as e:
        return JSONResponse({"error": f"Lỗi xử lý: {str(e)}"}, status_code=500)
@app.get("/api/chat-info")
async def get_chat_info(seller_id: str = Query(...)):
    url = f"https://chat-crm.megaads.vn/conversations/{seller_id}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(url)
        data = res.json()
        
        conversations = data if isinstance(data, list) else data.get("data", [data])
        result = []
        
        for c in conversations:
            customer = c.get("customerId") or {}
            seller = c.get("sellerId") or {}
            last_msg = c.get("lastMessage") or {}
            
            # Parse nội dung tin nhắn đơn hàng
            msg_content = last_msg.get("content", "")
            msg_type = last_msg.get("messageType", "text")
            order_info = None
            if msg_type == "order":
                try:
                    import json as _json
                    order_info = _json.loads(msg_content)
                except: pass

            def fmt_time(t):
                if not t: return "—"
                try:
                    from datetime import timezone
                    dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
                    dt_vn = dt.astimezone(timezone(timedelta(hours=7)))
                    return dt_vn.strftime("%d/%m/%Y %H:%M")
                except: return t

            result.append({
                "id":                   c.get("_id"),
                "customer_id":          customer.get("_id"),
                "customer_name":        customer.get("username"),
                "customer_online":      customer.get("isOnline", False),
                "seller_name":          seller.get("username"),
                "seller_online":        seller.get("isOnline", False),
                "msg_type":             msg_type,
                "msg_text":             msg_content if msg_type == "text" else None,
                "order_info":           order_info,
                "seller_unread":        c.get("sellerUnreadMessage", 0),
                "customer_unread":      c.get("customerUnreadMessage", 0),
                "created_at":           fmt_time(c.get("createdAt")),
                "updated_at":           fmt_time(c.get("updatedAt")),
                "last_seen":            fmt_time(c.get("lastSeenMessage")),
                "has_violation":        c.get("hasViolation", False),
            })
        
        return {"conversations": result, "total": len(result)}
    except Exception as e:
        return JSONResponse({"error": f"Lỗi: {str(e)}"}, status_code=500)
@app.get("/api/revenue/net")
async def get_revenue_net(shop_id: str = Query(...)):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=14)
    date_range = f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}"
    encoded_range = urllib.parse.quote(date_range)

    shops = get_shops_map()
    if shop_id not in shops:
        return JSONResponse({"error": "Không tìm thấy gian hàng."}, status_code=404)

    shop_url, shop_name = shops[shop_id]
    api_url = (
        f"https://api.chiaki.vn/api/{shop_id}/export-excel-order"
        f"?source=seller&page_index=1&page_size=500&status=finished"
        f"&range_date={encoded_range}&date_type=created_at&order=create-desc"
        f"&Seller_id={SELLER_ID}&Seller_token={SELLER_TOKEN}"
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(api_url)
        if resp.status_code != 200:
            return JSONResponse({"error": f"API lỗi HTTP {resp.status_code}"}, status_code=500)
        content_type = resp.headers.get("content-type", "")
        if "html" in content_type or len(resp.content) < 100:
            return JSONResponse({"error": "Không nhận được file Excel."}, status_code=500)

        wb = openpyxl.load_workbook(BytesIO(resp.content))
        ws = wb.active

        # Tìm index cột theo header
        headers = {}
        header_row = None
        for i, row in enumerate(ws.iter_rows(values_only=True), 1):
            if row and any(cell and "tổng tiền" in str(cell).lower() for cell in row):
                header_row = i
                for j, cell in enumerate(row):
                    if cell:
                        headers[str(cell).strip().lower()] = j
                break

        if header_row is None:
            return JSONResponse({"error": "Không tìm thấy header trong file Excel."}, status_code=500)

        # Tìm cột cần thiết
        def find_col(keyword):
            for k, v in headers.items():
                if keyword.lower() in k:
                    return v
            return None

        col_tong_tien   = find_col("tổng tiền")
        col_phu_phi     = find_col("phụ phí")
        col_doi_soat    = find_col("ngày đối soát")

        if col_tong_tien is None:
            return JSONResponse({"error": "Không tìm thấy cột 'Tổng tiền'."}, status_code=500)

        tong_tien_sum = 0
        phu_phi_sum   = 0
        row_count     = 0

        for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
            if not row or all(c is None for c in row):
                continue
            # Chỉ tính dòng có cột Ngày đối soát trống
            doi_soat_val = row[col_doi_soat] if col_doi_soat is not None else None
            if doi_soat_val is not None and str(doi_soat_val).strip() != "":
                continue

            try:
                tong_tien_sum += float(row[col_tong_tien] or 0)
            except: pass
            try:
                phu_phi_sum += float(row[col_phu_phi] or 0) if col_phu_phi is not None else 0
            except: pass
            row_count += 1

        doanh_thu_thuan = tong_tien_sum - phu_phi_sum

        return {
            "shop_name":       shop_name,
            "date_range":      date_range,
            "row_count":       row_count,
            "tong_tien":       tong_tien_sum,
            "phu_phi":         phu_phi_sum,
            "doanh_thu_thuan": doanh_thu_thuan,
        }
    except Exception as e:
        return JSONResponse({"error": f"Lỗi xử lý: {str(e)}"}, status_code=500)
@app.post("/api/order-info/check-key")
async def check_key(body: dict):
    key = body.get("key", "").strip()
    if key not in VALID_KEYS:
        return JSONResponse({"error": "Key không hợp lệ."}, status_code=403)
    used = VALID_KEYS[key]
    is_unlimited = key in UNLIMITED_KEYS
    return {
        "used": used,
        "remaining": -1 if is_unlimited else KEY_LIMIT - used,
        "limit": -1 if is_unlimited else KEY_LIMIT,
        "unlimited": is_unlimited
}
@app.get("/api/order-info/history")
async def get_key_history(request: Request):
    user_id = request.headers.get('X-User-ID', '')
    if user_id != 'Chang2000':
        return JSONResponse({"error": "Không có quyền."}, status_code=403)

    result = []
    for key, logs in KEY_HISTORY.items():
        if logs:
            result.append({
                "key":     key,
                "used":    VALID_KEYS.get(key, 0),
                "limit":   KEY_LIMIT,
                "history": logs
            })
    return {"data": result, "total_queries": sum(len(v) for v in KEY_HISTORY.values())}
@app.post("/api/auth/login-log")
async def login_log(body: dict, request: Request):
    key    = body.get("key", "").strip()
    event  = body.get("event", "login")  # "login" hoặc "logout"
    
    from datetime import timezone as _tz
    now_vn = datetime.now(_tz(timedelta(hours=7))).strftime("%H:%M:%S ngày %d/%m/%Y")
    
    LOGIN_HISTORY.append({
        "key":   key,
        "event": event,
        "time":  now_vn,
    })
    return {"ok": True}

@app.get("/api/auth/login-history")
async def get_login_history(request: Request):
    user_id = request.headers.get('X-User-ID', '')
    if user_id != 'Chang2000':
        return JSONResponse({"error": "Không có quyền."}, status_code=403)
    return {"data": LOGIN_HISTORY, "total": len(LOGIN_HISTORY)}
@app.get("/api/export-order/{order_code}")
async def export_order(order_code: str, request: Request, db: Session = Depends(get_db)):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    import io

    # Tìm đơn trong DB — dùng SQLAlchemy như các endpoint khác
    order = db.query(Order).filter(Order.order_code == order_code).first()

    if not order:
        return JSONResponse({"error": "Không tìm thấy đơn hàng"}, status_code=404)

    wb = Workbook()
    ws = wb.active
    ws.title = "Đơn hàng"

    headers = [
        ("Mã đơn",        order.order_code or ""),
        ("Ngày tạo",      order.order_date or ""),
        ("Gian hàng",     order.shop_name or ""),
        ("Tên khách",     order.customer_name or order.buyer_name or ""),
        ("Số điện thoại", order.phone or ""),
        ("Địa chỉ",       order.address or ""),
        ("Sản phẩm",      order.product or ""),
        ("Số lượng",      order.quantity or ""),
        ("Tổng tiền",     order.total or ""),
        ("Trạng thái",    order.status or ""),
    ]

    for i, (label, value) in enumerate(headers, start=1):
        c_label = ws.cell(row=i, column=1, value=label)
        c_label.font = Font(bold=True, color="5B4B8A", size=11)
        c_label.fill = PatternFill("solid", fgColor="EDE8FF")
        c_label.alignment = Alignment(horizontal="left", vertical="center")

        c_val = ws.cell(row=i, column=2, value=str(value) if value else "")
        c_val.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 48

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"don-hang-{order_code}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
    )
@app.post("/api/print-label")
async def print_label(body: dict):
    shop_name     = body.get("shop_name", "")
    shipping_code = body.get("shipping_code", "")
    order_code    = body.get("order_code", "")
    customer_name = body.get("customer_name", "")
    address       = body.get("address", "")
    product       = body.get("product", "")
    order_date    = body.get("order_date", "")
    total         = body.get("prepaid_amount", "")

    W, H = 4 * inch, 6 * inch
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))

    # Màu đen
    c.setFillColorRGB(0, 0, 0)

    # ── HEADER: Logo text + mã đơn ──────────────────────────
    c.setFont("Helvetica-BoldOblique", 16)
    c.drawString(0.18*inch, H - 0.32*inch, "Chiaki.vn")

    c.setFont("Helvetica-Bold", 7)
    c.drawRightString(W - 0.18*inch, H - 0.22*inch, f"Ma van don: {shipping_code}")
    c.setFont("Helvetica", 7)
    c.drawRightString(W - 0.18*inch, H - 0.32*inch, f"Ma don hang: {order_code}")

    # Đường kẻ ngang dưới header
    y_line = H - 0.4*inch
    c.setLineWidth(1.5)
    c.line(0.18*inch, y_line, W - 0.18*inch, y_line)

    # ── BARCODE placeholder ──────────────────────────────────
    c.setLineWidth(0.5)
    c.setDash(3, 2)
    c.rect(0.18*inch, H - 0.72*inch, W - 0.36*inch, 0.25*inch)
    c.setDash()

    # ── TỪ ──────────────────────────────────────────────────
    y_from = H - 1.05*inch
    c.setLineWidth(0.8)
    c.rect(0.18*inch, y_from - 0.32*inch, 1.2*inch, 0.42*inch)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(0.24*inch, y_from + 0.04*inch, "Tu:")
    c.setFont("Helvetica-Bold", 8.5)
    # wrap shop name
    lines = simpleSplit(shop_name, "Helvetica-Bold", 8.5, 1.1*inch)
    for i, ln in enumerate(lines[:2]):
        c.drawString(0.24*inch, y_from - 0.08*inch - i*0.13*inch, ln)

    # ── ĐẾN ─────────────────────────────────────────────────
    c.setLineWidth(1.5)
    c.rect(1.5*inch, y_from - 0.32*inch, W - 1.68*inch, 0.42*inch)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(1.56*inch, y_from + 0.04*inch, "Den:")
    c.setFont("Helvetica-Bold", 9)
    c.drawString(1.56*inch, y_from - 0.08*inch, customer_name[:30])
    c.setFont("Helvetica", 7.5)
    addr_lines = simpleSplit(address, "Helvetica", 7.5, 2.2*inch)
    for i, ln in enumerate(addr_lines[:3]):
        c.drawString(1.56*inch, y_from - 0.2*inch - i*0.12*inch, ln)

    # ── NỘI DUNG HÀNG + QR ──────────────────────────────────
    y_content = H - 2.0*inch
    box_h = 1.1*inch
    c.setLineWidth(0.8)
    c.rect(0.18*inch, y_content - box_h, 2.9*inch, box_h)

    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(0.24*inch, y_content - 0.14*inch, "Noi dung hang (Tong SL san pham: 1)")

    c.setFont("Helvetica", 8)
    prod_lines = simpleSplit(f"1. {product}, SL: 1", "Helvetica", 8, 2.78*inch)
    for i, ln in enumerate(prod_lines[:4]):
        c.drawString(0.24*inch, y_content - 0.28*inch - i*0.13*inch, ln)

    c.setFont("Helvetica", 6.5)
    note = "Kiem tra ten san pham va doi chieu Ma van don / Ma don hang truoc khi nhan hang."
    note_lines = simpleSplit(note, "Helvetica", 6.5, 2.78*inch)
    for i, ln in enumerate(note_lines[:2]):
        c.drawString(0.24*inch, y_content - 0.86*inch - i*0.11*inch, ln)

    # QR placeholder
    c.setLineWidth(0.5)
    c.rect(3.16*inch, y_content - box_h, 0.66*inch, 0.66*inch)
    c.setFont("Helvetica", 6)
    c.drawCentredString(3.49*inch, y_content - box_h - 0.1*inch, "QR Code")

    # ── NGÀY ĐẶT HÀNG ───────────────────────────────────────
    y_date = y_content - box_h - 0.2*inch
    c.setLineWidth(0.5)
    c.line(0.18*inch, y_date, W - 0.18*inch, y_date)
    c.setFont("Helvetica", 7.5)
    c.drawRightString(W - 0.18*inch, y_date - 0.14*inch, "Ngay dat hang:")
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(W - 0.18*inch, y_date - 0.26*inch, order_date)

    # ── TIỀN THU ────────────────────────────────────────────
    y_money = y_date - 0.42*inch
    c.setLineWidth(1.5)
    c.line(0.18*inch, y_money, W - 0.18*inch, y_money)
    c.setFont("Helvetica", 8)
    c.drawString(0.18*inch, y_money - 0.2*inch, "Tien thu nguoi nhan:")
    c.setFont("Helvetica-Bold", 20)
    c.drawRightString(W - 0.18*inch, y_money - 0.28*inch, total)

    # ── CHỮ KÝ + CHỈ DẪN ────────────────────────────────────
    y_sign = y_money - 0.6*inch
    c.setLineWidth(0.8)
    c.rect(0.18*inch, y_sign - 0.55*inch, W - 0.36*inch, 0.65*inch)

    c.setFont("Helvetica", 6.5)
    guide = "Chi dan giao hang: Duoc dong kiem; Khong boc tem, seal, thu san pham; Chuyen hoan sau 3 lan phat; Luu kho toi da 5 ngay."
    guide_lines = simpleSplit(guide, "Helvetica", 6.5, 2.2*inch)
    for i, ln in enumerate(guide_lines[:3]):
        c.drawString(0.24*inch, y_sign - 0.1*inch - i*0.11*inch, ln)

    c.setFont("Helvetica-Bold", 7.5)
    c.drawCentredString(3.5*inch, y_sign - 0.08*inch, "Chu ky nguoi nhan")
    c.setFont("Helvetica", 6.5)
    c.drawCentredString(3.5*inch, y_sign - 0.2*inch, "Xac nhan hang nguyen ven,")
    c.drawCentredString(3.5*inch, y_sign - 0.3*inch, "khong mop/meo, be/vo")
    c.line(3.0*inch, y_sign - 0.5*inch, W - 0.18*inch, y_sign - 0.5*inch)

    c.save()
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{order_code}.pdf"'}
    )
@app.get("/api/orders/delivering")
async def get_delivering_orders(shop_id: str = Query(None)):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    date_range = f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}"
    encoded_range = urllib.parse.quote(date_range)

    shops = get_shops_map()
    shop_items = list({shop_id: shops[shop_id]}.items()) if shop_id and shop_id in shops else list(shops.items())

    async def fetch_one(client, sid, shop_name):
        api_url = (
            f"https://api.chiaki.vn/api/{sid}/export-excel-order"
            f"?source=seller&page_index=1&page_size=200"
            f"&status=delivering"
            f"&range_date={encoded_range}"
            f"&date_type=created_at&order=create-desc"
            f"&Seller_id={SELLER_ID}&Seller_token={SELLER_TOKEN}"
        )
        try:
            resp = await client.get(api_url)
            if resp.status_code != 200:
                return []
            if "html" in resp.headers.get("content-type", "") or len(resp.content) < 100:
                return []

            wb = openpyxl.load_workbook(BytesIO(resp.content))
            ws = wb.active

            headers_map = {}
            header_row = None
            for i, row in enumerate(ws.iter_rows(values_only=True), 1):
                if row and any(cell and "mã đơn" in str(cell).lower() for cell in row):
                    header_row = i
                    for j, cell in enumerate(row):
                        if cell:
                            headers_map[str(cell).strip().lower()] = j
                    break

            if header_row is None:
                return []

            def fc(kw):
                for k, v in headers_map.items():
                    if kw.lower() in k:
                        return v
                return None

            col_code    = fc("mã đơn")
            col_date    = fc("ngày tạo") or fc("ngày đặt")
            col_name    = fc("tên người nhận") or fc("tên khách")
            col_phone   = fc("số điện thoại") or fc("điện thoại")
            col_address = fc("địa chỉ")
            col_product = fc("tên sản phẩm") or fc("sản phẩm")
            col_total   = fc("tổng tiền") or fc("giá trị")

            orders = []
            for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
                if not row or all(c is None for c in row):
                    continue
                def gv(col):
                    return str(row[col]).strip() if col is not None and row[col] is not None else "—"
                orders.append({
                    "shop_id":       sid,
                    "shop_name":     shop_name,
                    "order_code":    gv(col_code),
                    "order_date":    gv(col_date),
                    "customer_name": gv(col_name),
                    "phone":         gv(col_phone),
                    "address":       gv(col_address),
                    "product":       gv(col_product),
                    "total":         gv(col_total),
                })
            return orders

        except Exception as e:
            print(f"[delivering] {sid} lỗi: {e}")
            return []

    # Gọi song song tất cả shop, giới hạn 10 request cùng lúc tránh bị block
    semaphore = asyncio.Semaphore(10)

    async def fetch_with_sem(client, sid, shop_name):
        async with semaphore:
            return await fetch_one(client, sid, shop_name)

    async with httpx.AsyncClient(timeout=30) as client:
        tasks = [fetch_with_sem(client, sid, val[1]) for sid, val in shop_items]
        results = await asyncio.gather(*tasks)

    all_orders = [order for shop_orders in results for order in shop_orders]

    return {"date_range": date_range, "total": len(all_orders), "data": all_orders}
@app.post("/api/auth/verify-id")
async def verify_id(body: dict):
    VALID_IDS = {
        "PNPhuong2000": {"hours": 1,           "label": "Phương"},
        "ChangAUTHKEY2000":    {"hours": 9999999999,   "label": "Hoàng"},
    }
    user_id = body.get("id", "").strip()
    info = VALID_IDS.get(user_id)
    if not info:
        return JSONResponse({"error": "ID không hợp lệ."}, status_code=403)
    
    import time
    first_entry = body.get("firstEntry")  # ms từ frontend
    if not first_entry:
        first_entry = int(time.time() * 1000)
    
    exp_ms = first_entry + info["hours"] * 3600000
    if int(time.time() * 1000) > exp_ms:
        return JSONResponse({"error": "ID đã hết hạn."}, status_code=403)
    
    return {"ok": True, "label": info["label"], "expMs": exp_ms, "firstEntry": first_entry}
