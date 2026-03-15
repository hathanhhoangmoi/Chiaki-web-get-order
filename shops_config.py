import re

SHOPS = [
    ("https://chiaki.vn/stz88clwvl-st2732", "Min Duty"),
    ("https://chiaki.vn/gian-hang-st4299", "HADES Shop"),
    ("https://chiaki.vn/gian-hang-st3522", "ShipnhanhStore"),
    ("https://chiaki.vn/stk635opng-st4337", "TH Cosmetic"),
    ("https://chiaki.vn/stf4cahsa3-st3684", "Hoya Life"),
    ("https://chiaki.vn/stioaqzbw3-st3540", "Rongcon"),
    ("https://chiaki.vn/stioaqzbw3-st3783", "Đẹp & Khoẻ 365"),
    ("https://chiaki.vn/stioaqzbw3-st1489", "Beauty & Healthy"),
    ("https://chiaki.vn/stioaqzbw3-st4036", "Kitty House"),
    ("https://chiaki.vn/stioaqzbw3-st635", "Trang Perfume"),
    ("https://chiaki.vn/stioaqzbw3-st1498", "Kho Dược TPCN"),
    ("https://chiaki.vn/gian-hang-st5090", "Mason House Store"),
    ("https://chiaki.vn/gian-hang-st5091", "Gia Phương Shop"),
    ("https://chiaki.vn/gian-hang-st4339", "PINASAGO Pin Sài Gòn"),
    ("https://chiaki.vn/gian-hang-st4961", "Kalos Việt Nam"),
    ("https://chiaki.vn/gian-hang-st4872", "Green House"),
    ("https://chiaki.vn/gian-hang-st4917", "Moss Skincare"),
    ("https://chiaki.vn/gian-hang-st4647", "XXIV Store"),
    ("https://chiaki.vn/gian-hang-st4732", "Ken Perfume"),
    ("https://chiaki.vn/gian-hang-st5112", "MoiThom - Mèo bán nước hoa"),
    ("https://chiaki.vn/gian-hang-st2292", "Thế Giới Hàng Auth 88"),
    ("https://chiaki.vn/gian-hang-st4940", "Mint- Skin Beauty & Cosmetics"),
    ("https://chiaki.vn/gian-hang-st5096", "The Senté Hill"),
    ("https://chiaki.vn/gian-hang-st1164", "O2 PHARMACY"),
    ("https://chiaki.vn/gian-hang-st3612", "NGUYENKIM"),
    ("https://chiaki.vn/gian-hang-st5092", "Thế Giới Son"),
    ("https://chiaki.vn/gian-hang-st5125", "Felice Beauty Garden"),
]

# Credentials từ extension của bạn
SELLER_ID    = "4647"
SELLER_TOKEN = "ebf7e96d976f74aa77b2b874b7a087ef"
RESTRICTED_SHOPS = {"4917", "4647", "4732", "5112"}
RESTRICTED_PASS  = "38241540"

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
