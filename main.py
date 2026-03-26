import asyncio
from fastapi import FastAPI, Depends, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_
from database import engine, get_db, migrate
from models import Base, Order, ShopMeta
from shops_config import get_shops_map, BLOCKED_SHOPS, SELLER_ID, SELLER_TOKEN
from fetcher import sync_shop, parse_excel
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
from shops_config import SHOP_NAME_MAP
import json as _json
from fastapi import UploadFile, File, Form

# ── Key management cho order-info ─────────────────────────
VALID_KEYS = {
    "ADMIN-UNLIMITED-HOANG": 0,
    "PHONE-KEY-1472-3891": 0,
    "PHONE-KEY-5830-2147": 0,
    "PHONE-KEY-9214-6753": 0,
    "PHONE-KEY-3768-4512": 0,
    "PHONE-KEY-6091-8324": 0,
    "PHONE-KEY-2845-7163": 0,
    "PHONE-KEY-7539-1086": 0,
    "PHONE-KEY-4127-9450": 0,
    "PHONE-KEY-8963-2718": 0,
    "PHONE-KEY-1604-5937": 0,
    "PHONE-KEY-5281-3074": 0,
    "PHONE-KEY-9746-6812": 0,
    "PHONE-KEY-3019-8265": 0,
    "PHONE-KEY-6453-1790": 0,
    "PHONE-KEY-2897-4631": 0,
    "PHONE-KEY-7162-9048": 0,
    "PHONE-KEY-4385-2576": 0,
    "PHONE-KEY-8720-5193": 0,
    "PHONE-KEY-1938-7402": 0,
    "PHONE-KEY-5674-3819": 0,
    "PHONE-KEY-9051-6247": 0,
    "PHONE-KEY-3492-8760": 0,
    "PHONE-KEY-6815-1034": 0,
    "PHONE-KEY-2370-9581": 0,
    "PHONE-KEY-7643-4208": 0,
    "PHONE-KEY-4056-7925": 0,
    "PHONE-KEY-8219-3467": 0,
    "PHONE-KEY-1587-6140": 0,
    "PHONE-KEY-5904-2783": 0,
    "PHONE-KEY-9368-5016": 0,
    "PHONE-KEY-PHUONG2000": 0,
}
KEY_LIMIT = 10
# Lưu lịch sử tra cứu: {key: [{"order_code": ..., "time": ...}]}
KEY_HISTORY: dict = {k: [] for k in VALID_KEYS}
# Lưu lịch sử đăng nhập: {key: [{"event": "login/logout", "time": ...}]}
LOGIN_HISTORY: list = []  # [{key, event, time}]
# Database setup
Base.metadata.create_all(bind=engine)
migrate()
UNLIMITED_KEYS = {"ADMIN-UNLIMITED-HOANG", "PHONE-KEY-PHUONG2000"}
# ── Key management cho Cancel Order ───────────────────────
CANCEL_KEYS = {
    "ADMIN-UNLIMITED-HOANG": 0,
    "CANCEL-KEY-3821-7045": 0,
    "CANCEL-KEY-6174-2938": 0,
    "CANCEL-KEY-9502-5163": 0,
    "CANCEL-KEY-1847-8320": 0,
    "CANCEL-KEY-4293-6751": 0,
    "CANCEL-KEY-7618-3094": 0,
    "CANCEL-KEY-2056-9482": 0,
    "CANCEL-KEY-5739-1867": 0,
    "CANCEL-KEY-8401-4215": 0,
    "CANCEL-KEY-3164-7590": 0,
    "CANCEL-KEY-6827-2043": 0,
    "CANCEL-KEY-9350-5718": 0,
    "CANCEL-KEY-1493-8261": 0,
    "CANCEL-KEY-4706-3947": 0,
    "CANCEL-KEY-7082-6534": 0,
    "CANCEL-KEY-2915-9170": 0,
    "CANCEL-KEY-5348-1826": 0,
    "CANCEL-KEY-8671-4302": 0,
    "CANCEL-KEY-3209-7654": 0,
    "CANCEL-KEY-6543-2187": 0,
    "CANCEL-KEY-9876-5430": 0,
    "CANCEL-KEY-1230-8976": 0,
    "CANCEL-KEY-4567-3219": 0,
    "CANCEL-KEY-7894-6542": 0,
    "CANCEL-KEY-2341-9875": 0,
    "CANCEL-KEY-5678-1234": 0,
    "CANCEL-KEY-8912-4567": 0,
    "CANCEL-KEY-3456-7891": 0,
    "CANCEL-KEY-6789-2345": 0,
    "CANCEL-KEY-9123-5678": 0,

}
CANCEL_KEY_LIMIT = 10
CANCEL_UNLIMITED_KEYS = {"ADMIN-UNLIMITED-HOANG"} 
CANCEL_KEY_HISTORY: dict = {k: [] for k in CANCEL_KEYS}
# ── GETORDER KEY ──
GETORDER_KEYS = {
    "GETORDER-KEY-1234-5678": 0,
    "GETORDER-KEY-8765-4321": 0,
    "GETORDER-KEY-1798-1820": 0,
    "GETORDER-KEY-5307-5294": 0,
    "GETORDER-KEY-6682-4366": 0,
    "GETORDER-KEY-2422-1762": 0,
    "GETORDER-KEY-9373-9617": 0,
    "GETORDER-KEY-4393-7851": 0,
    "GETORDER-KEY-2553-6631": 0,
    "GETORDER-KEY-4570-1679": 0,
    "GETORDER-KEY-7842-7049": 0,
    "GETORDER-KEY-8631-3272": 0,
    "GETORDER-KEY-3181-7097": 0,
    "GETORDER-KEY-5801-6373": 0,
    "GETORDER-KEY-3097-7233": 0,
    "GETORDER-KEY-6608-3640": 0,
    "GETORDER-KEY-7555-9096": 0,
    "GETORDER-KEY-2161-1064": 0,
    "GETORDER-KEY-6003-8995": 0,
    "GETORDER-KEY-9679-7130": 0,
    "GETORDER-KEY-4630-3698": 0,
    "GETORDER-KEY-9001-8597": 0,
    "ADMIN-UNLIMITED-HOANG":  0,
}
GETORDER_KEY_LIMIT      = 20
GETORDER_UNLIMITED_KEYS = {"ADMIN-UNLIMITED-HOANG"}
GETORDER_KEY_HISTORY    = {k: [] for k in GETORDER_KEYS}

