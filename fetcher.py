import httpx
import io
import json
import re
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models import Order, ShopMeta
from shops_config import SELLER_ID, SELLER_TOKEN

def build_api_url(shop_id: str) -> str:
    today = datetime.now()
    since = today - timedelta(days=30)
    def fmt(d): return d.strftime("%d/%m/%Y").replace("/", "%2F")
    range_str = f"{fmt(since)}%20-%20{fmt(today)}"
    return (
        f"https://api.chiaki.vn/api/{shop_id}/export-excel-order"
        f"?source=seller&page_index=1&page_size=500&status=receive_wating"
        f"&range_date={range_str}"
        f"&date_type=created_at&order=create-desc"
        f"&Seller_id={SELLER_ID}&Seller_token={SELLER_TOKEN}"
    )

async def fetch_shop_name(shop_url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(shop_url)
            match = re.search(r'<span[^>]*class="store-title"[^>]*>(.*?)</span>', res.text)
            return match.group(1).strip() if match else shop_url
    except:
        return shop_url

from openpyxl import load_workbook

def parse_excel(content: bytes, shop_id: str, shop_name: str) -> list[dict]:
    try:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            return []

        headers = [str(c).strip() if c else "" for c in rows[0]]

        def find_col(keywords):
            for kw in keywords:
                for i, h in enumerate(headers):
                    if kw.lower() in h.lower():
                        return i
            return None

        col_code    = find_col(["mã đơn", "order_id", "order id", "mã"])
        col_buyer   = find_col(["tên", "buyer", "khách", "người mua"])
        col_phone   = find_col(["điện thoại", "phone", "sdt"])
        col_address = find_col(["địa chỉ", "address"])
        col_product = find_col(["sản phẩm", "product", "hàng"])
        col_qty     = find_col(["số lượng", "quantity", "qty", "sl"])
        col_total   = find_col(["tổng", "total", "tiền", "amount"])
        col_status  = find_col(["trạng thái", "status"])
        col_date    = find_col(["ngày", "date", "thời gian"])

        def val(row, idx):
            if idx is None or idx >= len(row): return ""
            v = row[idx]
            return str(v).strip() if v is not None else ""

        orders = []
        for i, row in enumerate(rows[1:]):
            code = val(row, col_code) or f"{shop_id}_{i}"
            if not code or code == "None": continue
            try:
                qty   = int(float(val(row, col_qty)))   if val(row, col_qty)   else 0
                total = float(val(row, col_total))       if val(row, col_total) else 0.0
            except:
                qty, total = 0, 0.0
            orders.append({
                "order_code": code,
                "shop_id":    shop_id,
                "shop_name":  shop_name,
                "buyer_name": val(row, col_buyer),
                "phone":      val(row, col_phone),
                "address":    val(row, col_address),
                "product":    val(row, col_product),
                "quantity":   qty,
                "total":      total,
                "status":     val(row, col_status),
                "order_date": val(row, col_date),
                "raw_data":   json.dumps(
                    dict(zip(headers, [str(c) for c in row])),
                    ensure_ascii=False
                ),
            })
        return orders
    except Exception as e:
        print(f"[parse_excel] Error shop {shop_id}: {e}")
        return []

async def sync_shop(shop_id: str, shop_url: str, db: Session) -> int:
    """Fetch + parse + upsert orders cho 1 shop. Trả về số đơn mới."""
    shop_name = await fetch_shop_name(shop_url)
    url = build_api_url(shop_id)

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            res = await client.get(url)
            if res.status_code != 200:
                print(f"[sync_shop] {shop_id} HTTP {res.status_code}")
                return 0
            content = res.content
    except Exception as e:
        print(f"[sync_shop] {shop_id} fetch error: {e}")
        return 0

    orders = parse_excel(content, shop_id, shop_name)
    new_count = 0

    for o in orders:
        exists = db.query(Order).filter(Order.order_code == o["order_code"]).first()
        if not exists:
            db.add(Order(**o))
            new_count += 1

    # Cập nhật ShopMeta
    meta = db.query(ShopMeta).filter(ShopMeta.shop_id == shop_id).first()
    total_count = db.query(Order).filter(Order.shop_id == shop_id).count() + new_count
    if meta:
        meta.shop_name   = shop_name
        meta.last_sync   = datetime.now()
        meta.order_count = total_count
    else:
        db.add(ShopMeta(
            shop_id=shop_id, shop_name=shop_name,
            shop_url=shop_url, last_sync=datetime.now(),
            order_count=total_count
        ))

    db.commit()
    print(f"[sync] {shop_name} ({shop_id}): +{new_count} đơn mới")
    return new_count
