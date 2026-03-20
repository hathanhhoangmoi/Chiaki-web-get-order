import re

SHOPS = [
    ("https://chiaki.vn/stz88clwvl-st2732", "Min Duty", "STZ88CLWVL"),
    ("https://chiaki.vn/gian-hang-st4299", "HADES Shop", "STPU7XXLRO"),
    ("https://chiaki.vn/gian-hang-st3522", "ShipnhanhStore", "ST8RBD8N7P"),
    ("https://chiaki.vn/stk635opng-st4337", "TH Cosmetic", "STK635OPNG"),
    ("https://chiaki.vn/stf4cahsa3-st3684", "Hoya Life", "STF4CAHSA3"),
    ("https://chiaki.vn/stioaqzbw3-st3540", "Rongcon", "ST0FB63UNK"),
    ("https://chiaki.vn/stioaqzbw3-st3783", "Đẹp & Khoẻ 365", "ST52DPRAAQ"),
    ("https://chiaki.vn/stioaqzbw3-st1489", "Beauty & Healthy", "STYL4YS4G4"),
    ("https://chiaki.vn/stioaqzbw3-st4036", "Kitty House", "STXSHR33MD"),
    ("https://chiaki.vn/stioaqzbw3-st635", "Trang Perfume", "STMVBWFASC"),
    ("https://chiaki.vn/stioaqzbw3-st1498", "Kho Dược TPCN", "STIOAQZBW3"),
    ("https://chiaki.vn/gian-hang-st5090", "Mason House Store", "ST6UI8IKUZ"),
    ("https://chiaki.vn/gian-hang-st5091", "Gia Phương Shop", "ST5V3Z9EZ0"),
    ("https://chiaki.vn/gian-hang-st4339", "PINASAGO Pin Sài Gòn", "STBCBL0Q2J"),
    ("https://chiaki.vn/gian-hang-st4961", "Kalos Việt Nam", "ST7A4S1NMX"),
    ("https://chiaki.vn/gian-hang-st4872", "Green House", "STFXBK1K2R"),
    ("https://chiaki.vn/gian-hang-st4917", "Moss Skincare", "STMXKJHF9Q"),
    ("https://chiaki.vn/gian-hang-st4647", "XXIV Store", "ST1O3RWF9U"),
    ("https://chiaki.vn/gian-hang-st4732", "Ken Perfume", "ST8VBX0YDU"),
    ("https://chiaki.vn/gian-hang-st5112", "MoiThom - Mèo bán nước hoa", "STA0D5B480"),
    ("https://chiaki.vn/gian-hang-st2292", "Thế Giới Hàng Auth 88", "STD3YL1TSI"),
    ("https://chiaki.vn/gian-hang-st4940", "Mint- Skin Beauty & Cosmetics", "STIBP1581Z"),
    ("https://chiaki.vn/gian-hang-st5096", "The Senté Hill", "STUAT0DIPC"),
    ("https://chiaki.vn/gian-hang-st1164", "O2 PHARMACY", "ST62778NKR"),
    ("https://chiaki.vn/gian-hang-st3612", "NGUYENKIM", "STYKS36NRV"),
    ("https://chiaki.vn/gian-hang-st5092", "Thế Giới Son", "STICBF43TU"),
    ("https://chiaki.vn/gian-hang-st5125", "Felice Beauty Garden", ")STNAHLO6A2",
    ("https://chiaki.vn/gian-hang-st1600", "ChoychoyStore", "ST8TO6BBH6"),
    ("https://chiaki.vn/gian-hang-st2423", "Peony Cosmetics", "STMDTS134P"),
    ("https://chiaki.vn/gian-hang-st4965", "nhathuocsuckhoe2", "STD14EBRRV"),
    ("https://chiaki.vn/gian-hang-st4365", "Nana Beauty & More", "ST8IXXEWFP"),
    ("https://chiaki.vn/gian-hang-st1729", "MHDMART", "),
    ("https://chiaki.vn/gian-hang-st4360", "SnapshopVN", "),
    ("https://chiaki.vn/gian-hang-st5094", "Shop Snap TPHCM", "),
    ("https://chiaki.vn/gian-hang-st1602", "Winny Shop", "),
    ("https://chiaki.vn/gian-hang-st1105", "MjuMju", "),
    ("https://chiaki.vn/gian-hang-st4294", "Life Healthy", "),
    ("https://chiaki.vn/gian-hang-st3009", "QuangNgoc1976", "),
    ("https://chiaki.vn/gian-hang-st1414", "Dược Phẩm Tâm An", "),
    ("https://chiaki.vn/gian-hang-st2573", "MiMi Beauty", "),
    ("https://chiaki.vn/gian-hang-st2225", "T&T Japan shop", "),
    ("https://chiaki.vn/gian-hang-st3047", "GREENBOX", "),
    ("https://chiaki.vn/gian-hang-st3864", "Hàng ngoại giá tốt", "),
    ("https://chiaki.vn/gian-hang-st3852", "Baby Grow Shop", "),
    ("https://chiaki.vn/gian-hang-st1273", "NHÀ THUỐC MINH TÂM", "),
    ("https://chiaki.vn/gian-hang-st3300", "Mayya Hàng Nội Địa Nhật", "),
    ("https://chiaki.vn/gian-hang-st1258", "Shop Adam", "),
    ("https://chiaki.vn/gian-hang-st3337", "Shop Sài Gòn", "),
    ("https://chiaki.vn/gian-hang-st4342", "Sản Phẩm Hỗ Trợ", "),
    ("https://chiaki.vn/gian-hang-st1015", "Green Healthy & Beauty", "),
    ("https://chiaki.vn/gian-hang-st3218", "Bảo Lâm Anh", "),
    ("https://chiaki.vn/gian-hang-st2557", "XUAN MINH PHARMACY", "),    
]

# Credentials từ extension của bạn
SELLER_ID    = "4647"
SELLER_TOKEN = "ebf7e96d976f74aa77b2b874b7a087ef"
SHOP_NAME_MAP = {code: name for _, name, code in SHOPS}
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
