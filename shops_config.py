import re

SHOPS = [
    ("https://chiaki.vn/stz88clwvl-st2732", "Min Duty"),
    ("https://chiaki.vn/gian-hang-st4299", "HADES Shop"),
    ("https://chiaki.vn/st8rbd8n7p-st3522", "ShipnhanhStore"),
    ("https://chiaki.vn/stk635opng-st4337", "TH Cosmetic"),
    ("https://chiaki.vn/stf4cahsa3-st3684", "Hoya Life"),
    ("https://chiaki.vn/stioaqzbw3-st3540", "Rongcon"),
    ("https://chiaki.vn/stioaqzbw3-st3783", "Đẹp & Khoẻ 365"),
    ("https://chiaki.vn/stioaqzbw3-st1489", "Beauty & Healthy"),
    ("https://chiaki.vn/stioaqzbw3-st4036", "Kitty House"),
    ("https://chiaki.vn/stioaqzbw3-st635", "Trang Perfume"),
    ("https://chiaki.vn/stioaqzbw3-st4917", "Moss Skincare"),
]

# Credentials từ extension của bạn
SELLER_ID    = "4647"
SELLER_TOKEN = "ebf7e96d976f74aa77b2b874b7a087ef"

def extract_id(url: str) -> str | None:
    m = re.search(r'-st(\d+)', url, re.IGNORECASE)
    return m.group(1) if m else None

def get_shops_map() -> dict:
    result = {}
    for url, name in SHOPS:
        sid = extract_id(url)
        if sid:
            result[sid] = (url, name)
    return result
