import streamlit as st
import requests
import json
import re

# ตั้งค่าหน้าตาเว็บ
st.set_page_config(page_title="Price Hunter Pro", page_icon="🏷️", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 2.2rem; font-weight: bold; color: #ff4b4b; text-align: center; }
    .sub-title { font-size: 1.1rem; text-align: center; color: #666; margin-bottom: 2rem; }
    .best-price { color: #00875a; font-size: 1.5rem; font-weight: bold; }
    .normal-price { color: #d9381e; font-size: 1.2rem; font-weight: bold; }
    .shop-name { color: #1e88e5; font-size: 1.1rem; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# อ่านค่า Secrets
SERPAPI_KEY = st.secrets.get("SERPAPI_KEY", st.secrets.get("GEMINI_API_KEY", ""))
LINE_TOKEN = st.secrets.get("LINE_NOTIFY_TOKEN", "")

if "wishlist" not in st.session_state:
    st.session_state.wishlist = []

# --- ฟังก์ชันดึงเฉพาะชื่อร้านค้า ราคา และลิงก์พิกัดจริง ---
def fetch_real_shopping_data(keyword):
    if not SERPAPI_KEY:
        st.error("⚠️ ยังไม่ได้ใส่ SERPAPI_KEY ใน Secrets ครับ!")
        return []

    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_shopping",
        "q": keyword,
        "location": "Thailand",
        "hl": "th",
        "gl": "th",
        "api_key": SERPAPI_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        results = []
        shopping_results = data.get("shopping_results", [])

        for item in shopping_results[:8]:
            raw_price = item.get("extracted_price", 0)
            if not raw_price:
                price_str = re.sub(r'[^\d.]', '', str(item.get("price", "0")))
                try:
                    raw_price = float(price_str) if price_str else 0
                except ValueError:
                    raw_price = 0

            results.append({
                "title": item.get("title", keyword),
                "price": item.get("price", "ไม่ระบุราคา"),
                "num_price": raw_price,
                "source": item.get("source", "ไม่ระบุชื่อร้าน"),
                "link": item.get("link", "#"),
                "thumbnail": item.get("thumbnail", "https://via.placeholder.com/150")
            })

        return results

    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาดในการดึงข้อมูล: {e}")
        return []

# --- ฟังก์ชันส่ง LINE แจ้งเตือน: สรุปร้านค้าทั้งหมด + ลิงก์พิกัดร้าน ---
def send_line_alert_all_shops(keyword, best_deal, all_results):
    if not LINE_TOKEN:
        return False
    
    msg = f"🎯 [สรุปรายงานราคา] {keyword}\n"
    msg += f"--------------------------------\n"
    msg += f"🏆 ถูกที่สุด: {best_deal['source']} ({best_deal['price']})\n"
    msg += f"📍 ลิงก์ร้านถูกสุด:\n{best_deal['link']}\n"
    msg += f"--------------------------------\n"
    msg += f"📊 รายการร้านทั้งหมดที่หาเจอ:\n\n"
    
    for idx, item in enumerate(all_results[:5]):
        msg += f"{idx+1}. {item['source']}\n"
        msg += f"   🏷️ ราคา: {item['price']}\n"
        msg += f"   🔗 พิกัด: {item['link']}\n\n"
    
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_TOKEN}"}
    payload = {"messages": [{"type": "text", "text": msg}]}
    
    try:
        res = requests.post(url, headers=headers, json=payload)
        return res.status_code == 200
    except Exception:
        return False

# ================= UI STREAMLIT =================

st.markdown('<p class="main-title">🏷️ Price Hunter Pro (Price Comparison)</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">เปรียบเทียบราคาแต่ละร้านค้า ➔ ส่งสรุปร้านค้าและพิกัดลิงก์เข้า LINE</p>', unsafe_allow_html=True)

# 1. ค้นหา
st.subheader("1️⃣ ค้นหาชื่อสินค้าที่ต้องการเช็กราคาตามร้านค้า")
user_input = st.text_input(
    "ชื่อสินค้า / รุ่น / ยี่ห้อ:",
    placeholder="เช่น Anker Soundcore R60i NC หรือ iPhone 15 Pro Max"
)

if st.button("🔍 ดึงราคาทุกร้านค้า"):
    if user_input:
        with st.spinner("🌐 กำลังรวบรวมราคาจากร้านค้าต่างๆ..."):
            real_data = fetch_real_shopping_data(user_input)
            if real_data:
                st.session_state['search_results'] = real_data
                st.session_state['current_keyword'] = user_input
                st.success(f"✅ ดึงข้อมูลสำเร็จ พบทั้งหมด {len(real_data)} ร้านค้า!")
            else:
                st.warning("ไม่พบข้อมูลสินค้า หรือ API Key มีปัญหา")
    else:
        st.warning("กรุณาพิมพ์ชื่อสินค้าก่อนครับ")

st.divider()

# 2. ผลลัพธ์
if 'search_results' in st.session_state and st.session_state['search_results']:
    results = st.session_state['search_results']
    keyword = st.session_state.get('current_keyword', 'สินค้าที่เลือก')
    
    valid_prices = [x for x in results if x.get('num_price', 0) > 0]
    best_deal = min(valid_prices, key=lambda x: x.get('num_price', 0)) if valid_prices else results[0]

    st.subheader(f"2️⃣ รายการราคาของ: {keyword}")
    
    col_alert1, col_alert2 = st.columns([2, 1])
    with col_alert1:
        st.info(f"🏆 ร้านที่ขายถูกที่สุดในระบบขณะนี้: **{best_deal['source']}** ราคา **{best_deal['price']}**")
    with col_alert2:
        if st.button("📲 เล็งสินค้านี้ (ส่งรายการร้าน+พิกัดลิงก์เข้า LINE)", use_container_width=True):
            wish_item = {
                "keyword": keyword,
                "best_deal": best_deal,
                "all_shops": results
            }
            st.session_state.wishlist.append(wish_item)
            st.toast("บันทึกสินค้านี้เข้า Wishlist แล้ว!", icon="🎉")
            if send_line_alert_all_shops(keyword, best_deal, results):
                st.success("🔔 ส่งรายการร้าน+พิกัดลิงก์เข้า LINE เรียบร้อยแล้ว!")

    st.write("---")
    st.write("📊 **รายการร้านค้าที่พบทั้งหมด:**")
    
    for idx in range(0, len(results), 2):
        c1, c2 = st.columns(2)
        
        # การ์ดที่ 1
        with c1:
            item = results[idx]
            is_best = (item == best_deal)
            
            with st.container(border=True):
                if is_best:
                    st.markdown("⭐ **[ร้านที่ขายถูกที่สุด]**")
                st.image(item['thumbnail'], width=100)
                st.write(f"**{item['title']}**")
                st.markdown(f"🏪 ร้านค้า: <span class='shop-name'>{item['source']}</span>", unsafe_allow_html=True)
                price_class = "best-price" if is_best else "normal-price"
                st.markdown(f"🏷️ ราคาขาย: <span class='{price_class}'>{item['price']}</span>", unsafe_allow_html=True)

        # การ์ดที่ 2 (ถ้ามี)
        if idx + 1 < len(results):
            with c2:
                item2 = results[idx + 1]
                is_best2 = (item2 == best_deal)
                
                with st.container(border=True):
                    if is_best2:
                        st.markdown("⭐ **[ร้านที่ขายถูกที่สุด]**")
                    st.image(item2['thumbnail'], width=100)
                    st.write(f"**{item2['title']}**")
                    st.markdown(f"🏪 ร้านค้า: <span class='shop-name'>{item2['source']}</span>", unsafe_allow_html=True)
                    price_class2 = "best-price" if is_best2 else "normal-price"
                    st.markdown(f"🏷️ ราคาขาย: <span class='{price_class2}'>{item2['price']}</span>", unsafe_allow_html=True)

# 3. Wishlist
st.divider()
st.subheader("📋 3️⃣ รายการสินค้าที่คุณเล็งไว้")
if st.session_state.wishlist:
    for idx, wish in enumerate(st.session_state.wishlist):
        st.write(f"**{idx+1}. {wish['keyword']}**")
        st.write(f"• ร้านถูกสุด: **{wish['best_deal']['source']}** ({wish['best_deal']['price']})")
        st.write("---")
else:
    st.write("ยังไม่มีรายการสินค้าที่เล็งไว้")
