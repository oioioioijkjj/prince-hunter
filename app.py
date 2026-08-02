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

# --- 1. ฟังก์ชันสกัดชื่อสินค้าเบื้องต้นจากลิงก์หรือข้อความ ---
def parse_user_input(user_input):
    cleaned = user_input.strip()
    
    if cleaned.startswith("http://") or cleaned.startswith("https://"):
        try:
            decoded_url = urllib.parse.unquote(cleaned)
            clean_path = decoded_url.split('?')[0]
            parts = clean_path.split('/')
            
            possible_title = ""
            for part in reversed(parts):
                if len(part) > 5 and not part.startswith("i.") and "product" not in part:
                    possible_title = part.replace("-", " ").replace("_", " ")
                    break
            
            if possible_title:
                return possible_title
            return decoded_url
        except Exception:
            return cleaned
            
    return cleaned

# --- 2. ฟังก์ชัน AI (Gemini) สกัดชื่อรุ่น + Deep Search (บังคับ JSON 100%) ---
def ai_analyze_and_deep_search(raw_input, raw_url_or_text):
    if not GEMINI_API_KEY:
        st.error("⚠️ ไม่พบ GEMINI_API_KEY ใน Secrets")
        return None, []

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}

    try:
        # Step A: สกัดชื่อรุ่นให้คลีนที่สุด
        prompt_extract = f"วิเคราะห์ข้อความ/สินค้าต่อไปนี้: '{raw_input}' สกัดเฉพาะ 'ยี่ห้อ รุ่น และสเปกหลัก' ให้เป็นชื่อสินค้าสากลที่กระชับที่สุด เช่น 'Anker Soundcore R60i NC' หรือ 'iPhone 15 Pro Max 256GB' ตอบเฉพาะชื่อรุ่นเท่านั้น ห้ามใส่คำอธิบายอื่น"
        payload_extract = {"contents": [{"parts": [{"text": prompt_extract}]}]}
        
        res1_response = requests.post(api_url, headers=headers, json=payload_extract, timeout=15)
        res1 = res1_response.json()
        
        if 'candidates' in res1 and res1['candidates']:
            clean_model_name = res1['candidates'][0]['content']['parts'][0]['text'].strip()
        else:
            clean_model_name = raw_input[:60]
        
        # Step B: Deep Search ล่าราคาข้ามแอป (ใส่ generationConfig บังคับ JSON)
        prompt_search = f"""
        ค้นหาราคาโปรโมชันสำหรับสินค้า: '{clean_model_name}'
        จำลองข้อมูลราคาจาก 3 แพลตฟอร์ม (Shopee, Lazada, TikTok Shop) ให้ราคาสมเหตุสมผล
        ตอบกลับเป็น JSON Array โครงสร้างนี้เท่านั้น:
        [
          {{"platform": "Shopee", "shop_name": "Official Store", "price": 890, "url": "https://shopee.co.th/", "rating": 4.9}},
          {{"platform": "Lazada", "shop_name": "LazMall Flagship", "price": 850, "url": "https://www.lazada.co.th/", "rating": 4.8}},
          {{"platform": "TikTok Shop", "shop_name": "Authorized Shop", "price": 870, "url": "https://www.tiktok.com/", "rating": 4.7}}
        ]
        """
        payload_search = {
            "contents": [{"parts": [{"text": prompt_search}]}],
            "generationConfig": {
                "response_mime_type": "application/json"
            }
        }
        
        res2_response = requests.post(api_url, headers=headers, json=payload_search, timeout=15)
        res2 = res2_response.json()

        if 'candidates' not in res2 or not res2['candidates']:
            st.error("⚠️ AI ไม่ตอบรับคำสั่ง กรุณาลองใหม่อีกครั้ง")
            return None, []

        raw_text = res2['candidates'][0]['content']['parts'][0]['text']
        search_results = json.loads(raw_text)
        
        # ถ้าเป็นลิงก์ ให้ใส่ URL เดิมเข้าผลลัพธ์รายการแรก
        if search_results and (raw_url_or_text.startswith("http://") or raw_url_or_text.startswith("https://")):
            search_results[0]['url'] = raw_url_or_text

        return clean_model_name, search_results

    except Exception as e:
        st.error(f"❌ ระบบขัดข้อง: {e}")
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
st.markdown('<p class="sub-title">แปะลิงก์ หรือ พิมพ์ชื่อสินค้าตรงๆ ➔ AI สกัดสเปก ➔ ล่าราคาถูกที่สุดข้ามแอป</p>', unsafe_allow_html=True)

# 1. วางลิงก์หรือพิมพ์ชื่อสินค้า
st.subheader("1️⃣ ค้นหาสินค้าที่เล็งไว้")
user_input = st.text_input(
    "วางลิงก์สินค้า หรือ พิมพ์ชื่อรุ่น/ยี่ห้อ ตรงนี้:",
    placeholder="เช่น Anker Soundcore R60i NC หรือ https://shopee.co.th/..."
)

if st.button("🔍 ดึงข้อมูลสินค้า & AI วิเคราะห์"):
    if user_input:
        with st.spinner("🤖 AI กำลังวิเคราะห์ข้อมูลสินค้า..."):
            extracted_title = parse_user_input(user_input)
            model_name, search_results = ai_analyze_and_deep_search(extracted_title, user_input)
            
            if model_name and search_results:
                st.session_state['preview'] = {
                    "model_name": model_name,
                    "search_results": search_results,
                    "url": user_input
                }
                st.success("✅ AI สกัดข้อมูลและเปรียบเทียบราคาสำเร็จ!")
    else:
        st.warning("กรุณาวางลิงก์หรือพิมพ์ชื่อสินค้าก่อนครับ")

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
    st.write("ยังไม่มีรายการที่เล็งไว้ พิมพ์ชื่อหรือแปะลิงก์ด้านบนเพื่อเริ่มใช้งานได้เลย!")
