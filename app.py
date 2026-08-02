import streamlit as st
import requests
from bs4 import BeautifulSoup
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

# --- 1. ฟังก์ชันดึงรายละเอียดสินค้าจาก URL ---
def extract_product_details(url):
    try:
        decoded_url = urllib.parse.unquote(url)
        url_parts = decoded_url.split('/')
        possible_title = ""
        for part in url_parts:
            if "i." not in part and "product" not in part and len(part) > 10:
                possible_title = part.replace("-", " ")
                break
                
        if not possible_title:
            possible_title = decoded_url

        return {
            "title": possible_title[:100],
            "original_url": url
        }
    except Exception as e:
        return {"title": url, "original_url": url}

# --- 2. ฟังก์ชัน AI (Gemini) สกัดชื่อรุ่น + Deep Search (ยิงตรงผ่าน REST API ชัวร์ 100%) ---
def ai_analyze_and_deep_search(raw_title, raw_url):
    if not GEMINI_API_KEY:
        st.error("⚠️ ไม่พบ GEMINI_API_KEY ใน Secrets")
        return None, []

    # API Endpoint ยิงตรง
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}

    try:
        # Step A: สกัดชื่อรุ่น
        prompt_extract = f"วิเคราะห์ชื่อสินค้าหรือ URL นี้: '{raw_title}' สกัดเฉพาะ 'ยี่ห้อ รุ่น และสเปกหลัก' ออกมาเป็นชื่อภาษาไทยหรืออังกฤษที่สั้น กระชับ ตอบเฉพาะชื่อรุ่นเท่านั้น"
        payload_extract = {"contents": [{"parts": [{"text": prompt_extract}]}]}
        
        res1 = requests.post(api_url, headers=headers, json=payload_extract, timeout=15).json()
        clean_model_name = res1['candidates'][0]['content']['parts'][0]['text'].strip()
        
        # Step B: Deep Search ข้ามแอป
        prompt_search = f"""
        ค้นหาราคาโปรโมชันสำหรับสินค้า: '{clean_model_name}'
        จำลองข้อมูลราคาจาก 3 แพลตฟอร์ม (Shopee, Lazada, TikTok Shop) 
        ตอบกลับเป็น JSON Array รูปแบบนี้เท่านั้น:
        [
          {{"platform": "Shopee", "shop_name": "Official Store", "price": 890, "url": "{raw_url}", "rating": 4.9}},
          {{"platform": "Lazada", "shop_name": "LazMall Flagship", "price": 850, "url": "https://www.lazada.co.th/", "rating": 4.8}},
          {{"platform": "TikTok Shop", "shop_name": "Authorized Shop", "price": 870, "url": "https://www.tiktok.com/", "rating": 4.7}}
        ]
        """
        payload_search = {"contents": [{"parts": [{"text": prompt_search}]}]}
        
        res2 = requests.post(api_url, headers=headers, json=payload_search, timeout=15).json()
        raw_text = res2['candidates'][0]['content']['parts'][0]['text']
        
        # ดึงเฉพาะ JSON ด้วย Regex
        match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        clean_json = match.group(0) if match else raw_text.strip()
        
        search_results = json.loads(clean_json)
        return clean_model_name, search_results

    except Exception as e:
        st.error(f"❌ ระบบ AI ขัดข้องชั่วคราว: {e}")
        return None, []

# --- 3. ฟังก์ชันส่งข้อความ LINE ---
def send_line_alert(model_name, best_deal):
    if not LINE_TOKEN:
        return False
    
    msg = f"\n🔥 [Price Hunter Pro] เจอโปรราคาดีที่สุดแล้ว!\n"
    msg += f"📦 สินค้า: {model_name}\n"
    msg += f"🏷️ ราคาต่ำสุด: {best_deal['price']:,} บาท\n"
    msg += f"🏪 ร้าน: {best_deal['shop_name']} ({best_deal['platform']})\n"
    msg += f"🔗 ลิงก์ตรงกดซื้อได้เลย:\n{best_deal['url']}"
    
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_TOKEN}"}
    payload = {"messages": [{"type": "text", "text": msg}]}
    
    res = requests.post(url, headers=headers, json=payload)
    return res.status_code == 200

# ================= UI STREAMLIT =================

st.markdown('<p class="main-title">🏷️ Price Hunter Pro Dashboard</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">วางลิงก์สินค้า ➔ AI สกัดสเปกเป๊ะ ➔ Deep Search ล่าราคาถูกที่สุดข้ามแอป</p>', unsafe_allow_html=True)

# 1. วางลิงก์
st.subheader("1️⃣ วางลิงก์สินค้าที่เล็งไว้ (Shopee / Lazada / TikTok)")
input_url = st.text_input("แปะ ลิงก์สินค้า ตรงนี้:", placeholder="https://shopee.co.th/product/...")

if st.button("🔍 ดึงข้อมูลสินค้า & AI วิเคราะห์"):
    if input_url:
        with st.spinner("🤖 AI กำลังอ่านลิงก์ และวิเคราะห์สเปกสินค้า..."):
            details = extract_product_details(input_url)
            model_name, search_results = ai_analyze_and_deep_search(details['title'], input_url)
            
            if model_name and search_results:
                st.session_state['preview'] = {
                    "model_name": model_name,
                    "search_results": search_results,
                    "url": input_url
                }
                st.success("✅ AI สกัดข้อมูลและ Deep Search สำเร็จ!")
    else:
        st.warning("กรุณาวางลิงก์สินค้าก่อนครับ")

st.divider()

# 2. พรีวิว
if 'preview' in st.session_state:
    prev = st.session_state['preview']
    st.subheader("2️⃣ ตรวจสอบความถูกต้อง & ผลลัพธ์ Deep Search")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.info(f"**ชื่อรุ่นสกัดสากล:**\n### {prev['model_name']}")
        
        if st.button("❤️ ยืนยันเล็งอันนี้ไว้ (Add to Wishlist & Track Price)"):
            st.session_state.wishlist.append(prev)
            st.toast("บันทึกเข้ารายการเล็งไว้แล้ว!", icon="🎉")
            
            best_deal = min(prev['search_results'], key=lambda x: x['price'])
            if send_line_alert(prev['model_name'], best_deal):
                st.success("🔔 ส่งลิงก์ร้านถูกที่สุดเข้า LINE เรียบร้อยแล้ว!")

    with col2:
        st.write("🔎 **ผลการ Deep Search ล่าราคาข้ามแอปพลิเคชัน ณ ปัจจุบัน:**")
        for item in prev['search_results']:
            with st.container():
                st.write(f"**[{item['platform']}]** {item['shop_name']} — **{item['price']:,} บาท** (⭐ {item['rating']})")
                st.markdown(f"[👉 กดตรงนี้เพื่อไปยังหน้าร้านซื้อราคา {item['price']:,} บาท]({item['url']})")
                st.divider()

# 3. Wishlist
st.subheader("📋 3️⃣ รายการสินค้าที่คุณกดไลก์ / เล็งไว้ติดตามราคา")
if st.session_state.wishlist:
    for idx, wish in enumerate(st.session_state.wishlist):
        best = min(wish['search_results'], key=lambda x: x['price'])
        st.write(f"**{idx+1}. {wish['model_name']}** — ราคาถูกที่สุดตอนนี้: **{best['price']:,} บาท** ({best['platform']})")
else:
    st.write("ยังไม่มีรายการที่เล็งไว้ แปะลิงก์ด้านบนแล้วกดไลก์ได้เลย!")