app = FastAPI(title="Chiaki Order Dashboard")
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
        print(f"[debug] store_code in d = {d.get('store_code')}")
        print(f"[debug] SHOP_NAME_MAP.get = '{SHOP_NAME_MAP.get('STD14EBRRV')}'")
        print(f"[debug] SHOP_NAME_MAP keys = {list(SHOP_NAME_MAP.keys())[:5]}")
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
        db_product   = db_order.product   if db_order else "—"
        shop_id_from_api = g("store_code", "creator_name")
        db_shop_name = (
            SHOP_NAME_MAP.get(shop_id_from_api)
            or (db_order.shop_name if db_order else None)
            or shop_id_from_api
        )
        db_total     = f"{int(db_order.total):,} đ".replace(",", ".") if db_order and db_order.total else "—"
        url_history_parsed = []
        try:
            meta_raw = d.get("meta_data", "{}")
            meta = _json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
            uh = meta.get("url_history", {})
            if isinstance(uh, dict):
                url_history_parsed = [v for _, v in sorted(uh.items(), key=lambda x: int(x[0]))]
            elif isinstance(uh, list):
                url_history_parsed = uh
        except Exception:
                url_history_parsed = []
        meta = {}
        try:
            meta = json.loads(g("meta_data") or "{}")
        except:
            pass

        source_from = meta.get("meta_tracking", {}).get("from", "") or g("from") or ""
        return {
    "order_code":           g("code"),
    "status":               g("status"),
    "shop_name":            db_shop_name,
    "order_date":           g("verified_time", "create_time"),
    "customer_name":        g("related_user_name", "receiver_name"),
    "phone":                phone,
    "email":                g("email_id"),
    "address":              g("delivery_address"),
    "source":               g("source", "from"),
    "source_from":          source_from,
    "payment":              payment_status,
    "prepaid_amount":       db_total,            # ← lấy từ DB thay vì API
    "shipping_code":        g("shipping_code"),
    "delivery_status":      g("delivery_status"),
    "shipper_receive_time": g("shipper_receive_time"),
    "product":              db_product,          # ← thêm mới
    "quantity":             d.get("quantity") or (db_order.quantity if db_order else None),
    "url_history":          url_history_parsed,
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
            "cccd_front":       (s.get("citizen_identification_front_files") or [{}])[0].get("value"),
            "cccd_back":        (s.get("citizen_identification_back_files")  or [{}])[0].get("value"),
            "business_license": (s.get("business_license_files")            or [{}])[0].get("value"),
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
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import inch
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.utils import simpleSplit
    from reportlab.graphics.barcode import code128
    import io, os

    shop_name    = body.get("shop_name", "")
    shipping_code= body.get("shipping_code", "")
    order_code   = body.get("order_code", "")
    customer_name= body.get("customer_name", "")
    address      = body.get("address", "")
    product      = body.get("product", "")
    order_date   = body.get("order_date", "")
    total        = body.get("prepaid_amount", "")

    # ── Font tiếng Việt ──
    FONT_DIR = os.path.join(os.path.dirname(__file__), "static", "fonts")
    try:
        pdfmetrics.registerFont(TTFont("Roboto",      f"{FONT_DIR}/Roboto-Regular.ttf"))
        pdfmetrics.registerFont(TTFont("Roboto-Bold", f"{FONT_DIR}/Roboto-Bold.ttf"))
        F_REG  = "Roboto"
        F_BOLD = "Roboto-Bold"
    except:
        F_REG  = "Helvetica"
        F_BOLD = "Helvetica-Bold"

    W, H = 4 * inch, 6 * inch
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setFillColorRGB(0, 0, 0)

    # ════════════════════════════════
    # HEADER — Logo + Mã đơn
    # ════════════════════════════════
    c.setFont(F_BOLD, 18)
    c.drawString(0.18*inch, H - 0.35*inch, "Chiaki.vn")

    c.setFont(F_BOLD, 7.5)
    c.drawRightString(W - 0.18*inch, H - 0.22*inch, f"Mã vận đơn: {shipping_code}")
    c.setFont(F_REG, 7.5)
    c.drawRightString(W - 0.18*inch, H - 0.34*inch, f"Mã đơn hàng: {order_code}")

    # Barcode mã vận đơn
    if shipping_code:
        try:
            bc = code128.Code128(shipping_code, barHeight=0.28*inch, barWidth=0.9)
            bc.drawOn(c, W - 1.5*inch, H - 0.38*inch)
        except:
            pass

    # Đường kẻ ngang dưới header
    y_line = H - 0.45*inch
    c.setLineWidth(1.5)
    c.line(0.18*inch, y_line, W - 0.18*inch, y_line)

    # ════════════════════════════════
    # TỪ / ĐẾN
    # ════════════════════════════════
    y_from = H - 1.08*inch
    c.setLineWidth(0.8)
    # Box TỪ
    c.rect(0.18*inch, y_from - 0.32*inch, 1.2*inch, 0.44*inch)
    c.setFont(F_BOLD, 7)
    c.drawString(0.24*inch, y_from + 0.04*inch, "Từ:")
    shop_lines = simpleSplit(shop_name, F_BOLD, 8, 1.1*inch)
    c.setFont(F_BOLD, 8)
    for i, ln in enumerate(shop_lines[:2]):
        c.drawString(0.24*inch, y_from - 0.08*inch - i*0.13*inch, ln)

    # Box ĐẾN
    c.rect(1.52*inch, y_from - 0.32*inch, W - 1.7*inch, 0.44*inch)
    c.setFont(F_BOLD, 7)
    c.drawString(1.58*inch, y_from + 0.04*inch, "Đến:")
    c.setFont(F_BOLD, 8.5)
    c.drawString(1.58*inch, y_from - 0.08*inch, customer_name[:28])
    c.setFont(F_REG, 7)
    addr_lines = simpleSplit(address, F_REG, 7, 2.2*inch)
    for i, ln in enumerate(addr_lines[:2]):
        c.drawString(1.58*inch, y_from - 0.22*inch - i*0.12*inch, ln)

    # ════════════════════════════════
    # NỘI DUNG HÀNG + QR
    # ════════════════════════════════
    y_content = H - 2.05*inch
    box_h = 1.1*inch
    c.setLineWidth(0.8)
    # Box sản phẩm
    c.rect(0.18*inch, y_content - box_h, 2.9*inch, box_h)
    c.setFont(F_BOLD, 7.5)
    c.drawString(0.24*inch, y_content - 0.14*inch, "Nội dung hàng (Tổng SL sản phẩm: 1)")
    c.setFont(F_REG, 7.5)
    prod_lines = simpleSplit(f"1. {product}, SL: 1", F_REG, 7.5, 2.78*inch)
    for i, ln in enumerate(prod_lines[:4]):
        c.drawString(0.24*inch, y_content - 0.28*inch - i*0.13*inch, ln)

    # Ghi chú nhỏ
    c.setFont(F_REG, 6)
    note = "Kiểm tra tên sản phẩm và đối chiếu Mã vận đơn/ Mã đơn hàng trước khi nhận hàng (Lưu ý: Một số sản phẩm có thể bị ẩn do danh sách quá dài.)"
    note_lines = simpleSplit(note, F_REG, 6, 2.78*inch)
    for i, ln in enumerate(note_lines[:3]):
        c.drawString(0.24*inch, y_content - 0.84*inch - i*0.10*inch, ln)

    # Box QR / mã kho
    c.rect(3.16*inch, y_content - box_h, 0.66*inch, box_h)
    c.setFont(F_BOLD, 7.5)
    c.drawCentredString(3.49*inch, y_content - 0.28*inch, "HN-20")
    c.setFont(F_REG, 6.5)
    c.drawCentredString(3.49*inch, y_content - 0.42*inch, "03-01")

    # ════════════════════════════════
    # NGÀY ĐẶT HÀNG
    # ════════════════════════════════
    y_date = y_content - box_h - 0.2*inch
    c.setLineWidth(0.5)
    c.line(0.18*inch, y_date, W - 0.18*inch, y_date)
    c.setFont(F_REG, 7)
    c.drawRightString(W - 0.18*inch, y_date - 0.14*inch, "Ngày đặt hàng:")
    c.setFont(F_BOLD, 9)
    c.drawRightString(W - 0.18*inch, y_date - 0.27*inch, order_date)

    # ════════════════════════════════
    # TIỀN THU + CHỮ KÝ
    # ════════════════════════════════
    y_money = y_date - 0.45*inch
    c.setLineWidth(1.5)
    c.line(0.18*inch, y_money, W - 0.18*inch, y_money)
    c.setFont(F_REG, 7.5)
    c.drawString(0.18*inch, y_money - 0.20*inch, "Tiền thu người nhận:")
    c.setFont(F_BOLD, 7)
    c.drawRightString(W - 0.18*inch, y_money - 0.14*inch, f"Khối lượng tối đa: 100g")
    c.setFont(F_BOLD, 20)
    c.drawString(0.18*inch, y_money - 0.48*inch, f"{total} VND" if total else "")

    # Box chữ ký
    y_sign = y_money - 0.55*inch
    c.setLineWidth(0.8)
    c.rect(2.9*inch, y_sign - 0.55*inch, W - 3.08*inch, 0.65*inch)
    c.setFont(F_BOLD, 7.5)
    c.drawCentredString(3.49*inch, y_sign - 0.08*inch, "Chữ ký người nhận")
    c.setFont(F_REG, 6.5)
    c.drawCentredString(3.49*inch, y_sign - 0.20*inch, "Xác nhận hàng nguyên vẹn, không")
    c.drawCentredString(3.49*inch, y_sign - 0.31*inch, "móp/méo, bể/vỡ")

    # ════════════════════════════════
    # CHỈ DẪN GIAO HÀNG
    # ════════════════════════════════
    y_guide = y_sign - 0.65*inch
    c.setLineWidth(0.5)
    c.setDash(3, 2)
    c.line(0.18*inch, y_guide + 0.05*inch, W - 0.18*inch, y_guide + 0.05*inch)
    c.setDash()
    c.setFont(F_BOLD, 6.5)
    guide = "Chỉ dẫn giao hàng: Được đồng kiểm; Không bóc tem, seal, thử sản phẩm; Chuyển hoàn sau 3 lần phát; Lưu kho tối đa 5 ngày."
    guide_lines = simpleSplit(guide, F_BOLD, 6.5, W - 0.36*inch)
    for i, ln in enumerate(guide_lines):
        c.drawString(0.18*inch, y_guide - i*0.12*inch, ln)

    c.save()
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={order_code}.pdf"}
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
            col_date    = fc("Thời gian đặt hàng") or fc("ngày đặt")
            col_name    = fc("Người đặt hàng") or fc("tên khách")
            col_phone   = fc("số điện thoại") or fc("điện thoại")
            col_address = fc("địa chỉ")
            col_product = fc("tên sản phẩm") or fc("sản phẩm")
            col_qty     = fc("số lượng") or fc("sl")  
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
                    "quantity":      gv(col_qty), 
                    "total":         gv(col_total),
                })
            return orders

        except Exception as e:
            print(f"[delivering] {sid} lỗi: {e}")
            return []

    # Gọi song song tất cả shop, giới hạn 10 request cùng lúc tránh bị block
    semaphore = asyncio.Semaphore(2)

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
        "LOGIN-KEY-PHUONG2000": {"hours": 1,           "label": "Phương"},
        "LOGIN-KEY-CHANGTESTUSER":    {"hours": 9999999999,   "label": "Hoàng"},
        "Chang2000":    {"hours": 9999999999,   "label": "Hoàng"},
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
@app.get("/api/orders/mien-bac")
async def get_mien_bac_orders(request: Request, db: Session = Depends(get_db)):
    user_id = request.headers.get("X-User-ID", "")
    keywords = [
        "hải phòng", "hai phong",
        "bắc giang", "bac giang", "bắc kạn", "bac kan",
        "cao bằng", "cao bang", "hà giang", "ha giang",
        "lạng sơn", "lang son", "phú thọ", "phu tho",
        "quảng ninh", "quang ninh", "thái nguyên", "thai nguyen",
        "tuyên quang", "tuyen quang", "điện biên", "dien bien",
        "hòa bình", "hoa binh", "lai châu", "lai chau",
        "lào cai", "lao cai", "sơn la", "son la",
        "yên bái", "yen bai", "bắc ninh", "bac ninh",
        "hà nam", "ha nam", "hải dương", "hai duong",
        "hưng yên", "hung yen", "nam định", "nam dinh",
        "ninh bình", "ninh binh", "thái bình", "thai binh",
        "vĩnh phúc", "vinh phuc"
    ]
    filters = [func.lower(Order.address).contains(kw.lower()) for kw in keywords]
    orders = db.query(Order).filter(or_(*filters)).order_by(Order.order_date.desc()).all()
    def serialize_with_user(o):
        mask = o.shop_id in BLOCKED_SHOPS and user_id != 'Chang2000'
        return serialize_order(o, mask=mask)
    return [serialize_with_user(o) for o in orders]

