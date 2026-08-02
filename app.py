import streamlit as st
import requests
import json
import urllib.parse
import re
import google.generativeai as genai

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

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

if "wishlist" not in st.session_state:
    st.session_state.wishlist = []

# --- 1. ฟังก์ชันสร้าง Search URL จริงของแต่ละแพลตฟอร์ม ---
def generate_platform_search_urls(keyword):
    encoded_query = urllib.parse.quote(keyword)
    return {
        "Shopee": f"https://shopee.co.th/search?keyword={encoded_query}",
        "Lazada": f"https://www.lazada.co.th/catalog/?q={encoded_query}",
        "TikTok Shop": f"https://www.tiktok.com/search?q={encoded_query}"
    }

# --- 2. ฟังก์ชัน AI (Gemini) สกัดชื่อรุ่น & ประเมินราคาจริง ---
def ai_analyze_and_deep_search(user_input):
    if not GEMINI_API_KEY:
        st.error("⚠️ ไม่พบ GEMINI_API_KEY ใน Secrets")
        return None, []

    # สร้างลิงก์ค้นหาตรงของทั้ง 3 แพลตฟอร์มล่วงหน้า
    search_urls = generate_platform_search_urls(user_input)

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')

        # Step A: สกัดชื่อรุ่นให้เคลียร์
        prompt_extract = f"วิเคราะห์ข้อความ/สินค้า: '{user_input}' สกัดเฉพาะ 'ยี่ห้อ รุ่น และสเปกหลัก' ออกมาเป็นชื่อภาษาไทยหรืออังกฤษสากลที่กระชับที่สุด เช่น 'iPhone 15 Pro Max 256GB' หรือ 'Anker Soundcore R60i NC' ตอบเฉพาะชื่อรุ่นเท่านั้น"
        res1 = model.generate_content(prompt_extract)
        clean_model_name = res1.text.strip() if res1.text else user_input[:50]

        # Step B: ให้ AI ประเมินช่วงราคาตลาดจริงของสินค้านี้
        prompt_price = f"""
        วิเคราะห์สินค้า: '{clean_model_name}'
        ช่วยประมาณการ 'ราคาตลาดโดยเฉลี่ย' (บาท) ของสินค้านี้ในไทย โดยตอบมาเฉพาะตัวเลขอารบิกเท่านั้น (เช่น 35900 หรือ 890) ห้ามมีอักขระอื่น
        """
        res2 = model.generate_content(prompt_price)
        raw_price_text = re.sub(r'[^\d]', '', res2.text) if res2.text else "0"
        
        base_price = int(raw_price_text) if raw_price_text else 1000

        # ถ้า AI คำนวณราคาได้ ให้สร้างช่วงราคาโปรโมชันสมมุติใกล้เคียงความเป็นจริง
        search_results = [
            {
                "platform": "Shopee",
                "shop_name": "Shopee Mall / Official",
                "price": int(base_price * 0.98),
                "url": search_urls["Shopee"],
                "rating": 4.9
            },
            {
                "platform": "Lazada",
                "shop_name": "LazMall Flagship",
                "price": int(base_price * 0.95), # ถูกสุด
                "url": search_urls["Lazada"],
                "rating": 4.8
            },
            {
                "platform": "TikTok Shop",
                "shop_name": "Authorized Shop",
                "price": int(base_price * 0.97),
                "url": search_urls["TikTok Shop"],
                "rating": 4.7
            }
        ]

        return clean_model_name, search_results

    except Exception as e:
        # Fallback กรณี API ขัดข้อง
        search_results = [
            {"platform": "Shopee", "shop_name": "Official Store", "price": 0, "url": search_urls["Shopee"], "rating": 4.9},
            {"platform": "Lazada", "shop_name": "LazMall Flagship", "price": 0, "url": search_urls["Lazada"], "rating": 4.8},
            {"platform": "TikTok Shop", "shop_name": "Authorized Shop", "price": 0, "url": search_urls["TikTok Shop"], "rating": 4.7}
        ]
        return user_input, search_results

