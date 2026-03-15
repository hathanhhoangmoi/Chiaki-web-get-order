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
    ("https://chiaki.vn/gian-hang-st1600", "ChoychoyStore"),
    ("https://chiaki.vn/gian-hang-st2423", "Peony Cosmetics"),
    ("https://chiaki.vn/gian-hang-st4965", "nhathuocsuckhoe2"),
    ("https://chiaki.vn/gian-hang-st4365", "Nana Beauty & More"),
    ("https://chiaki.vn/gian-hang-st1729", "MHDMART"),
    ("https://chiaki.vn/gian-hang-st4360", "SnapshopVN"),
    ("https://chiaki.vn/gian-hang-st5094", "Shop Snap TPHCM"),
    ("https://chiaki.vn/gian-hang-st1602", "Winny Shop"),
    ("https://chiaki.vn/gian-hang-st1105", "MjuMju"),
    ("https://chiaki.vn/gian-hang-st4294", "Life Healthy"),
    ("https://chiaki.vn/gian-hang-st3009", "QuangNgoc1976"),
    ("https://chiaki.vn/gian-hang-st1414", "Dược Phẩm Tâm An"),
    ("https://chiaki.vn/gian-hang-st2573", "MiMi Beauty"),
    ("https://chiaki.vn/gian-hang-st2225", "T&T Japan shop"),
    ("https://chiaki.vn/gian-hang-st3047", "GREENBOX"),
    ("https://chiaki.vn/gian-hang-st3864", "Hàng ngoại giá tốt"),
    ("https://chiaki.vn/gian-hang-st3852", "Baby Grow Shop"),
    ("https://chiaki.vn/gian-hang-st1273", "NHÀ THUỐC MINH TÂM"),
    ("https://chiaki.vn/gian-hang-st3300", "Mayya Hàng Nội Địa Nhật"),
]

# Credentials từ extension của bạn
SELLER_ID    = "4647"
SELLER_TOKEN = "ebf7e96d976f74aa77b2b874b7a087ef"
BLOCKED_SHOPS = {
    "4917",  # Moss Skincare
    "4647",  # XXIV Store
    "4732",  # Ken Perfume
    "5112",  # MoiThom - Mèo bán nước hoa
    "4940",  # Mint- Skin Beauty & Cosmetics
    "5096",  # The Senté Hill
    "5125",  # Felice Beauty Garden
}

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
