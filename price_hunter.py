import os
import json
import requests

# -------------------------------------------------------------------
# 1. ฟังก์ชันดึงข้อมูลสินค้า (ตัวอย่างแบบครอบคลุม)
# -------------------------------------------------------------------
def fetch_marketplace_data(keyword):
    print(f"🔍 [Search Engine] กำลังดึงข้อมูลสินค้าคำว่า: '{keyword}'...")
    
    # ข้อมูลจำลองที่ดึงมาจาก E-commerce
    mock_data = [
        {"platform": "Lazada", "title": f"Apple {keyword} (256GB) - Natural Titanium เครื่องศูนย์ไทย", "price": 37900, "url": "https://www.lazada.co.th/"},
        {"platform": "Shopee", "title": f"เคสกันกระแทกอย่างดี สำหรับ {keyword} ใส ไม่เหลือง", "price": 290, "url": "https://shopee.co.th/"},
        {"platform": "TikTok Shop", "title": f"{keyword} 256GB TH มือ 1 ประกันศูนย์ 1 ปี", "price": 38500, "url": "https://www.tiktok.com/"},
        {"platform": "Shopee", "title": f"ฟิล์มกระจกโฟกัส กันรอย เต็มจอ {keyword}", "price": 150, "url": "https://shopee.co.th/"}
    ]
    return mock_data

# -------------------------------------------------------------------
# 2. ฟังก์ชัน Gemini AI Filter (กรองเคส/ฟิล์มออก เหลือเฉพาะตัวเครื่องจริง)
# -------------------------------------------------------------------
def filter_with_gemini(target_item, items_list):
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        print("⚠️ ไม่พบ GEMINI_API_KEY จะใช้ระบบกรองคำพื้นฐานแทน")
        return [item for item in items_list if not any(x in item['title'].lower() for x in ["เคส", "ฟิล์ม", "case"])]

    print("🤖 [AI Filter] ส่งข้อมูลให้ Gemini วิเคราะห์และคัดกรองเคส/อุปกรณ์เสริมออก...")
    
    prompt = f"""
    เป้าหมายผู้ใช้ต้องการซื้อ: "{target_item}"
    โปรดเลือกเฉพาะรายการที่เป็นตัวเครื่องจริงๆ เท่านั้น (ตัดเคส, ฟิล์ม, อุปกรณ์เสริม ออกทั้งหมด)
    
    รายการสินค้า:
    {json.dumps(items_list, ensure_ascii=False)}
    
    ตอบกลับเฉพาะ JSON Array ของรายการที่ผ่านการคัดกรองแล้วเท่านั้น ไม่ต้องมีคำอธิบายอื่น
    """

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        headers = {'Content-Type': 'application/json'}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        
        response = requests.post(url, headers=headers, json=payload)
        res_data = response.json()
        
        ai_reply = res_data['candidates'][0]['content']['parts'][0]['text']
        clean_json = ai_reply.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
        
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return [item for item in items_list if not any(x in item['title'].lower() for x in ["เคส", "ฟิล์ม", "case"])]

# -------------------------------------------------------------------
# 3. ฟังก์ชันส่งข้อความแจ้งเตือนเข้า LINE (Messaging API)
# -------------------------------------------------------------------
def send_line_broadcast(message_text):
    line_token = os.environ.get("LINE_NOTIFY_TOKEN")
    
    if not line_token:
        print("⚠️ ไม่พบ LINE_NOTIFY_TOKEN ไม่สามารถส่งแจ้งเตือนได้")
        return

    print("🔔 [LINE System] กำลังส่งข้อความแจ้งเตือนเข้า LINE...")
    
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {line_token}"
    }
    payload = {
        "messages": [
            {
                "type": "text",
                "text": message_text
            }
        ]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print("✅ ส่งแจ้งเตือนเข้า LINE สำเร็จแล้ว!")
    else:
        print(f"❌ ส่ง LINE ไม่สำเร็จ (Code {response.status_code}): {response.text}")

# -------------------------------------------------------------------
# 4. ฟังก์ชันหลักสั่งทำงาน
# -------------------------------------------------------------------
def main():
    target_keyword = "iPhone 15 Pro Max 256GB"
    target_price = 38000
    
    print("=" * 50)
    print(f"🎯 ค้นหา: {target_keyword} | ราคาเป้าหมาย: {target_price:,} บาท")
    print("=" * 50)
    
    # 1. ดึงข้อมูล
    raw_items = fetch_marketplace_data(target_keyword)
    
    # 2. ให้ AI กรอง
    valid_items = filter_with_gemini(target_keyword, raw_items)
    print(f"✅ คัดกรองเหลือเครื่องจริง: {len(valid_items)} รายการ\n")
    
    # 3. ตรวจสอบราคา และเตรียมข้อความส่ง LINE
    good_deals = []
    for item in valid_items:
        if item['price'] <= target_price:
            good_deals.append(item)
            
    if good_deals:
        msg = f"🔥 [Price Hunter] เจอนโปรราคาถูกกว่าเป้าแล้ว!\n"
        msg += f"🎯 สินค้า: {target_keyword}\n"
        msg += f"💰 ราคาเป้าหมาย: {target_price:,} บาท\n\n"
        
        for deal in good_deals:
            msg += f"📍 [{deal['platform']}] {deal['price']:,} บาท\n"
            msg += f"🔗 ลิงก์: {deal['url']}\n\n"
            
        send_line_broadcast(msg)
    else:
        print("😔 ยังไม่มีร้านไหนทำราคาลงมาถึงเป้าหมาย")

if __name__ == "__main__":
    main()
