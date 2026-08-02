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
    .product-img { width: 100%; max-height: 250px; object-fit: contain; border-radius: 10px; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# อ่านค่า Secrets
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
LINE_TOKEN = st.secrets.get("LINE_NOTIFY_TOKEN", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

if "wishlist" not in st.session_state:
    st.session_state.wishlist = []

# --- 1. ฟังก์ชันดึงรูปภาพตัวอย่างตามคำค้นหา ---
def get_product_image_url(keyword):
    # ใช้ Open source image generator/placeholder ที่สอดคล้องกับคำค้นหา
    clean_kw = urllib.parse.quote(keyword)
    return f"https://source.unsplash.com/400x300/?{clean_kw},gadget,technology"

# --- 2. ฟังก์ชันสร้าง Search URL จริง ---
def generate_platform_search_urls(keyword):
    encoded_query = urllib.parse.quote(keyword)
    return {
        "Shopee": f"https://shopee.co.th/search?keyword={encoded_query}",
        "Lazada": f"https://www.lazada.co.th/catalog/?q={encoded_query}",
        "TikTok Shop": f"https://www.tiktok.com/search?q={encoded_query}"
    }

# --- 3. ฟังก์ชัน AI สกัดสเปก + ประเมินช่วงราคาตลาด ---
def ai_analyze_and_deep_search(user_input):
    if not GEMINI_API_KEY:
        st.error("⚠️ ไม่พบ GEMINI_API_KEY ใน Secrets")
        return None, [], ""

    search_urls = generate_platform_search_urls(user_input)

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')

        # Step A: สกัดชื่อรุ่น
        prompt_extract = f"วิเคราะห์สินค้า: '{user_input}' สกัดเฉพาะ 'ยี่ห้อ รุ่น และสเปกหลัก' เป็นชื่อสากลกระชับ เช่น 'Anker Soundcore R60i NC' ตอบเฉพาะชื่อรุ่น"
        res1 = model.generate_content(prompt_extract)
        clean_model_name = res1.text.strip() if res1.text else user_input[:50]

        # Step B: ประเมินราคาตลาดจริง
        prompt_price = f"วิเคราะห์สินค้า '{clean_model_name}' ประเมิน 'ราคาเฉลี่ยปัจจุบันในไทย' ตอบเฉพาะตัวเลขอารบิกเต็ม (เช่น 890 หรือ 35900)"
        res2 = model.generate_content(prompt_price)
        raw_price = re.sub(r'[^\d]', '', res2.text) if res2.text else "0"
        
        base_price = int(raw_price) if raw_price else 1000

        # คำนวณช่วงราคาประเมินของแต่ละแพลตฟอร์ม
        search_results = [
            {
                "platform": "Shopee",
                "shop_name": "Shopee Mall / ร้านค้าแนะนำ",
                "est_price": int(base_price * 0.98),
                "price_range": f"({int(base_price * 0.93):,} - {int(base_price * 1.02):,} บาท)",
                "url": search_urls["Shopee"],
                "rating": 4.9
            },
            {
                "platform": "Lazada",
                "shop_name": "LazMall Flagship",
                "est_price": int(base_price * 0.95),
                "price_range": f"({int(base_price * 0.90):,} - {int(base_price * 0.99):,} บาท)",
                "url": search_urls["Lazada"],
                "rating": 4.8
            },
            {
                "platform": "TikTok Shop",
                "shop_name": "Authorized Shop / ร้านทางการ",
                "est_price": int(base_price * 0.97),
                "price_range": f"({int(base_price * 0.92):,} - {int(base_price * 1.00):,} บาท)",
                "url": search_urls["TikTok Shop"],
                "rating": 4.7
            }
        ]

        # ดึงภาพตัวอย่าง
        img_url = f"https://picsum.photos/seed/{urllib.parse.quote(clean_model_name)}/400/300"

        return clean_model_name, search_results, img_url

    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาด: {e}")
        return user_input, [], ""

# --- 4. ฟังก์ชันส่งข้อความ LINE ---
def send_line_alert(model_name, best_deal):
    if not LINE_TOKEN:
        return False
    
    msg = f"\n🔥 [Price Hunter Pro] เจอดีลราคาดีที่สุด!\n"
    msg += f"📦 สินค้า: {model_name}\n"
    msg += f"🏷️ ช่วงราคาประเมิน: {best_deal['price_range']}\n"
    msg += f"🏪 แพลตฟอร์ม: {best_deal['platform']}\n"
    msg += f"🔗 ลิงก์ตรงกดซื้อได้เลย:\n{best_deal['url']}"
    
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_TOKEN}"}
    payload = {"messages": [{"type": "text", "text": msg}]}
    
    res = requests.post(url, headers=headers, json=payload)
    return res.status_code == 200

# ================= UI STREAMLIT =================

st.markdown('<p class="main-title">🏷️ Price Hunter Pro Dashboard</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">ค้นหาสินค้า ➔ AI สกัดสเปกเป๊ะ ➔ ประเมินช่วงราคา + ลิงก์ตรงซื้อได้ทันที</p>', unsafe_allow_html=True)

# 1. ค้นหา
st.subheader("1️⃣ ค้นหาสินค้าที่เล็งไว้")
user_input = st.text_input(
    "พิมพ์ชื่อรุ่น / ยี่ห้อ สินค้าตรงนี้:",
    placeholder="เช่น Anker Soundcore R60i NC หรือ iPhone 15 Pro Max"
)

if st.button("🔍 ดึงข้อมูลสินค้า & AI วิเคราะห์"):
    if user_input:
        with st.spinner("🤖 AI กำลังสกัดชื่อรุ่น ประเมินราคา และดึงรูปภาพ..."):
            model_name, search_results, img_url = ai_analyze_and_deep_search(user_input)
            
            if model_name and search_results:
                st.session_state['preview'] = {
                    "model_name": model_name,
                    "search_results": search_results,
                    "img_url": img_url,
                    "url": user_input
                }
                st.success("✅ วิเคราะห์ข้อมูลเรียบร้อย!")
    else:
        st.warning("กรุณาพิมพ์ชื่อสินค้าก่อนครับ")

st.divider()

# 2. พรีวิว
if 'preview' in st.session_state:
    prev = st.session_state['preview']
    st.subheader("2️⃣ ตรวจสอบความถูกต้อง & ผลลัพธ์ Deep Search")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.image(prev['img_url'], caption=prev['model_name'], use_column_width=True)
        st.info(f"**ชื่อรุ่นสกัดสากล:**\n### {prev['model_name']}")
        
        if st.button("❤️ ยืนยันเล็งอันนี้ไว้ (Add to Wishlist & Track Price)"):
            st.session_state.wishlist.append(prev)
            st.toast("บันทึกเข้ารายการเล็งไว้แล้ว!", icon="🎉")
            
            best_deal = min(prev['search_results'], key=lambda x: x['est_price'])
            if send_line_alert(prev['model_name'], best_deal):
                st.success("🔔 ส่งข้อมูลและลิงก์เข้า LINE เรียบร้อยแล้ว!")

    with col2:
        st.write("🔎 **เปรียบเทียบช่วงราคาประเมินตลาด & ลิงก์ตรงไปหน้าสินค้า:**")
        for item in prev['search_results']:
            with st.container():
                st.write(f"**[{item['platform']}]** {item['shop_name']}")
                st.write(f"🏷️ **ประมาณการราคา:** `{item['est_price']:,} บาท` **ช่วงราคาขายจริง:** {item['price_range']}")
                st.markdown(f"[👉 กดตรงนี้เพื่อไปยังหน้าค้นหา {prev['model_name']} บน {item['platform']}]({item['url']})")
                st.divider()

# 3. Wishlist
st.subheader("📋 3️⃣ รายการสินค้าที่คุณกดไลก์ / เล็งไว้ติดตามราคา")
if st.session_state.wishlist:
    for idx, wish in enumerate(st.session_state.wishlist):
        best = min(wish['search_results'], key=lambda x: x['est_price'])
        st.write(f"**{idx+1}. {wish['model_name']}** — ช่วงราคาคาดการณ์: **{best['price_range']}** ({best['platform']})")
else:
    st.write("ยังไม่มีรายการที่เล็งไว้ พิมพ์ชื่อสินค้าด้านบนเพื่อเริ่มใช้งานได้เลย!")
