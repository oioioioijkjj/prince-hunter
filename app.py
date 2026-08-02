import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
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

# ตั้งค่า Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

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

# --- 2. ฟังก์ชัน AI (Gemini) สกัดชื่อรุ่น + Deep Search ---
def ai_analyze_and_deep_search(raw_title, raw_url):
    if not GEMINI_API_KEY:
        st.error("⚠️ ไม่พบ GEMINI_API_KEY ใน Secrets")
        return None, []

    try:
        # ใช้โมเดลมาตรฐาน gemini-1.5-flash
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Step A: สกัดชื่อรุ่น
        prompt_extract = f"""
        วิเคราะห์ชื่อสินค้าหรือ URL นี้: "{raw_title}"
        โปรดสกัดออกมาเฉพาะ "ยี่ห้อ รุ่น และสเปกหลัก" ให้เป็นชื่อสินค้าภาษาไทยหรืออังกฤษสากลที่สั้นและกระชับที่สุด
        ตัวอย่าง: "ANKER Soundcore R60i NC" หรือ "iPhone 15 Pro Max 256GB"
        ตอบเฉพาะชื่อรุ่นเท่านั้น ห้ามใส่คำอธิบายอื่น
        """
        response_extract = model.generate_content(prompt_extract)
        clean_model_name = response_extract.text.strip()
        
        # Step B: Deep Search ข้ามแอป
        prompt_search = f"""
        คุณคือระบบ Deep Search ค้นหาราคาโปรโมชันสำหรับสินค้า: "{clean_model_name}"
        จงจำลองข้อมูลราคาสินค้านี้จาก 3 แพลตฟอร์ม (Shopee, Lazada, TikTok Shop) โดยให้ราคาอยู่ในช่วงที่สมเหตุสมผล
        
        ตอบกลับเป็น JSON Array โครงสร้างนี้เท่านั้น (ห้ามมีคำอื่น):
        [
          {{"platform": "Shopee", "shop_name": "Official Store", "price": 890, "url": "{raw_url}", "rating": 4.9}},
          {{"platform": "Lazada", "shop_name": "LazMall Flagship", "price": 850, "url": "https://www.lazada.co.th/", "rating": 4.8}},
          {{"platform": "TikTok Shop", "shop_name": "Authorized Shop", "price": 870, "url": "https://www.tiktok.com/", "rating": 4.7}}
        ]
        """
        response_search = model.generate_content(prompt_search)
        clean_json_text = response_search.text.replace("```json", "").replace("
