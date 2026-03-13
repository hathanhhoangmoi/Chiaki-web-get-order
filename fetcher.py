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

def parse_excel(content: bytes, shop_id: str, shop_name: str) -> list[dict]:
    """Đọc Excel, chuẩn hoá cột, trả về list dict"""
    try:
        df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
        df.columns = [str(c).strip() for c in df.columns]

        # Map cột linh hoạt — tìm theo từ khoá trong tên cột
        def find_col(keywords: list) -> str | None:
            for kw in keywords:
                for col in df.columns:
                    if kw.lower() in col.lower():
                        return col
            return None

        col_code    = find_col(["mã đơn", "order_id", "order id", "mã"])
        col_buyer   = find_col(["tên", "buyer", "khách", "người mua"])
        col_phone   = find_col(["điện thoại", "phone", "sdt", "số đt"])
        col_address = find_col(["địa chỉ", "address", "địa chi"])
        col_product = find_col(["sản phẩm", "product", "tên sp", "hàng"])
        col_qty     = find_col(["số lượng", "quantity", "qty", "sl"])
        col_total   = find_col(["tổng", "total", "tiền", "amount"])
        col_status  = find_col(["trạng thái", "status", "tình trạng"])
        col_date    = find_col(["ngày", "date", "thời gian", "tạo"])

        orders = []
        for _, row in df.iterrows():
            code = str(row[col_code]).strip() if col_code else f"{shop_id}_{_}"
            if not code or code == "nan":
                continue
            orders.append({
                "order_code": code,
                "shop_id":    shop_id,
                "shop_name":  shop_name,
                "buyer_name": str(row[col_buyer]).strip()   if col_buyer   else "",
                "phone":      str(row[col_phone]).strip()   if col_phone   else "",
                "address":    str(row[col_address]).strip() if col_address else "",
                "product":    str(row[col_product]).strip() if col_product else "",
                "quantity":   int(row[col_qty])   if col_qty and str(row[col_qty]) != "nan" else 0,
                "total":      float(row[col_total]) if col_total and str(row[col_total]) != "nan" else 0,
                "status":     str(row[col_status]).strip() if col_status else "",
                "order_date": str(row[col_date]).strip()   if col_date   else "",
                "raw_data":   json.dumps(row.to_dict(), ensure_ascii=False, default=str),
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
