import streamlit as st
import requests
import json
import urllib.parse
import re

# ตั้งค่าหน้าตาเว็บ
st.set_page_config(page_title="Price Hunter Pro", page_icon="🏷️", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 2.2rem; font-weight: bold; color: #ff4b4b; text-align: center; }
    .sub-title { font-size: 1.1rem; text-align: center; color: #666; margin-bottom: 2rem; }
    </style>
""", unsafe_allow_html=True)

# อ่านค่า Secrets
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
LINE_TOKEN = st.secrets.get("LINE_NOTIFY_TOKEN", "")

if "wishlist" not in st.session_state:
    st.session_state.wishlist = []

# --- 1. ฟังก์ชันสร้าง Search URL ตรง ---
def generate_platform_search_urls(keyword):
    encoded_query = urllib.parse.quote(keyword)
    return {
        "Shopee": f"https://shopee.co.th/search?keyword={encoded_query}",
        "Lazada": f"https://www.lazada.co.th/catalog/?q={encoded_query}",
        "TikTok Shop": f"https://www.tiktok.com/search?q={encoded_query}"
    }

# --- 2. ฟังก์ชันเรียก Gemini API ยิงตรงผ่าน REST (แก้ปัญหา 404 ถาวร) ---
def ai_analyze_product(user_input):
    if not GEMINI_API_KEY:
        st.error("⚠️ ไม่พบ GEMINI_API_KEY ใน Secrets")
        return user_input, "ไม่สามารถประเมินราคาได้"

    # ใช้ Endpoint v1beta ตัวใหม่ล่าสุด
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    prompt = f"""
    วิเคราะห์ข้อความ/ชื่อสินค้านี้: '{user_input}'
    1. สกัดเฉพาะ 'ยี่ห้อ รุ่น และสเปกหลัก' เป็นภาษาไทยหรืออังกฤษสากลที่กระชับ
    2. ประเมินช่วงราคาตลาดในไทย ณ ปัจจุบัน
    
    ตอบกลับเป็น JSON รูปแบบนี้เท่านั้น:
    {{
        "clean_name": "ชื่อรุ่นที่สกัดแล้ว",
        "price_range": "ช่วงราคาประเมิน เช่น 35,000 - 38,000 บาท"
    }}
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        res_data = response.json()
        
        if 'candidates' in res_data and res_data['candidates']:
            raw_text = res_data['candidates'][0]['content']['parts'][0]['text']
            data = json.loads(raw_text)
            return data.get("clean_name", user_input), data.get("price_range", "เช็กราคาจริงหน้าเว็บ")
        else:
            return user_input, "เช็กราคาจริงหน้าเว็บ"
    except Exception as e:
        return user_input, "เช็กราคาจริงหน้าเว็บ"

# --- 3. ฟังก์ชันส่ง LINE Notify ---
def send_line_alert(model_name, search_urls, price_range):
    if not LINE_TOKEN:
        return False
    
    msg = f"\n📌 [Price Hunter Pro] บันทึกสินค้าที่คุณเล็งไว้แล้ว!\n"
    msg += f"📦 สินค้า: {model_name}\n"
    msg += f"🏷️ ช่วงราคาประเมิน: {price_range}\n\n"
    msg += f"🔗 กดเช็กราคาโปรโมชันจริงล่าสุดได้ที่นี่:\n"
    msg += f"• Shopee: {search_urls['Shopee']}\n"
    msg += f"• Lazada: {search_urls['Lazada']}\n"
    msg += f"• TikTok: {search_urls['TikTok Shop']}"
    
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_TOKEN}"}
    payload = {"messages": [{"type": "text", "text": msg}]}
    
    res = requests.post(url, headers=headers, json=payload)
    return res.status_code == 200

# ================= UI STREAMLIT =================

st.markdown('<p class="main-title">🏷️ Price Hunter Pro Dashboard</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">ค้นหาสินค้า ➔ AI สกัดสเปกเป๊ะ ➔ สร้างลิงก์ค้นหาตรงข้ามแอปพลิเคชัน</p>', unsafe_allow_html=True)

# 1. ค้นหา
st.subheader("1️⃣ ค้นหาสินค้าที่เล็งไว้")
user_input = st.text_input(
    "พิมพ์ชื่อรุ่น / ยี่ห้อ สินค้าตรงนี้:",
    placeholder="เช่น iPhone 17 Pro Max หรือ Anker Soundcore R60i NC"
)

if st.button("🔍 ดึงข้อมูลสินค้า & AI วิเคราะห์"):
    if user_input:
        with st.spinner("🤖 AI กำลังวิเคราะห์สินค้า..."):
            model_name, price_range = ai_analyze_product(user_input)
            search_urls = generate_platform_search_urls(model_name)
            
            st.session_state['preview'] = {
                "model_name": model_name,
                "price_range": price_range,
                "search_urls": search_urls
            }
            st.success("✅ AI สกัดข้อมูลและสร้างลิงก์สำเร็จ!")
    else:
        st.warning("กรุณาพิมพ์ชื่อสินค้าก่อนครับ")

st.divider()

# 2. พรีวิว
if 'preview' in st.session_state:
    prev = st.session_state['preview']
    st.subheader("2️⃣ ตรวจสอบความถูกต้อง & ทางไปเช็กราคา")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.info(f"**ชื่อรุ่นสกัดสากล:**\n### {prev['model_name']}")
        st.write(f"🏷️ **ช่วงราคาประเมินตลาด:** {prev['price_range']}")
        
        if st.button("❤️ เล็งอันนี้ไว้ (ส่งลิงก์เข้า LINE เพื่อตามต่อ)"):
            st.session_state.wishlist.append(prev)
            st.toast("บันทึกเข้ารายการเล็งไว้แล้ว!", icon="🎉")
            
            if send_line_alert(prev['model_name'], prev['search_urls'], prev['price_range']):
                st.success("🔔 ส่งลิงก์ค้นหาข้ามแอปเข้า LINE เรียบร้อยแล้ว!")
            else:
                st.error("⚠️ ไม่สามารถส่ง LINE ได้ กรุณาเช็ก LINE_NOTIFY_TOKEN")

    with col2:
        st.write("🔎 **ลิงก์ตรงไปหน้าค้นหาราคาจริง ณ ปัจจุบัน:**")
        for platform, url_link in prev['search_urls'].items():
            with st.container():
                st.write(f"**[{platform}]**")
                st.markdown(f"[👉 กดตรงนี้เพื่อดูราคาจริงบน {platform}]({url_link})")
                st.divider()

# 3. Wishlist
st.subheader("📋 3️⃣ รายการสินค้าที่คุณเล็งไว้")
if st.session_state.wishlist:
    for idx, wish in enumerate(st.session_state.wishlist):
        st.write(f"**{idx+1}. {wish['model_name']}** ({wish['price_range']})")
else:
    st.write("ยังไม่มีรายการที่เล็งไว้ พิมพ์ชื่อสินค้าด้านบนเพื่อเริ่มใช้งานได้เลย!")