@app.post("/api/order/cancel")
async def cancel_order(body: dict):
    order_code = body.get("order_code", "").strip()
    cancel_key = body.get("cancel_key", "").strip()

    if not order_code or not cancel_key:
        return JSONResponse({"error": "Thiếu mã đơn hàng hoặc cancel key."}, status_code=400)

    if cancel_key not in CANCEL_KEYS:
        return JSONResponse({"error": "Cancel Key không hợp lệ."}, status_code=403)

    if cancel_key not in CANCEL_UNLIMITED_KEYS and CANCEL_KEYS[cancel_key] >= CANCEL_KEY_LIMIT:
        return JSONResponse({"error": f"Cancel Key đã hết lượt sử dụng ({CANCEL_KEY_LIMIT}/{CANCEL_KEY_LIMIT})."}, status_code=403)


    if len(order_code) < 9:
        return JSONResponse({"error": "Mã đơn hàng không hợp lệ."}, status_code=400)

    # order_id và input_id = 7 số sau 2 ký tự đầu
    # VD: R8547883114 → bỏ "R8" → lấy "5478831"
    order_id = order_code[2:9]
    url = f"https://ec.megaads.vn/service/inoutput/find-promotion-codes-api?inoutputId={order_id}"
    session = "eyJpdiI6ImIra2pmWitCVVRRTlp2K3pRUUZOZ1E9PSIsInZhbHVlIjoibXpYaFhkQmVZU1VMRFRKWWhEcXRCdnBFSWdycVNzNFlSVHpGWjVYT0hTVDFpdlErVWxDSWhEaVdcL3JyT2RvSjZIcDNkMVJSYTllZDJMMTlsR2ZIQ3BnPT0iLCJtYWMiOiI2MDc2MTFlNDg0MTg4M2IyNDBiNDAzMDE4ZWE0MTk0ZTFkNDdlNGU3MjQ0ZjA3ODFkYTlkYzZiMjcyOTEyMzNmIn0%3D"

    try:
        # Bước 1: Lấy sync_id
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

        sync_id = d.get("sync_id") or d.get("id")

        print(f"[cancel] order_code={order_code} → order_id={order_id} | sync_id={sync_id}")

        if not sync_id:
            return JSONResponse({
                "error": "Không lấy được sync_id. Liên hệ admin để được hỗ trợ về đơn hàng này.",
                "debug_keys": list(d.keys()) if isinstance(d, dict) else str(d)
            }, status_code=400)

        # Bước 2: Huỷ đơn với sync_id + order_id vừa lấy
        cancel_payload = {
            "sync_id": str(sync_id),
            "order_id": str(order_id),
            "cancel_code": "change_item_order",
            "cancel_reason": "Thay đổi đơn hàng (màu sắc, kích thước, thêm mã giảm giá,...)"
        }

        print(f"[cancel] payload → {cancel_payload}")

        async with httpx.AsyncClient(timeout=15) as client:
            cancel_res = await client.post(
                "https://api.chiaki.vn/api/order/request-cancel",
                json=cancel_payload,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Encoding": "gzip, deflate",
                    "Content-Type": "application/json",
                    "token": "YjYTQY7fP4vExhg0a8itBqBEFKzZlmcKWBoxkwc91XNyF3zpCi",
                    "User-Agent": "chiakiApp/3.6.2"
                }
            )
            result = cancel_res.json()

        print(f"[cancel] result → {result}")

        # Kiểm tra kết quả
        status = result.get("status") or result.get("message") or ""
        if "successful" in str(status).lower() or result.get("success") is True:
            CANCEL_KEYS[cancel_key] += 1
            remaining = -1 if cancel_key in CANCEL_UNLIMITED_KEYS else CANCEL_KEY_LIMIT - CANCEL_KEYS[cancel_key]

            from datetime import timezone as _tz
            now_vn = datetime.now(_tz(timedelta(hours=7))).strftime("%d/%m/%Y %H:%M")
            CANCEL_KEY_HISTORY[cancel_key].append({"order_code": order_code, "time": now_vn})

            return {"ok": True, "message": "Đã huỷ đơn hàng thành công.", "remaining": remaining}
        else:
            return JSONResponse({
                "error": "Liên hệ admin để được hỗ trợ về đơn hàng này.",
                "detail": result
            }, status_code=400)

    except Exception as e:
        return JSONResponse({"error": f"Lỗi khi gọi API: {str(e)}"}, status_code=500)
