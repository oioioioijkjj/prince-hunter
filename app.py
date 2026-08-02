import streamlit as st
import requests
import json

# ตั้งค่าหน้าตาเว็บ
st.set_page_config(page_title="Price Hunter Pro", page_icon="🏷️", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 2.2rem; font-weight: bold; color: #ff4b4b; text-align: center; }
    .sub-title { font-size: 1.1rem; text-align: center; color: #666; margin-bottom: 2rem; }
    .product-price { color: #00875a; font-size: 1.4rem; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# อ่านค่า Secrets
SERPAPI_KEY = st.secrets.get("SERPAPI_KEY", "")
LINE_TOKEN = st.secrets.get("LINE_NOTIFY_TOKEN", "")

if "wishlist" not in st.session_state:
    st.session_state.wishlist = []

# --- ฟังก์ชันดึงราคาจริงและรูปจริงผ่าน SerpAPI ---
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

        # ดึง 6 รายการแรกที่เจอราคาจริงในไทย
        for item in shopping_results[:6]:
            results.append({
                "title": item.get("title", keyword),
                "price": item.get("price", "ไม่ระบุราคา"),
                "source": item.get("source", "ร้านค้าออนไลน์"),
                "link": item.get("link", "#"),
                "thumbnail": item.get("thumbnail", "https://via.placeholder.com/150")
            })

        return results

    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาดในการดึงข้อมูล: {e}")
        return []

# --- ฟังก์ชันส่ง LINE Notify ---
def send_line_alert(product):
    if not LINE_TOKEN:
        return False
    
    msg = f"\n🔥 [Price Hunter] บันทึกสินค้าติดตามราคาแล้ว!\n"
    msg += f"📦 สินค้า: {product['title']}\n"
    msg += f"🏷️ ราคาจริงปัจจุบัน: {product['price']}\n"
    msg += f"🏪 ร้านค้า: {product['source']}\n"
    msg += f"🔗 ลิงก์ตรงหน้าสินค้า:\n{product['link']}"
    
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_TOKEN}"}
    payload = {"messages": [{"type": "text", "text": msg}]}
    
    res = requests.post(url, headers=headers, json=payload)
    return res.status_code == 200

# ================= UI STREAMLIT =================

st.markdown('<p class="main-title">🏷️ Price Hunter Pro (Real-Time Search)</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">ระบบค้นหาราคาจริง + รูปภาพจริง + ลิงก์ตรง ณ วินาทีนี้</p>', unsafe_allow_html=True)

# 1. ค้นหา
st.subheader("1️⃣ พิมพ์ชื่อสินค้าที่ต้องการเช็กราคาจริง")
user_input = st.text_input(
    "ชื่อสินค้า / รุ่น / ยี่ห้อ:",
    placeholder="เช่น Anker Soundcore R60i NC หรือ iPhone 15 Pro Max"
)

if st.button("🔍 ค้นหาราคาและรูปภาพจริง"):
    if user_input:
        with st.spinner("🌐 กำลังดึงข้อมูลราคาจริงจากหน้าร้านค้าออนไลน์..."):
            real_data = fetch_real_shopping_data(user_input)
            if real_data:
                st.session_state['search_results'] = real_data
                st.success(f"✅ ดึงราคาจริงสำเร็จ เจอทั้งหมด {len(real_data)} รายการ!")
            else:
                st.warning("ไม่พบข้อมูลสินค้า หรือ API Key มีปัญหา")
    else:
        st.warning("กรุณาพิมพ์ชื่อสินค้าก่อนครับ")

st.divider()

# 2. ผลลัพธ์
if 'search_results' in st.session_state:
    st.subheader("2️⃣ ผลการเปรียบเทียบราคาจริงในตลาด ณ ตอนนี้")
    
    results = st.session_state['search_results']
    
    # แสดงผลเป็น Card Grid 2 คอลัมน์
    for idx in range(0, len(results), 2):
        col1, col2 = st.columns(2)
        
        # สินค้าการ์ดที่ 1
        with col1:
            item = results[idx]
            with st.container(border=True):
                st.image(item['thumbnail'], width=150)
                st.write(f"**{item['title']}**")
                st.write(f"🏪 ร้านค้า: **{item['source']}**")
                st.markdown(f"🏷️ ราคาจริง: <span class='product-price'>{item['price']}</span>", unsafe_unsafe_allow_html=True)
                st.markdown(f"[👉 กดตรงนี้เพื่อไปยังหน้าร้านค้า]({item['link']})")
                
                if st.button(f"❤️ เล็งรายการนี้", key=f"btn_{idx}"):
                    st.session_state.wishlist.append(item)
                    st.toast("บันทึกเข้ารายการเรียบร้อย!", icon="🎉")
                    send_line_alert(item)

        # สินค้าการ์ดที่ 2 (ถ้ามี)
        if idx + 1 < len(results):
            with col2:
                item2 = results[idx + 1]
                with st.container(border=True):
                    st.image(item2['thumbnail'], width=150)
                    st.write(f"**{item2['title']}**")
                    st.write(f"🏪 ร้านค้า: **{item2['source']}**")
                    st.markdown(f"🏷️ ราคาจริง: <span class='product-price'>{item2['price']}</span>", unsafe_allow_html=True)
                    st.markdown(f"[👉 กดตรงนี้เพื่อไปยังหน้าร้านค้า]({item2['link']})")
                    
                    if st.button(f"❤️ เล็งรายการนี้", key=f"btn_{idx+1}"):
                        st.session_state.wishlist.append(item2)
                        st.toast("บันทึกเข้ารายการเรียบร้อย!", icon="🎉")
                        send_line_alert(item2)

# 3. Wishlist
st.divider()
st.subheader("📋 3️⃣ รายการสินค้าที่คุณกดบันทึกไว้")
if st.session_state.wishlist:
    for idx, wish in enumerate(st.session_state.wishlist):
        st.write(f"**{idx+1}. {wish['title']}** — **{wish['price']}** (ร้านค้า: {wish['source']})")
else:
    st.write("ยังไม่มีรายการที่เล็งไว้")
