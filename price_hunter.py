import os
import json
import requests

# -------------------------------------------------------------------
# ฟังก์ชันดึงข้อมูลราคา (จำลองการดึงจาก Shopee / Lazada / TikTok)
# -------------------------------------------------------------------
def fetch_marketplace_data(keyword):
    print(f"🔍 กำลังค้นหาสินค้าคำว่า: '{keyword}'...")
    
    # ข้อมูลจำลองที่บอทหามาได้ (มีทั้งเครื่องจริง เคส และฟิล์มกระจก)
    mock_scraped_data = [
        {"platform": "Lazada", "title": f"Apple {keyword} (256GB) - Natural Titanium เครื่องแท้ประกันศูนย์", "price": 37900, "url": "https://lazada.co.th/item1"},
        {"platform": "Shopee", "title": f"เคสกันกระแทกอย่างดี สำหรับ {keyword} ใส ไม่เหลือง", "price": 290, "url": "https://shopee.co.th/item2"},
        {"platform": "TikTok Shop", "title": f"{keyword} 256GB เครื่อง TH มือ 1", "price": 38500, "url": "https://tiktok.com/item3"},
        {"platform": "Shopee", "title": f"ฟิล์มกระจกโฟกัส กันรอย เต็มจอ {keyword}", "price": 150, "url": "https://shopee.co.th/item4"}
    ]
    return mock_scraped_data


# -------------------------------------------------------------------
# Step 2: ฟังก์ชัน AI Filter (ใช้ Gemini แยกแยะตัวสินค้าจริง)
# -------------------------------------------------------------------
def filter_with_ai(target_item, items_list):
    """
    ใช้ Gemini API เพื่อคัดกรองเฉพาะสินค้าจริง ตัดพวกเคส/ฟิล์ม/อุปกรณ์เสริมออก
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    
    # ถ้ายังไม่ได้ใส่ API Key ให้ใช้วิธี Simple Rule Filter สำรองไปก่อน
    if not api_key:
        print("⚠️ ไม่พบ GEMINI_API_KEY ในระบบ (จะใช้ระบบกรองคำเบื้องต้นแทน)")
        filtered = []
        for item in items_list:
            title_lower = item['title'].lower()
            # ถ้ามีคำว่า เคส หรือ ฟิล์ม ให้ข้ามไป
            if "เคส" not in title_lower and "ฟิล์ม" not in title_lower and "case" not in title_lower:
                filtered.append(item)
        return filtered

    print("🤖 กำลังส่งข้อมูลให้ Gemini AI ช่วยวิเคราะห์และคัดกรองสินค้า...")
    
    # เตรียม Prompt ส่งให้ Gemini
    prompt = f"""
    คุณคือ AI ผู้เชี่ยวชาญด้าน E-commerce 
    เป้าหมายผู้ใช้ต้องการซื้อ: "{target_item}"
    
    โปรดวิเคราะห์รายการสินค้าต่อไปนี้ แล้วตอบกลับเฉพาะรายการที่เป็นตัวเครื่องจริงเท่านั้น (ตัด เคส, ฟิล์ม, อุปกรณ์เสริม, อะแดปเตอร์ ออกทั้งหมด)
    รายการสินค้า:
    {json.dumps(items_list, ensure_ascii=False)}
    
    ส่งผลลัพธ์กลับมาเป็นรูปแบบ JSON Array เฉพาะรายการที่ผ่านการคัดกรองแล้วเท่านั้น ไม่ต้องมีคำอธิบายเพิ่มเติม
    """

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        
        response = requests.post(url, headers=headers, json=payload)
        res_data = response.json()
        
        # แกะข้อมูล JSON จากตอบกลับของ AI
        ai_reply = res_data['candidates'][0]['content']['parts'][0]['text']
        # ลบ markdown code block ออกถ้ามี
        clean_json = ai_reply.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
        
    except Exception as e:
        print(f"❌ AI Analysis Error: {e}")
        # ถ้า AI เกิดข้อผิดพลาด ให้ส่งคืนข้อมูลทั้งหมดไปก่อน
        return items_list


# -------------------------------------------------------------------
# ฟังก์ชันหลัก (Main Hunt Execution)
# -------------------------------------------------------------------
def main():
    target_keyword = "iPhone 15 Pro Max 256GB"
    target_price = 38000
    
    print("=" * 50)
    print(f"🎯 ภารกิจตามล่า: {target_keyword}")
    print(f"💰 ราคาเป้าหมาย: {target_price:,} บาท")
    print("=" * 50)
    
    # 1. ดึงข้อมูล
    raw_items = fetch_marketplace_data(target_keyword)
    print(f"\n📦 พบรายการค้นหาเบื้องต้น {len(raw_items)} รายการ")
    
    # 2. ให้ AI กรอง
    valid_items = filter_with_ai(target_keyword, raw_items)
    print(f"✅ AI คัดกรองเหลือตัวเครื่องจริง: {len(valid_items)} รายการ\n")
    
    # 3. เช็กราคาและแจ้งเตือน
    deals_found = False
    for item in valid_items:
        price = item['price']
        status = "🔥 ถึงราคาเป้าหมายแล้ว!" if price <= target_price else "❌ ราคายังแพงกว่าเป้า"
        print(f"📱 [{item['platform']}] {item['title']}")
        print(f"   💵 ราคา: {price:,} บาท | สถานะ: {status}")
        print(f"   🔗 ลิงก์: {item['url']}\n")
        
        if price <= target_price:
            deals_found = True

    if deals_found:
        print("🔔 [Notification System] เตรียมส่งแจ้งเตือนเข้า LINE...")
        # (เราจะเขียนส่วนส่ง LINE ต่อใน Step ถัดไปครับ)

if __name__ == "__main__":
    main()
