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
    </style>
""", unsafe_allow_html=True)

# อ่านค่า Secrets
SERPAPI_KEY = st.secrets.get("SERPAPI_KEY", st.secrets.get("GEMINI_API_KEY", ""))
LINE_TOKEN = st.secrets.get("LINE_NOTIFY_TOKEN", "")

if "wishlist" not in st.session_state:
    st.session_state.wishlist = []

# --- ฟังก์ชันดึงราคาจริงผ่าน SerpAPI ---
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
                # แปลงข้อความราคาเป็นตัวเลขไว้หาค่าต่ำสุด
                price_str = re.sub(r'[^\d.]', '', str(item.get("price", "0")))
                raw_price = float(price_str) if price_str else 0

            results.append({
                "title": item.get("title", keyword),
                "price": item.get("price", "ไม่ระบุราคา"),
                "num_price": raw_price,
                "source": item.get("source", "ร้านค้าออนไลน์"),
                "link": item.get("link", "#"),
                "thumbnail": item.get("thumbnail", "https://via.placeholder.com/150")
            })

        return results

    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาดในการดึงข้อมูล: {e}")
        return []

# --- ฟังก์ชันส่ง LINE เตือนร้านที่ถูกที่สุด ---
def send_line_alert_best_deal(keyword, best_deal, total_found):
    if not LINE_TOKEN:
        return False
    
    msg = f"\n🎯 [Price Hunter] บันทึกเล็งสินค้าสำเร็จ!\n"
    msg += f"📦 สินค้า: {keyword}\n"
    msg += f"🔍 ค้นพบทั้งหมด: {total_found} ร้านค้า\n"
    msg += f"--------------------------------\n"
    msg += f"🏆 ร้านที่ถูกที่สุดตอนนี้: {best_deal['source']}\n"
    msg += f"🏷️ ราคาต่ำสุด: {best_deal['price']}\n"
    msg += f"🔗 กดซื้อร้านถูกสุดได้ที่นี่:\n{best_deal['link']}"
    
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_TOKEN}"}
    payload = {"messages": [{"type": "text", "text": msg}]}
    
    res = requests.post(url, headers=headers, json=payload)
    return res.status_code == 200

# ================= UI STREAMLIT =================

st.markdown('<p class="main-title">🏷️ Price Hunter Pro (Product Price Tracker)</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">ค้นหาสินค้า ➔ เปรียบเทียบราคาทุกร้าน ➔ แจ้งเตือนร้านที่ถูกที่สุดเข้า LINE</p>', unsafe_allow_html=True)

# 1. ค้นหา
st.subheader("1️⃣ พิมพ์ชื่อสินค้าที่ต้องการเล็งติดตามราคา")
user_input = st.text_input(
    "ชื่อสินค้า / รุ่น / ยี่ห้อ:",
    placeholder="เช่น Anker Soundcore R60i NC หรือ iPhone 15 Pro Max"
)

if st.button("🔍 ดึงข้อมูลและค้นหาร้านที่ถูกที่สุด"):
    if user_input:
        with st.spinner("🌐 กำลังค้นหาราคาจากทุกร้านค้าในตลาด..."):
            real_data = fetch_real_shopping_data(user_input)
            if real_data:
                st.session_state['search_results'] = real_data
                st.session_state['current_keyword'] = user_input
                st.success(f"✅ ดึงราคาจริงสำเร็จ เจอทั้งหมด {len(real_data)} ร้านค้า!")
            else:
                st.warning("ไม่พบข้อมูลสินค้า หรือ API Key มีปัญหา")
    else:
        st.warning("กรุณาพิมพ์ชื่อสินค้าก่อนครับ")

st.divider()

# 2. ผลลัพธ์
if 'search_results' in st.session_state and st.session_state['search_results']:
    results = st.session_state['search_results']
    keyword = st.session_state.get('current_keyword', 'สินค้าที่เลือก')
    
    # หาร้านที่ถูกที่สุด (ร้านที่ num_price > 0 และต่ำที่สุด)
    valid_prices = [x for x in results if x['num_price'] > 0]
    best_deal = min(valid_prices, key=lambda x: x['num_price']) if valid_prices else results[0]

    # ส่วนหัวสำหรับกดเล็งทั้งตัวสินค้า
    st.subheader(f"2️⃣ ผลการเปรียบเทียบราคาของ: {keyword}")
    
    col_alert1, col_alert2 = st.columns([2, 1])
    with col_alert1:
        st.info(f"🏆 ร้านที่ขายถูกที่สุดตอนนี้คือ **{best_deal['source']}** ในราคา **{best_deal['price']}**")
    with col2 if 'col2' in locals() else col_alert2:
        if st.button("❤️ เล็งสินค้านี้ (ติดตามร้านที่ถูกที่สุด)", use_container_width=True):
            wish_item = {
                "keyword": keyword,
                "best_deal": best_deal,
                "total_shops": len(results)
            }
            st.session_state.wishlist.append(wish_item)
            st.toast("บันทึกสินค้านี้เข้า Wishlist แล้ว!", icon="🎉")
            if send_line_alert_best_deal(keyword, best_deal, len(results)):
                st.success("🔔 ส่งข้อมูลร้านถูกที่สุดเข้า LINE เรียบร้อยแล้ว!")

    st.write("---")
    st.write("🔎 **รายการร้านค้าทั้งหมดที่จำหน่ายสินค้านี้:**")

    # แสดงผล Card Grid 2 คอลัมน์
    for idx in range(0, len(results), 2):
        c1, c2 = st.columns(2)
        
        # การ์ดที่ 1
        with c1:
            item = results[idx]
            is_best = (item == best_deal)
            border_color = "green" if is_best else "#ccc"
            
            with st.container(border=True):
                if is_best:
                    st.markdown("⭐ **[ร้านที่ถูกที่สุด]**")
                st.image(item['thumbnail'], width=130)
                st.write(f"**{item['title']}**")
                st.write(f"🏪 ร้านค้า: **{item['source']}**")
                price_class = "best-price" if is_best else "normal-price"
                st.markdown(f"🏷️ ราคา: <span class='{price_class}'>{item['price']}</span>", unsafe_allow_html=True)
                
                # ปุ่มลิงก์ภายนอกแบบกดแล้วเปิดแท็บใหม่แน่นอน 100%
                st.link_button("👉 กดเพื่อไปยังหน้าร้านซื้อเลย", item['link'], use_container_width=True)

        # การ์ดที่ 2 (ถ้ามี)
        if idx + 1 < len(results):
            with c2:
                item2 = results[idx + 1]
                is_best2 = (item2 == best_deal)
                
                with st.container(border=True):
                    if is_best2:
                        st.markdown("⭐ **[ร้านที่ถูกที่สุด]**")
                    st.image(item2['thumbnail'], width=130)
                    st.write(f"**{item2['title']}**")
                    st.write(f"🏪 ร้านค้า: **{item2['source']}**")
                    price_class2 = "best-price" if is_best2 else "normal-price"
                    st.markdown(f"🏷️ ราคา: <span class='{price_class2}'>{item2['price']}</span>", unsafe_allow_html=True)
                    
                    st.link_button("👉 กดเพื่อไปยังหน้าร้านซื้อเลย", item2['link'], use_container_width=True)

# 3. Wishlist สินค้าที่เล็งไว้
st.divider()
st.subheader("📋 3️⃣ รายการสินค้าที่คุณกดเล็งติดตามไว้")
if st.session_state.wishlist:
    for idx, wish in enumerate(st.session_state.wishlist):
        st.write(f"**{idx+1}. {wish['keyword']}** — ร้านถูกสุด: **{wish['best_deal']['source']}** ({wish['best_deal']['price']})")
        st.link_button(f"🔗 ไปยังร้านถูกที่สุดของ {wish['keyword']}", wish['best_deal']['link'])
        st.write("---")
else:
    st.write("ยังไม่มีรายการสินค้าที่เล็งไว้")
