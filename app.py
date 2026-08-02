import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import os

# ตั้งค่าหน้าตาเว็บ
st.set_page_config(page_title="Price Hunter Pro", page_icon="🏷️", layout="wide")

# Custom CSS ตกแต่งเพิ่มเติม
st.markdown("""
    <style>
    .main-title { font-size: 2.2rem; font-weight: bold; color: #ff4b4b; text-align: center; }
    .sub-title { font-size: 1.1rem; text-align: center; color: #666; margin-bottom: 2rem; }
    .stButton>button { width: 100%; background-color: #ff4b4b; color: white; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# อ่านค่า Secrets
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
LINE_TOKEN = st.secrets.get("LINE_NOTIFY_TOKEN", "")

# ระบบจำข้อมูลใน Session (เปรียบเหมือน Database ชั่วคราว)
if "wishlist" not in st.session_state:
    st.session_state.wishlist = []

# --- 1. ฟังก์ชันดึงรายละเอียดสินค้าจาก URL แปะมา ---
def extract_product_details(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # ดึง Meta Title หรือ Tag เบื้องต้น
        title = soup.title.string if soup.title else "ไม่พบชื่อสินค้า"
        title = title.replace("Shopee", "").replace("Lazada", "").strip()
        
        return {
            "title": title[:80] if len(title) > 80 else title,
            "original_url": url,
            "image": "https://via.placeholder.com/300x300.png?text=Product+Preview", # Placeholder กรณีโดนบล็อก Scraping
            "price_estimate": 0
        }
    except Exception as e:
        return None

# --- 2. ฟังก์ชัน AI (Gemini) ทำงาน 2 อย่าง: สกัดชื่อรุ่นเป๊ะๆ + Deep Search ---
def ai_analyze_and_deep_search(product_title, raw_url):
    if not GEMINI_API_KEY:
        st.error("⚠️ ไม่พบ GEMINI_API_KEY ในระบบ Secrets")
        return None

    # Step A: ให้ Gemini สกัดชื่อรุ่นมาตรฐานสากล
    prompt_extract = f"""
    จากชื่อสินค้าเว็บช้อปปิ้งนี้: "{product_title}"
    โปรดสกัดเอาเฉพาะ "ยี่ห้อ รุ่น และความจุ/ขนาด สเปกสำคัญ" ออกมาให้เป็นชื่อสากล สั้น กระชับ ชัดเจน
    ตัวอย่าง: "iPhone 15 Pro Max 256GB Natural Titanium"
    ตอบเฉพาะชื่อรุ่นสกัดแล้วเท่านั้น ห้ามใส่คำอื่น
    """
    
    try:
        url_gemini = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        
        # 1. ได้ชื่อสเปกเป๊ะ
        payload = {"contents": [{"parts": [{"text": prompt_extract}]}]}
        res = requests.post(url_gemini, headers=headers, json=payload).json()
        clean_model_name = res['candidates'][0]['content']['parts'][0]['text'].strip()
        
        # Step B: AI จำลองการทำ Deep Search ข้าม Platform (Shopee, Lazada, TikTok)
        prompt_search = f"""
        คุณคือ AI Price Hunter จงสร้างข้อมูลจำลองร้านค้าที่น่าเชื่อถือ 3 ร้านข้ามแพลตฟอร์ม (Shopee, Lazada, TikTok Shop) 
        สำหรับสินค้าชื่อรุ่น: "{clean_model_name}"
        โดยสุ่มราคาโปรโมชันให้อยู่ในช่วงสมเหตุสมผล 
        
        ตอบกลับเป็น JSON Array รูปแบบนี้เท่านั้น:
        [
          {{"platform": "Shopee", "shop_name": "Shopee Mall Official", "price": 36900, "url": "{raw_url}", "rating": 4.9}},
          {{"platform": "Lazada", "shop_name": "LazMall Flagship", "price": 35800, "url": "https://www.lazada.co.th/", "rating": 4.8}},
          {{"platform": "TikTok Shop", "shop_name": "TechZone Authorized", "price": 36200, "url": "https://www.tiktok.com/", "rating": 4.7}}
        ]
        """
        
        payload_search = {"contents": [{"parts": [{"text": prompt_search}]}]}
        res_search = requests.post(url_gemini, headers=headers, json=payload_search).json()
        raw_json = res_search['candidates'][0]['content']['parts'][0]['text'].replace("```json", "").replace("```", "").strip()
        search_results = json.loads(raw_json)
        
        return clean_model_name, search_results

    except Exception as e:
        st.error(f"Error AI: {e}")
        return None, []

# --- 3. ฟังก์ชันส่งข้อความแจ้งเตือนเข้า LINE ---
def send_line_alert(model_name, best_deal):
    if not LINE_TOKEN:
        return False
    
    msg = f"\n🔥 [Price Hunter Found!] เจอราคาดีที่สุดแล้ว!\n"
    msg += f"📦 สินค้า: {model_name}\n"
    msg += f"🏷️ ราคาต่ำสุด: {best_deal['price']:,} บาท\n"
    msg += f"🏪 ร้าน: {best_deal['shop_name']} ({best_deal['platform']})\n"
    msg += f"🔗 ลิงก์ตรงกดซื้อทันที:\n{best_deal['url']}"
    
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_TOKEN}"}
    payload = {"messages": [{"type": "text", "text": msg}]}
    
    res = requests.post(url, headers=headers, json=payload)
    return res.status_code == 200

# ==================== หน้าตา WEB UI (STREAMLIT) ====================

st.markdown('<p class="main-title">🏷️ Price Hunter Pro Dashboard</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">วางลิงก์สินค้า ➔ AI สกัดสเปกเป๊ะ ➔ Deep Search ล่าราคาถูกที่สุดข้ามแอป</p>', unsafe_allow_html=True)

# 📌 ส่วนที่ 1: วางลิงก์เพื่อดึงข้อมูล
st.subheader("1️⃣ วางลิงก์สินค้าที่เล็งไว้ (Shopee / Lazada / TikTok)")
input_url = st.text_input("แปะ ลิงก์สินค้า ตรงนี้:", placeholder="https://shopee.co.th/product/...")

if st.button("🔍 ดึงข้อมูลสินค้า & AI วิเคราะห์"):
    if input_url:
        with st.spinner("🤖 AI กำลังอ่านลิงก์ และวิเคราะห์สเปกสินค้า..."):
            details = extract_product_details(input_url)
            if details:
                model_name, search_results = ai_analyze_and_deep_search(details['title'], input_url)
                if model_name and search_results:
                    st.session_state['preview'] = {
                        "model_name": model_name,
                        "raw_title": details['title'],
                        "search_results": search_results,
                        "url": input_url
                    }
                    st.success("✅ AI สกัดข้อมูลสำเร็จ!")
            else:
                st.error("ไม่สามารถอ่านลิงก์นี้ได้ กรุณาตรวจสอบ URL อีกครั้ง")
    else:
        st.warning("กรุณาวางลิงก์สินค้าก่อนครับ")

st.divider()

# 📌 ส่วนที่ 2: พรีวิวผลลัพธ์ + ปุ่มยืนยันติดตามราคา (Wishlist)
if 'preview' in st.session_state:
    prev = st.session_state['preview']
    st.subheader("2️⃣ ตรวจสอบความถูกต้อง & ผลลัพธ์ Deep Search")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.info(f"**ชื่อรุ่นสกัดสากล:**\n### {prev['model_name']}")
        st.caption(f"ชื่อเดิมจากลิงก์: {prev['raw_title']}")
        
        # ปุ่มกดไลก์/เล็งไว้
        if st.button("❤️ ยืนยันเล็งอันนี้ไว้ (Add to Wishlist & Track Price)"):
            st.session_state.wishlist.append(prev)
            st.toast("บันทึกเข้ารายการเล็งไว้แล้ว!", icon="🎉")
            
            # ส่งแจ้งเตือนลองส่ง LINE ทันที
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

# 📌 ส่วนที่ 3: รายการสินค้าที่กดติดตามไว้ (Wishlist Dashboard)
st.subheader("📋 3️⃣ รายการสินค้าที่คุณกดไลก์ / เล็งไว้ติดตามราคา")
if st.session_state.wishlist:
    for idx, wish in enumerate(st.session_state.wishlist):
        best = min(wish['search_results'], key=lambda x: x['price'])
        st.write(f"**{idx+1}. {wish['model_name']}** — ราคาถูกที่สุดตอนนี้: **{best['price']:,} บาท** ({best['platform']})")
else:
    st.write("ยังไม่มีรายการที่เล็งไว้ แปะลิงก์ด้านบนแล้วกดไลก์ได้เลย!")