@app.post("/api/order/cancel/check-key")
async def check_cancel_key(body: dict):
    key = body.get("key", "").strip()
    if key not in CANCEL_KEYS:
        return JSONResponse({"error": "Cancel Key không hợp lệ."}, status_code=403)
    used = CANCEL_KEYS[key]
    is_unlimited = key in CANCEL_UNLIMITED_KEYS
    return {
        "used": used,
        "remaining": -1 if is_unlimited else CANCEL_KEY_LIMIT - used,
        "limit": -1 if is_unlimited else CANCEL_KEY_LIMIT,
        "unlimited": is_unlimited
    }
@app.post("/api/shop-orders/check-key")
async def check_getorder_key(body: dict):
    key = body.get("key", "").strip()
    if key not in GETORDER_KEYS:
        return JSONResponse({"error": "GETORDER-KEY không hợp lệ."}, status_code=403)
    used = GETORDER_KEYS[key]
    is_unlimited = key in GETORDER_UNLIMITED_KEYS
    return {
        "used": used,
        "remaining": -1 if is_unlimited else GETORDER_KEY_LIMIT - used,
        "limit": -1 if is_unlimited else GETORDER_KEY_LIMIT,
        "unlimited": is_unlimited,
    }

@app.post("/api/shop-orders")
async def get_shop_orders(body: dict, db: Session = Depends(get_db)):
    try:
        import re
        shop_url = body.get("shop_url", "").strip()
        key      = body.get("key", "").strip()

        if not shop_url or not key:
            return JSONResponse({"error": "Thiếu link gian hàng hoặc key."}, status_code=400)
        if key not in GETORDER_KEYS:
            return JSONResponse({"error": "GETORDER-KEY không hợp lệ."}, status_code=403)
        if key not in GETORDER_UNLIMITED_KEYS and GETORDER_KEYS[key] >= GETORDER_KEY_LIMIT:
            return JSONResponse({"error": f"Key đã hết lượt ({GETORDER_KEY_LIMIT}/{GETORDER_KEY_LIMIT})."}, status_code=403)

        m = re.search(r'gian-hang-([A-Z0-9]+)', shop_url, re.IGNORECASE)
        if not m:
            return JSONResponse({"error": "Link không hợp lệ. VD: https://chiaki.vn/gian-hang-ST****"}, status_code=400)
        store_code = m.group(1).upper()

        shops = get_shops_map()
        numeric_shop_id = None
        shop_name = None
        for sid, val in shops.items():
            # val có thể là (url, name) hoặc dạng khác — xử lý an toàn
            if isinstance(val, (list, tuple)) and len(val) >= 2:
                s_url, s_name = val[0], val[1]
            elif isinstance(val, str):
                s_url, s_name = val, str(sid)
            else:
                continue
            if store_code.lower() in str(s_url).lower():
                numeric_shop_id = str(sid)
                shop_name = s_name
                break

        print(f"[shop-orders] store_code={store_code} → shop_id={numeric_shop_id}, name={shop_name}")

        if not numeric_shop_id:
            return JSONResponse({"error": f"Không tìm thấy gian hàng '{store_code}'."}, status_code=404)
        PROTECTED_SHOPS = {"4917", "4647", "4732", "5112", "4940", "5096", "5125"}
        if numeric_shop_id in PROTECTED_SHOPS:
            return JSONResponse({
                "error": "⚠️ Bạn đang có dấu hiệu xâm phạm thông tin shop của admin, bạn sẽ bị thu hồi toàn bộ KEY và KHÔNG HOÀN TIỀN nếu tiếp tục vi phạm."
            }, status_code=403)
        # Lấy tất cả status trong DB của shop này
        status_stats = (
            db.query(Order.status, func.count(Order.id))
            .filter(Order.shop_id == numeric_shop_id)
            .group_by(Order.status)
            .all()
        )
        print(f"[shop-orders] status_stats={status_stats}")

        all_statuses = [str(s) for s, _ in status_stats if s is not None]

        KEYWORDS = ["request_out", "delivering", "wait", "chờ", "lấy hàng", "đang giao", "pickup"]
        matched_statuses = [
            s for s in all_statuses
            if any(kw.lower() in s.lower() for kw in KEYWORDS)
        ]
        print(f"[shop-orders] matched_statuses={matched_statuses}")

        if matched_statuses:
            orders_db = (
                db.query(Order)
                .filter(Order.shop_id == numeric_shop_id, Order.status.in_(matched_statuses))
                .order_by(Order.order_date.desc())
                .all()
            )
        else:
            # Không khớp keyword → trả 20 đơn gần nhất để debug
            orders_db = (
                db.query(Order)
                .filter(Order.shop_id == numeric_shop_id)
                .order_by(Order.order_date.desc())
                .limit(20)
                .all()
            )

        GETORDER_KEYS[key] += 1
        remaining = -1 if key in GETORDER_UNLIMITED_KEYS else GETORDER_KEY_LIMIT - GETORDER_KEYS[key]
        from datetime import timezone as _tz
        now_vn = datetime.now(_tz(timedelta(hours=7))).strftime("%d/%m/%Y %H:%M")
        GETORDER_KEY_HISTORY.setdefault(key, []).append({"shop_url": shop_url, "time": now_vn})

        return {
            "shop_name":      shop_name,
            "shop_id":        numeric_shop_id,
            "store_code":     store_code,
            "total":          len(orders_db),
            "remaining":      remaining,
            "debug_statuses": [[s, c] for s, c in status_stats],
            "orders": [{
                "order_code":    o.order_code,
                "order_date":    o.order_date,
                "customer_name": o.customer_name or o.buyer_name,
                "phone":         o.phone,
                "product":       o.product,
                "quantity":      o.quantity,
                "total":         str(o.total) if o.total else None,
                "status":        o.status,
            } for o in orders_db],
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": f"Lỗi server: {str(e)}"}, status_code=500)

@app.get("/api/shops-list")
def get_shops_list():
    from shops_config import get_shops_map, SHOP_NAME_MAP
    shops = get_shops_map()
    result = []
    for shop_id, (shop_url, shop_name) in shops.items():
        result.append({
            "shop_id": shop_id,
            "shop_name": shop_name,
            "shop_url": shop_url
        })
    return sorted(result, key=lambda x: x["shop_name"])

@app.post("/api/sync")
async def sync_now(body: dict, db: Session = Depends(get_db)):
    shop_id     = body.get("shop_id", "").strip()
    cf_chl_tk   = body.get("cf_chl_tk", "").strip()
    cf_clearance = body.get("cf_clearance", "").strip()

    if not shop_id:
        return JSONResponse({"error": "Thiếu shop_id"}, status_code=400)
    if not cf_chl_tk or not cf_clearance:
        return JSONResponse({"error": "Thiếu cf_chl_tk hoặc cf_clearance"}, status_code=400)

    shops = get_shops_map()
    if shop_id not in shops:
        return JSONResponse({"error": f"Không tìm thấy shop {shop_id}"}, status_code=404)

    shop_url, shop_name = shops[shop_id]

    try:
        synced = await sync_shop(shop_id, shop_url, shop_name, db,
                                 cf_chl_tk=cf_chl_tk, cf_clearance=cf_clearance)
        return {"ok": True, "shop_id": shop_id, "shop_name": shop_name, "synced": synced}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

@app.post("/api/sync-upload")
async def sync_upload(
    shop_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        shops = get_shops_map()
        if shop_id not in shops:
            return JSONResponse({"error": f"Không tìm thấy shop {shop_id}"}, status_code=404)

        shop_url, shop_name = shops[shop_id]
        content = await file.read()

        # Kiểm tra có phải Excel không (magic bytes PK = xlsx)
        if len(content) < 100:
            return JSONResponse({"error": "File quá nhỏ, không hợp lệ"}, status_code=422)

        orders = parse_excel(content, shop_id, shop_name)
        if not orders:
            return JSONResponse({"error": "Không đọc được dữ liệu từ file Excel. Kiểm tra lại cột header."}, status_code=422)

        deleted = db.query(Order).filter(Order.shop_id == shop_id).delete()
        for o in orders:
            db.add(Order(**o))
        db.commit()

        meta = db.query(ShopMeta).filter(ShopMeta.shop_id == shop_id).first()
        if meta:
            meta.shop_name   = shop_name
            meta.last_sync   = datetime.now()
            meta.order_count = len(orders)
        else:
            db.add(ShopMeta(
                shop_id=shop_id, shop_name=shop_name,
                shop_url=shop_url, last_sync=datetime.now(),
                order_count=len(orders)
            ))
        db.commit()

        return {
            "ok": True,
            "shop_id": shop_id,
            "shop_name": shop_name,
            "synced": len(orders),
            "deleted": deleted
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)
