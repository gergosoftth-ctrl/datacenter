import streamlit as st
import pandas as pd
import re
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
import pytesseract

def preprocess_header_black_label(crop_img):
    """ปรับแต่งและกลับสีป้ายสีดำตัวหนังสือขาว"""
    gray = crop_img.convert('L')
    inverted = ImageOps.invert(gray)
    enhancer = ImageEnhance.Contrast(inverted)
    return enhancer.enhance(2.5)

def preprocess_lcd_fast(crop_img):
    """ปรับแต่งภาพหน้าจอ LCD แบบเบาพิเศษ (ประมวลผลไว ไม่กิน CPU)"""
    img_np = np.array(crop_img)
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    
    # ขยายรูปเล็กน้อยพอให้อ่านออก (1.5 เท่า) เพื่อลดภาระการคำนวณ
    resized = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_LINEAR)
    
    # เร่ง Contrast คมชัดแบบสเปกเบา
    enhanced = cv2.equalizeHist(resized)
    return enhanced

def extract_lcd_metrics(raw_lcd_text):
    """สกัดจับคู่ Key-Value หัวข้อและตัวเลขชั่วโมง"""
    metrics = {}
    
    labels = [
        "Active Operation",
        "Cool Mode",
        "Heat Mode",
        "Humidify Mode",
        "De-Humidify Mode",
        "Fan Operation",
        "Cool 1 Operation",
        "Cool 2 Operation",
        "Heat 1 Operation",
        "Heat 2 Operation",
        "Humidifier Operation"
    ]
    
    for label in labels:
        pattern = re.escape(label).replace(r'\ ', r'\s*') + r'.*?\b0*(\d+)\s*(?:hrs)?'
        match = re.search(pattern, raw_lcd_text, re.IGNORECASE)
        if match:
            value = match.group(1)
            metrics[label] = int(value) if value else 0
            
    return metrics

def run_app():
    st.title("🔍 ระบบอ่านตัวเลขจากรูปภาพ PAC 1 / PAC 3")
    st.caption("เวอร์ชันปรับแต่งความเร็ว (Fast & Light Mode)")

    uploaded_files = st.file_uploader(
        "📥 เลือกไฟล์รูปภาพ (เลือกพร้อมกันได้หลายไฟล์):", 
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True
    )

    all_extracted_data = []

    if uploaded_files:
        st.markdown(f"📸 **กำลังประมวลผลรูปภาพทั้งหมด {len(uploaded_files)} ไฟล์...**")
        
        for uploaded_file in uploaded_files:
            # ใช้ st.spinner แจ้งสถานะป้องกันแอปค้าง
            with st.spinner(f"⏳ กำลังสแกนไฟล์ {uploaded_file.name}..."):
                try:
                    original_img = Image.open(uploaded_file).convert('RGB')
                    width, height = original_img.size

                    # 🎯 โซน 1: Crop ป้าย PAC ด้านบน
                    header_crop = original_img.crop((0, 0, width, int(height * 0.35)))
                    inverted_header = preprocess_header_black_label(header_crop)
                    header_text = pytesseract.image_to_string(inverted_header, config=r'--oem 3 --psm 6')

                    has_pac1 = bool(re.search(r'P?AC\s*[-_]?\s*[1lI]\b', header_text, re.IGNORECASE))
                    has_pac3 = bool(re.search(r'P?AC\s*[-_]?\s*3\b', header_text, re.IGNORECASE))

                    pac_found_type = "-"
                    if has_pac1:
                        pac_found_type = "PAC 1"
                    elif has_pac3:
                        pac_found_type = "PAC 3"

                    # 🎯 โซน 2: Crop หน้าจอ LCD สีเขียว
                    if has_pac1 or has_pac3:
                        lcd_crop = original_img.crop((int(width * 0.20), int(height * 0.38), int(width * 0.80), int(height * 0.68)))
                        processed_lcd = preprocess_lcd_fast(lcd_crop)
                        
                        # สแกนอ่านข้อความ
                        lcd_raw_text = pytesseract.image_to_string(processed_lcd, config=r'--oem 3 --psm 6')
                        metrics = extract_lcd_metrics(lcd_raw_text)
                        
                        if metrics:
                            formatted_metrics = " | ".join([f"{k} = {v}" for k, v in metrics.items()])
                        else:
                            formatted_metrics = "สแกนเจอจอ LCD แต่จับคู่ชั่วโมงไม่สำเร็จ"

                        row_data = {
                            "ชื่อไฟล์": uploaded_file.name,
                            "ประเภทที่พบ": pac_found_type,
                            "สถานะ": "✅ ผ่าน (พบ " + pac_found_type + ")",
                            "สรุปค่าบนหน้าจอ LCD": formatted_metrics,
                            "ข้อความดิบ LCD": lcd_raw_text.strip()
                        }
                        
                        for k, v in metrics.items():
                            row_data[k] = v

                        all_extracted_data.append(row_data)
                    else:
                        all_extracted_data.append({
                            "ชื่อไฟล์": uploaded_file.name,
                            "ประเภทที่พบ": "-",
                            "สถานะ": "❌ ไม่ผ่าน (ไม่พบป้าย PAC 1 หรือ PAC 3)",
                            "สรุปค่าบนหน้าจอ LCD": "-",
                            "ข้อความดิบ LCD": "ข้ามการอ่าน"
                        })
                        
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาดกับไฟล์ {uploaded_file.name}: {str(e)}")

        # --- แสดงตารางผลลัพธ์ ---
        if all_extracted_data:
            st.markdown("---")
            st.subheader("📋 ตารางสรุปผลข้อมูล")
            
            df = pd.DataFrame(all_extracted_data)
            display_cols = ["ชื่อไฟล์", "ประเภทที่พบ", "สถานะ", "สรุปค่าบนหน้าจอ LCD"]
            st.dataframe(df[display_cols], width="stretch")
            
            with st.expander("🔍 คลิกเพื่อดูข้อความดิบที่สแกนได้จากหน้าจอ LCD"):
                for idx, row in df.iterrows():
                    st.write(f"📁 **{row['ชื่อไฟล์']}** ({row['สถานะ']})")
                    st.code(row['ข้อความดิบ LCD'])
                    st.markdown("---")
            
            csv_data = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 ดาวน์โหลดข้อมูลสรุปทั้งหมดเป็น CSV",
                data=csv_data,
                file_name="pac_lcd_metrics.csv",
                mime="text/csv",
                width="stretch"
            )
