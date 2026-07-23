import streamlit as st
import pandas as pd
import re
import cv2
import numpy as np
from PIL import Image, ImageEnhance
import pytesseract

def preprocess_lcd(crop_img):
    """ปรับแต่งภาพหน้าจอ LCD สีเขียวให้อ่านตัวเลขได้คมชัดที่สุด"""
    img_np = np.array(crop_img)
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    
    # ขยายขนาด 2 เท่า
    resized = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    
    # เพิ่มความเข้มคมชัด (Contrast & Adaptive Thresholding)
    thresh = cv2.adaptiveThreshold(
        resized, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY_INV, 21, 10
    )
    
    # ถมจุดพิกเซลจอดอทเมตริกซ์ที่ขาดให้เชื่อมติดกันเป็นตัวเลข
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    final_img = cv2.bitwise_not(closed)
    return final_img

def run_app():
    st.title("🔍 ระบบอ่านตัวเลขจากรูปภาพ PAC 1 / PAC 3")
    st.caption("เวอร์ชันปรับแต่งโซนเฉพาะ: ไม่กิน RAM คลาวด์ และอ่านหน้าจอดิจิทัล")

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
                # 🎯 โซนที่ 1: Crop ป้าย PAC ด้านบน (กล่องดำใหญ่)
                # -------------------------------------------------------------
                header_crop = original_img.crop((0, 0, width, int(height * 0.35)))
                
                # เร่ง Contrast สำหรับป้ายดำ-ขาว
                gray_header = header_crop.convert('L')
                enhancer = ImageEnhance.Contrast(gray_header)
                enhanced_header = enhancer.enhance(3.0)
                
                header_text = pytesseract.image_to_string(enhanced_header, config=r'--oem 3 --psm 6')

                # ดักจับ PAC 1 หรือ PAC 3
                has_pac1 = bool(re.search(r'P?AC\s*[-_]?\s*[1lI]\b', header_text, re.IGNORECASE))
                has_pac3 = bool(re.search(r'P?AC\s*[-_]?\s*3\b', header_text, re.IGNORECASE))

                pac_found_type = "-"
                if has_pac1:
                    pac_found_type = "PAC 1"
                elif has_pac3:
                    pac_found_type = "PAC 3"

                # -------------------------------------------------------------
                # 🎯 โซนที่ 2: Crop หน้าจอ LCD สีเขียวตรงกลาง
                # -------------------------------------------------------------
                if has_pac1 or has_pac3:
                    lcd_crop = original_img.crop((int(width * 0.15), int(height * 0.30), int(width * 0.85), int(height * 0.70)))
                    processed_lcd = preprocess_lcd(lcd_crop)
                    
                    # บังคับสแกนหาเฉพาะตัวเลขบนหน้าจอ LCD
                    config_digits = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789'
                    lcd_text = pytesseract.image_to_string(processed_lcd, config=config_digits)

                    # ดึงกลุ่มตัวเลขความยาว 3-8 หลัก (ชั่วโมงการทำงาน)
                    numbers_found = re.findall(r'\b\d{3,8}\b', lcd_text)
                    unique_numbers = list(dict.fromkeys(numbers_found))
                    numbers_combined = ", ".join(unique_numbers) if unique_numbers else "ไม่พบตัวเลขในจอ"

                    all_extracted_data.append({
                        "ชื่อไฟล์": uploaded_file.name,
                        "ประเภทที่พบ": pac_found_type,
                        "สถานะ": "✅ ผ่าน (พบ " + pac_found_type + ")",
                        "ตัวเลขบนจอ LCD": numbers_combined,
                        "ข้อความป้ายส่วนบน": header_text.strip(),
                        "ตัวเลขที่สแกนได้ในจอ LCD": lcd_text.strip()
                    })
                else:
                    all_extracted_data.append({
                        "ชื่อไฟล์": uploaded_file.name,
                        "ประเภทที่พบ": "-",
                        "สถานะ": "❌ ไม่ผ่าน (ไม่พบป้าย PAC 1 หรือ PAC 3)",
                        "ตัวเลขบนจอ LCD": "-",
                        "ข้อความป้ายส่วนบน": header_text.strip() if header_text.strip() else "อ่านไม่ได้",
                        "ตัวเลขที่สแกนได้ในจอ LCD": "ข้ามการอ่าน"
                    })
                    
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดกับไฟล์ {uploaded_file.name}: {str(e)}")

        # --- ส่วนแสดงตารางผลลัพธ์ ---
        if all_extracted_data:
            st.markdown("---")
            st.subheader("📋 ตารางสรุปผลข้อมูล")
            
            df = pd.DataFrame(all_extracted_data)
            st.dataframe(df[["ชื่อไฟล์", "ประเภทที่พบ", "สถานะ", "ตัวเลขบนจอ LCD"]], width="stretch")
            
            with st.expander("🔍 คลิกเพื่อดูรายละเอียดข้อความที่ OCR อ่านได้"):
                for idx, row in df.iterrows():
                    st.write(f"📁 **{row['ชื่อไฟล์']}** ({row['สถานะ']})")
                    st.write(f"🏷️ **ข้อความป้ายบน:** `{row['ข้อความป้ายส่วนบน']}`")
                    st.write(f"📟 **ตัวเลขในจอ LCD:** `{row['ตัวเลขที่สแกนได้ในจอ LCD']}`")
                    st.markdown("---")
            
            csv_data = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 ดาวน์โหลดข้อมูลทั้งหมดเป็น CSV",
                data=csv_data,
                file_name="pac_ocr_data.csv",
                mime="text/csv",
                width="stretch"
            )
