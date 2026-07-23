import streamlit as st
import pandas as pd
import re
import cv2
import numpy as np
from PIL import Image
import pytesseract

def preprocess_dot_matrix_lcd(pil_img):
    """ปรับแต่งภาพหน้าจอดอทเมตริกซ์ LCD โดยการหลอมจุดพิกเซลให้เชื่อมกันเป็นตัวเลขทึบ"""
    # แปลง PIL Image เป็น OpenCV BGR Image
    img_np = np.array(pil_img)
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    
    # 1. ขยายขนาดภาพ 2 เท่า
    resized = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    
    # 2. ทำ Adaptive Thresholding แยกตัวหนังสือออกจากพื้นหลัง
    thresh = cv2.adaptiveThreshold(
        resized, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY_INV, 21, 10
    )
    
    # 3. 🎯 Morphological Closing: เชื่อมจุดดอทเมตริกซ์ที่ขาดให้ติดกัน
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    # พลิกกลับเป็นตัวดำพื้นขาว
    final_img = cv2.bitwise_not(closed)
    return final_img

def run_app():
    st.title("🔍 ระบบอ่านตัวเลขจากรูปภาพ PAC 1 / PAC 3")
    st.caption("เวอร์ชันเชื่อมจุดพิกเซลจอดอทเมตริกซ์ (Morphological OCR)")

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
                original_img = Image.open(uploaded_file)
                
                # 1. อ่านข้อความรวมทั้งหมดจากภาพต้นฉบับเพื่อหาป้าย PAC
                raw_full_text = pytesseract.image_to_string(original_img, config=r'--oem 3 --psm 11')
                
                # 2. ปรับแต่งภาพด้วย OpenCV สำหรับอ่านจอดอทเมตริกซ์ LCD
                processed_lcd = preprocess_dot_matrix_lcd(original_img)
                lcd_text = pytesseract.image_to_string(processed_lcd, config=r'--oem 3 --psm 6')
                
                combined_text = raw_full_text + " " + lcd_text

                # 🎯 เช็คว่าพบ PAC 1 หรือ PAC 3 หรือไม่
                has_pac1 = bool(re.search(r'P?AC\s*[-_]?\s*[1lI]\b', combined_text, re.IGNORECASE))
                has_pac3 = bool(re.search(r'P?AC\s*[-_]?\s*3\b', combined_text, re.IGNORECASE))

                pac_found_type = "-"
                if has_pac1:
                    pac_found_type = "PAC 1"
                elif has_pac3:
                    pac_found_type = "PAC 3"

                if has_pac1 or has_pac3:
                    # ดึงเฉพาะกลุ่มตัวเลขความยาว 3-8 หลักบนจอ
                    numbers_found = re.findall(r'\b\d{3,8}\b', combined_text)
                    unique_numbers = list(dict.fromkeys(numbers_found))
                    numbers_combined = ", ".join(unique_numbers) if unique_numbers else "ไม่พบตัวเลขในจอ"
                    
                    all_extracted_data.append({
                        "ชื่อไฟล์": uploaded_file.name,
                        "ประเภทที่พบ": pac_found_type,
                        "สถานะ": "✅ ผ่าน (พบ " + pac_found_type + ")",
                        "ตัวเลขบนจอ LCD": numbers_combined,
                        "ข้อความดิบที่ OCR อ่านได้": combined_text.strip().replace('\n', ' | ')
                    })
                else:
                    all_extracted_data.append({
                        "ชื่อไฟล์": uploaded_file.name,
                        "ประเภทที่พบ": "-",
                        "สถานะ": "❌ ไม่ผ่าน (ไม่พบป้าย PAC 1 หรือ PAC 3)",
                        "ตัวเลขบนจอ LCD": "-",
                        "ข้อความดิบที่ OCR อ่านได้": combined_text.strip().replace('\n', ' | ') if combined_text.strip() else "อ่านไม่ได้"
                    })
                    
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดกับไฟล์ {uploaded_file.name}: {str(e)}")

        # --- ส่วนแสดงตารางผลลัพธ์ ---
        if all_extracted_data:
            st.markdown("---")
            st.subheader("📋 ตารางสรุปผลข้อมูล")
            
            df = pd.DataFrame(all_extracted_data)
            st.dataframe(df, width="stretch")
            
            with st.expander("🔍 คลิกเพื่อดูข้อความดิบทั้งหมดที่ OCR สแกนได้"):
                for idx, row in df.iterrows():
                    st.write(f"📁 **{row['ชื่อไฟล์']}** ({row['สถานะ']})")
                    st.code(row['ข้อความดิบที่ OCR อ่านได้'])
                    st.markdown("---")
            
            csv_data = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 ดาวน์โหลดข้อมูลทั้งหมดเป็น CSV",
                data=csv_data,
                file_name="pac_lcd_data.csv",
                mime="text/csv",
                width="stretch"
            )
