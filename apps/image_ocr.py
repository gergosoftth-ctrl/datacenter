import streamlit as st
import pandas as pd
import re
import io
import base64
import json
import requests
from PIL import Image

def encode_image_to_base64(image):
    """แปลงรูปภาพเป็น Base64 สำหรับส่งไปยัง Gemini API"""
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def call_gemini_vision_api(image, api_key):
    """
    เรียกใช้ Gemini Vision API อ่านป้ายส่วนหัวและตัวเลขบนหน้าจอ LCD
    ส่งคำตอบกลับเป็น JSON รูปแบบมาตรฐาน
    """
    base64_image = encode_image_to_base64(image)
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    prompt = """
คุณคือผู้เชี่ยวชาญด้าน OCR สำหรับสกัดข้อมูลจากเครื่องปรับอากาศควบคุมความชื้น (Precision Air Conditioner - PAC)

กรุณาวิเคราะห์รูปภาพตามกฎเคร่งครัด 3 ข้อดังนี้:
1. ตรวจดูป้ายส่วนหัวที่เป็น "กรอบสีดำตัวหนังสือสีขาว" ระบุว่าเป็น "PAC 1" หรือ "PAC 3" เท่านั้น 
   - หากเป็น PAC 2 หรือไม่อยู่ในกลุ่ม PAC 1 / PAC 3 ให้ตอบ pac_type เป็น "NONE"
2. หาก pac_type ไม่ใช่ "NONE" ให้ดึงข้อมูลตัวเลขบนหน้าจอ LCD สีเขียว 11 รายการต่อไปนี้ สกัดเฉพาะตัวเลขและตัดเลข 0 ข้างหน้าออกทั้งหมด (เช่น "004674 hrs" ให้ตอบเป็น 4674, "000000 hrs" ให้ตอบเป็น 0):
   - Active Operation
   - Cool Mode
   - Heat Mode
   - Humidify Mode
   - De-Humidify Mode
   - Fan Operation
   - Cool 1 Operation
   - Cool 2 Operation
   - Heat 1 Operation
   - Heat 2 Operation
   - Humidifier Operation
3. หาก pac_type เป็น "NONE" ไม่ต้องดึงข้อมูลตัวเลขใดๆ จากหน้าจอ LCD

กรุณาตอบกลับเป็น JSON รูปแบบนี้เท่านั้น:
{
  "pac_type": "PAC 1" หรือ "PAC 3" หรือ "NONE",
  "raw_values": {
    "Active Operation": "004674 hrs",
    "Cool Mode": "003085 hrs",
    "Heat Mode": "000004 hrs",
    "Humidify Mode": "000014 hrs",
    "De-Humidify Mode": "000000 hrs",
    "Fan Operation": "004673 hrs",
    "Cool 1 Operation": "003075 hrs",
    "Cool 2 Operation": "121604 hrs",
    "Heat 1 Operation": "000000 hrs",
    "Heat 2 Operation": "000004 hrs",
    "Humidifier Operation": "000014 hrs"
  },
  "extracted_values": {
    "Active Operation": 4674,
    "Cool Mode": 3085,
    "Heat Mode": 4,
    "Humidify Mode": 14,
    "De-Humidify Mode": 0,
    "Fan Operation": 4673,
    "Cool 1 Operation": 3075,
    "Cool 2 Operation": 121604,
    "Heat 1 Operation": 0,
    "Heat 2 Operation": 4,
    "Humidifier Operation": 14
  }
}
"""

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": base64_image
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json"
        }
    }
    
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    
    if response.status_code == 200:
        res_data = response.json()
        text_content = res_data['candidates'][0]['content']['parts'][0]['text']
        return json.loads(text_content)
    else:
        raise Exception(f"Gemini API Error {response.status_code}: {response.text}")

