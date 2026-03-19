from sqlalchemy import Column, String, Integer, Float, DateTime, Text
from sqlalchemy.sql import func
from database import Base


# ─────────────────────────────────────────
# BẢNG DÙNG CHUNG (mixin để tránh lặp code)
# ─────────────────────────────────────────
class OrderMixin:
    id            = Column(Integer, primary_key=True, autoincrement=True)
    order_code    = Column(String, index=True)
    shop_id       = Column(String, index=True)
    shop_name     = Column(String)
    buyer_name    = Column(String)
    customer_name = Column(String)
    phone         = Column(String)
    address       = Column(Text)
    product       = Column(Text)
    quantity      = Column(String, default="")
    total         = Column(String, default="")
    order_date    = Column(String)
    fetched_at    = Column(DateTime, server_default=func.now())


# ─────────────────────────────────────────
# CHỜ LẤY HÀNG / CHUẨN BỊ HÀNG
# ─────────────────────────────────────────
class Order(OrderMixin, Base):
    __tablename__ = "orders"

    status   = Column(String)
    raw_data = Column(Text)  # JSON toàn bộ row gốc


# ─────────────────────────────────────────
# ĐANG GIAO
# ─────────────────────────────────────────
class DeliveringOrder(OrderMixin, Base):
    __tablename__ = "delivering_orders"


# ─────────────────────────────────────────
# ĐÃ GIAO
# ─────────────────────────────────────────
class FinishedOrder(OrderMixin, Base):
    __tablename__ = "finished_orders"


# ─────────────────────────────────────────
# HOÀN HÀNG
# ─────────────────────────────────────────
class ReturnedOrder(OrderMixin, Base):
    __tablename__ = "returned_orders"


# ─────────────────────────────────────────
# THÔNG TIN GIAN HÀNG
# ─────────────────────────────────────────
class ShopMeta(Base):
    __tablename__ = "shop_meta"

    shop_id     = Column(String, primary_key=True)
    shop_name   = Column(String)
    shop_url    = Column(String)
    last_sync   = Column(DateTime)
    order_count = Column(Integer, default=0)


# ─────────────────────────────────────────
# CACHE DOANH THU GỘP (30 ngày)
# ─────────────────────────────────────────
class RevenueCache(Base):
    __tablename__ = "revenue_cache"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    shop_id         = Column(String, unique=True, index=True)
    shop_name       = Column(String)
    ten_shop        = Column(String)
    chu_tk          = Column(String)
    ngan_hang       = Column(String)
    stk             = Column(String)
    doanh_thu_gop   = Column(Float, default=0)
    tong_khau_tru   = Column(Float, default=0)
    doanh_thu_thuan = Column(Float, default=0)
    date_range      = Column(String)
    fetched_at      = Column(DateTime, server_default=func.now())


# ─────────────────────────────────────────
# CACHE DOANH THU THUẦN (14 ngày)
# ─────────────────────────────────────────
class RevenueNetCache(Base):
    __tablename__ = "revenue_net_cache"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    shop_id         = Column(String, unique=True, index=True)
    shop_name       = Column(String)
    row_count       = Column(Integer, default=0)
    tong_tien       = Column(Float, default=0)
    phu_phi         = Column(Float, default=0)
    doanh_thu_thuan = Column(Float, default=0)
    date_range      = Column(String)
    fetched_at      = Column(DateTime, server_default=func.now())
