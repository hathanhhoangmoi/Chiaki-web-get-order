import re

SHOPS = [
    "https://chiaki.vn/stz88clwvl-st2732",  # Shop 1
    "https://chiaki.vn/gian-hang-st4299",  # Shop 2
    "https://chiaki.vn/st8rbd8n7p-st3522",  # Shop 3
    "https://chiaki.vn/stk635opng-st4337",  # Shop 3

]

# Credentials từ extension của bạn
SELLER_ID    = "4647"
SELLER_TOKEN = "ebf7e96d976f74aa77b2b874b7a087ef"

def extract_id(url: str) -> str | None:
    m = re.search(r'-st(\d+)', url, re.IGNORECASE)
    return m.group(1) if m else None

def get_shops_map() -> dict:
    """Trả về {shop_id: shop_url}"""
    result = {}
    for url in SHOPS:
        sid = extract_id(url)
        if sid:
            result[sid] = url
    return result
