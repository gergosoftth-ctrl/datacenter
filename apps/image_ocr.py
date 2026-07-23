import streamlit as st
import pandas as pd
import re
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
import pytesseract

def preprocess_header_black_label(crop_img):
    """ปรับแต่งและกลับสีป้ายสีดำตัวหนังสือขาว ให้กลายเป็นตัวหนังสือดำพื้นขาว"""
    gray = crop_img.convert('L')
    inverted = ImageOps.invert(gray)
    enhancer = ImageEnhance.Contrast(inverted)
    return enhancer.enhance(3.0)

def preprocess_lcd_screen(crop_img):
    """ปรับแต่งภาพหน้าจอ LCD Dot Matrix เพื่อให้อ่านข้อความตารางได้แม่นยำ"""
    img_np = np.array(crop_img)
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    
    # 1. ขยายขนาดรูป 3 เท่า
    resized = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    
    # 2. ปรับ Contrast ให้คมชัด
    alpha = 2.0  # Simple Contrast Control
    beta = 10    # Brightness Control
    contrast_img = cv2.convertScaleAbs(resized, alpha=alpha, beta=beta)
    
    # 3. Dilation ถมเส้นตัวหนังสือ Dot Matrix ให้หนาขึ้น
    kernel = np.ones((2,2), np.uint8)
    dilated_img = cv2.erode(contrast_img, kernel, iterations=1) # Erode On Black text = Dilation on black lines
    
    return dilated_img

def extract_lcd_metrics(raw_lcd_text):
    """สกัดเฉพาะค่าหัวข้อการทำงานชั่วโมง (Hours) เช่น Active Operation = 4674"""
    metrics = {}
    
    # รายการหัวข้อที่เราต้องการค้นหาจากหน้าจอ Liebert
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
        # Regex หาชื่อหัวข้อตามด้วยตัวเลขชั่วโมง (ตัดเลข 0 ข้างหน้าออก เช่น 004674 -> 4674)
        # ตัวอย่างแพทเทิร์น: Active\s*Operation.*?\s*0*(\d+)
        pattern = re.escape(label).replace(r'\ ', r'\s*') + r'.*?\b0*(\d+)\s*(?:hrs)?'
        match = re.search(pattern, raw_lcd_text, re.IGNORECASE)
        
        if match:
            value = match.group(1)
            metrics[label] = int(value) if value else 0
            
    return metrics

def run_app():
    st.title("🔍 ระบบอ่านตัวเลขจากรูปภาพ PAC 1 / PAC 3")
    st.caption("เวอร์ชันดึงค่าชั่วโมงการทำงาน (Run Hours) บนหน้าจอ Liebert LCD")

    uploaded_files = st.file_uploader(
        "📥 เลือกไฟล์รูปภาพ (เลือกพร้อมกันได้หลายไฟล์):", 
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True
    )

    all_extracted_data = []

    if uploaded_files:
        st.markdown(f"📸 **กำลังประมวลผลรูปภาพทั้งหมด {len(uploaded_files)} ไฟล์...**")
        
        for uploaded_file in uploaded_files:
            try:
                original_img = Image.open(uploaded_file).convert('RGB')
                width, height = original_img.size

                # -------------------------------------------------------------
                # 🎯 โซนที่ 1: Crop ป้าย PAC ด้านบน
                # -------------------------------------------------------------
                header_crop = original_img.crop((0, 0, width, int(height * 0.35)))
                inverted_header = preprocess_header_black_label(header_crop)
                header_text = pytesseract.image_to_string(inverted_header, config=r'--oem 3 --psm 6')

                # เช็คป้าย PAC 1 หรือ PAC 3
                has_pac1 = bool(re.search(r'P?AC\s*[-_]?\s*[1lI]\b', header_text, re.IGNORECASE))
                has_pac3 = bool(re.search(r'P?AC\s*[-_]?\s*3\b', header_text, re.IGNORECASE))

                pac_found_type = "-"
                if has_pac1:
                    pac_found_type = "PAC 1"
                elif has_pac3:
                    pac_found_type = "PAC 3"

                # -------------------------------------------------------------
                # 🎯 โซนที่ 2: Crop หน้าจอ LCD สีเขียว
                # -------------------------------------------------------------
                if has_pac1 or has_pac3:
                    # ตัดโฟกัสเฉพาะกรอบหน้าจอ LCD (25% - 68% ของความสูง)
                    lcd_crop = original_img.crop((int(width * 0.20), int(height * 0.38), int(width * 0.80), int(height * 0.68)))
                    processed_lcd = preprocess_lcd_screen(lcd_crop)
                    
                    # สแกนข้อความในหน้าจอ
                    lcd_raw_text = pytesseract.image_to_string(processed_lcd, config=r'--oem 3 --psm 6')
                    
                    # สกัดจับคู่ Key-Value
                    metrics = extract_lcd_metrics(lcd_raw_text)
                    
                    # จัดรูปแบบการแสดงผล Key = Value
                    if metrics:
                        formatted_metrics = " | ".join([f"{k} = {v}" for k, v in metrics.items()])
                    else:
                        formatted_metrics = "สแกนเจอจอ LCD แต่จับคู่หัวข้อชั่วโมงไม่สำเร็จ"

                    row_data = {
                        "ชื่อไฟล์": uploaded_file.name,
                        "ประเภทที่พบ": pac_found_type,
                        "สถานะ": "✅ ผ่าน (พบ " + pac_found_type + ")",
                        "สรุปค่าบนหน้าจอ LCD": formatted_metrics,
                        "ข้อความดิบ LCD": lcd_raw_text.strip()
                    }
                    
                    # ใส่คอลัมน์แยกแต่ละค่าลง DataFrame เพื่อสะดวกต่อการ Export CSV
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

        # --- ส่วนแสดงตารางผลลัพธ์ ---
        if all_extracted_data:
            st.markdown("---")
            st.subheader("📋 ตารางสรุปผลข้อมูล")
            
            df = pd.DataFrame(all_extracted_data)
            
            # คัดเลือกคอลัมน์ที่จะโชว์หน้าแรก
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
