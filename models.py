from sqlalchemy import Column, String, Integer, Float, DateTime, Text
from sqlalchemy.sql import func
from database import Base

class Order(Base):
    __tablename__ = "orders"

    id          = Column(Integer, primary_key=True, index=True)
    order_code = Column(String, index=True)
    shop_id     = Column(String, index=True)
    shop_name   = Column(String)
    buyer_name  = Column(String)
    customer_name = Column(String)
    phone       = Column(String)
    address     = Column(Text)
    product     = Column(Text)
    quantity    = Column(Integer, default=0)
    total       = Column(Float, default=0)
    status      = Column(String)
    order_date  = Column(String)
    raw_data    = Column(Text)   # JSON toàn bộ row gốc
    fetched_at  = Column(DateTime, server_default=func.now())

class ShopMeta(Base):
    __tablename__ = "shop_meta"

    shop_id     = Column(String, primary_key=True)
    shop_name   = Column(String)
    shop_url    = Column(String)
    last_sync   = Column(DateTime)
    order_count = Column(Integer, default=0)
buyer_name    = Column(String)
customer_name = Column(String)   # ← thêm dòng này (Người đặt hàng)