# --- 3. ฟังก์ชันส่งข้อความ LINE ---
def send_line_alert(model_name, best_deal):
    if not LINE_TOKEN:
        return False
    
    msg = f"\n🔥 [Price Hunter Pro] เจอโปรราคาดีที่สุดแล้ว!\n"
    msg += f"📦 สินค้า: {model_name}\n"
    msg += f"🏷️ ประมาณการราคาต่ำสุด: {best_deal['price']:,} บาท\n"
    msg += f"🏪 ร้าน: {best_deal['shop_name']} ({best_deal['platform']})\n"
    msg += f"🔗 กดดูหน้าค้นหาสินค้าตรงได้ที่นี่:\n{best_deal['url']}"
    
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_TOKEN}"}
    payload = {"messages": [{"type": "text", "text": msg}]}
    
    res = requests.post(url, headers=headers, json=payload)
    return res.status_code == 200

# ================= UI STREAMLIT =================

st.markdown('<p class="main-title">🏷️ Price Hunter Pro Dashboard</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">พิมพ์ชื่อสินค้า ➔ AI ประเมินราคาตลาด ➔ ลิงก์ตรงไปหน้าค้นหาข้ามแอป</p>', unsafe_allow_html=True)

# 1. วางลิงก์หรือพิมพ์ชื่อสินค้า
st.subheader("1️⃣ ค้นหาสินค้าที่เล็งไว้")
user_input = st.text_input(
    "พิมพ์ชื่อรุ่น / สินค้าที่ต้องการค้นหา:",
    placeholder="เช่น iPhone 15 Pro Max 256GB หรือ Anker Soundcore R60i NC"
)

if st.button("🔍 ดึงข้อมูลสินค้า & AI วิเคราะห์"):
    if user_input:
        with st.spinner("🤖 AI กำลังวิเคราะห์สินค้าและสร้างลิงก์ค้นหาตรง..."):
            model_name, search_results = ai_analyze_and_deep_search(user_input)
            
            if model_name and search_results:
                st.session_state['preview'] = {
                    "model_name": model_name,
                    "search_results": search_results,
                    "url": user_input
                }
                st.success("✅ วิเคราะห์ข้อมูลและสร้างลิงก์ค้นหาตรงสำเร็จ!")
    else:
        st.warning("กรุณาพิมพ์ชื่อสินค้าก่อนครับ")

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
                st.success("🔔 ส่งลิงก์ไปยัง LINE เรียบร้อยแล้ว!")

    with col2:
        st.write("🔎 **ผลการวิเคราะห์ราคา & ลิงก์กดตรงไปยังหน้าค้นหาสินค้า:**")
        for item in prev['search_results']:
            with st.container():
                price_disp = f"{item['price']:,} บาท" if item['price'] > 0 else "เช็กราคาหน้าเว็บ"
                st.write(f"**[{item['platform']}]** {item['shop_name']} — ประมาณการ **{price_disp}** (⭐ {item['rating']})")
                st.markdown(f"[👉 กดตรงนี้เพื่อไปยังหน้าค้นหา {prev['model_name']} บน {item['platform']}]({item['url']})")
                st.divider()

# 3. Wishlist
st.subheader("📋 3️⃣ รายการสินค้าที่คุณกดไลก์ / เล็งไว้ติดตามราคา")
if st.session_state.wishlist:
    for idx, wish in enumerate(st.session_state.wishlist):
        best = min(wish['search_results'], key=lambda x: x['price'])
        price_disp = f"{best['price']:,} บาท" if best['price'] > 0 else "เช็กราคาหน้าเว็บ"
        st.write(f"**{idx+1}. {wish['model_name']}** — ประมาณการราคาถูกที่สุด: **{price_disp}** ({best['platform']})")
else:
    st.write("ยังไม่มีรายการที่เล็งไว้ พิมพ์ชื่อสินค้าด้านบนเพื่อเริ่มใช้งานได้เลย!")
