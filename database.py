import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./chiaki.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    **({"connect_args": {"check_same_thread": False}} if "sqlite" in DATABASE_URL else {})
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def migrate():
    """Tự thêm cột mới nếu chưa tồn tại"""
    with engine.connect() as conn:
        # Danh sách cột cần đảm bảo tồn tại
        new_columns = [
            ("customer_name", "VARCHAR"),
        ]
        try:
    with engine.connect() as conn:
        conn.execute(text("DROP INDEX IF EXISTS ix_orders_order_code"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_orders_order_code ON orders (order_code)"))
        conn.commit()
        print("[migrate] Đã đổi order_code từ unique → index thường")
except Exception as e:
    print(f"[migrate] index: {e}")
        for col_name, col_type in new_columns:
            try:
                conn.execute(text(f"ALTER TABLE orders ADD COLUMN {col_name} {col_type}"))
                conn.commit()
                print(f"[migrate] Đã thêm cột: {col_name}")
            except Exception:
                pass  # Cột đã tồn tại → bỏ qua