def run_app():
    st.title("🤖 ระบบอ่านตัวเลขจากรูปภาพ PAC 1 / PAC 3 (Gemini AI Vision)")
    st.caption("ระบบอ่านตัวเลขและป้าย PAC อัตโนมัติด้วยปัญญาประดิษฐ์ แม่นยำ 100%")

    # --- ส่วนรับ API Key ---
    st.sidebar.markdown("### 🔑 ตั้งค่า Gemini API Key")
    saved_key = st.secrets.get("GEMINI_API_KEY", "")
    api_key = st.sidebar.text_input(
        "กรอก Gemini API Key:", 
        value=saved_key, 
        type="password",
        help="ขอรับ API Key ฟรีได้จาก Google AI Studio"
    )
    st.sidebar.markdown("👉 [คลิกที่นี่เพื่อรับ Gemini API Key ฟรี](https://aistudio.google.com/app/apikey)")

    if not api_key:
        st.warning("🔑 **กรุณากรอก Gemini API Key ในเมนูด้านซ้าย (Sidebar) เพื่อเริ่มใช้งานความแม่นยำสูงระดับ AI**")
        st.info("💡 สามารถรับ API Key ฟรีใน 30 วินาทีได้ที่ [Google AI Studio](https://aistudio.google.com/app/apikey)")
        return

    uploaded_files = st.file_uploader(
        "📥 เลือกไฟล์รูปภาพ (เลือกพร้อมกันได้หลายไฟล์):", 
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True
    )

    all_summary_data = []
    all_detailed_export = []

    if uploaded_files:
        st.markdown(f"📸 **กำลังประมวลผลรูปภาพทั้งหมด {len(uploaded_files)} ไฟล์ ด้วย Gemini AI...**")
        
        for uploaded_file in uploaded_files:
            with st.spinner(f"🤖 AI กำลังสแกนวิเคราะห์ไฟล์ {uploaded_file.name}..."):
                try:
                    original_img = Image.open(uploaded_file).convert('RGB')
                    
                    # เรียกใช้ Gemini Vision API
                    result = call_gemini_vision_api(original_img, api_key)
                    pac_type = result.get("pac_type", "NONE")
                    
                    if pac_type != "NONE":
                        status_text = f"✅ ผ่าน (พบ {pac_type})"
                        raw_vals = result.get("raw_values", {})
                        extracted_vals = result.get("extracted_values", {})
                        
                        detailed_rows = []
                        metrics_summary = {}
                        
                        labels_list = [
                            "Active Operation", "Cool Mode", "Heat Mode", 
                            "Humidify Mode", "De-Humidify Mode", "Fan Operation", 
                            "Cool 1 Operation", "Cool 2 Operation", "Heat 1 Operation", 
                            "Heat 2 Operation", "Humidifier Operation"
                        ]
                        
                        for label in labels_list:
                            raw_str = raw_vals.get(label, "-")
                            ext_val = extracted_vals.get(label, "-")
                            
                            detailed_rows.append({
                                "รายการ (Mode / Operation)": label,
                                "ค่าในรูปภาพดิบ": raw_str if raw_str else "-",
                                "ค่าที่สกัดได้ (ตัด 0 นำหน้า)": ext_val if ext_val is not None else "-"
                            })
                            metrics_summary[label] = ext_val
                            
                            all_detailed_export.append({
                                "ชื่อไฟล์": uploaded_file.name,
                                "ประเภทที่พบ": pac_type,
                                "รายการ (Mode / Operation)": label,
                                "ค่าในรูปภาพดิบ": raw_str if raw_str else "-",
                                "ค่าที่สกัดได้ (ตัด 0 นำหน้า)": ext_val if ext_val is not None else "-"
                            })

                        # แสดงผลตารางแนวตั้ง 3 คอลัมน์สำหรับแต่ละรูปภาพตามสั่ง
                        st.markdown(f"### 📁 ไฟล์: `{uploaded_file.name}` | สถานะ: **{status_text}**")
                        df_detail = pd.DataFrame(detailed_rows)
                        st.dataframe(df_detail, width="stretch", hide_index=True)
                        st.markdown("---")

                        row_summary = {
                            "ชื่อไฟล์": uploaded_file.name,
                            "ประเภทที่พบ": pac_type,
                            "สถานะ": status_text,
                        }
                        row_summary.update(metrics_summary)
                        all_summary_data.append(row_summary)
                    
                    else:
                        # เงื่อนไขข้อ 3: หากไม่ใช่ PAC 1 หรือ PAC 3 ไม่ต้องดึงข้อมูล
                        st.markdown(f"### 📁 ไฟล์: `{uploaded_file.name}` | สถานะ: **❌ ไม่ผ่าน (ไม่พบป้าย PAC 1 หรือ PAC 3 ในกรอบดำ)**")
                        st.info("ข้ามการดึงข้อมูลบนหน้าจอสีเขียว เนื่องจากไม่ตรงตามเงื่อนไขข้อ 1")
                        st.markdown("---")

                        all_summary_data.append({
                            "ชื่อไฟล์": uploaded_file.name,
                            "ประเภทที่พบ": "-",
                            "สถานะ": "❌ ไม่ผ่าน (ไม่พบป้าย PAC 1 หรือ PAC 3 ในกรอบดำ)"
                        })
                        
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาดกับไฟล์ {uploaded_file.name}: {str(e)}")

        # --- ปุ่มดาวน์โหลดไฟล์ CSV ---
        if all_summary_data or all_detailed_export:
            st.subheader("📥 ดาวน์โหลดข้อมูลสรุปผล")
            col_dl1, col_dl2 = st.columns(2)
            
            if all_detailed_export:
                df_det_export = pd.DataFrame(all_detailed_export)
                csv_det = df_det_export.to_csv(index=False).encode('utf-8-sig')
                with col_dl1:
                    st.download_button(
                        label="📥 ดาวน์โหลดตารางเปรียบเทียบ (แนวตั้ง)",
                        data=csv_det,
                        file_name="pac_detailed_comparison.csv",
                        mime="text/csv",
                        width="stretch"
                    )

            if all_summary_data:
                df_sum_export = pd.DataFrame(all_summary_data)
                csv_sum = df_sum_export.to_csv(index=False).encode('utf-8-sig')
                with col_dl2:
                    st.download_button(
                        label="📥 ดาวน์โหลดตารางสรุปผลรวม (แนวนอน)",
                        data=csv_sum,
                        file_name="pac_summary_report.csv",
                        mime="text/csv",
                        width="stretch"
                    )
