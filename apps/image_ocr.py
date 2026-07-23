import streamlit as st
import pandas as pd
import re
from PIL import Image, ImageEnhance
import pytesseract

def process_image_for_lcd(img):
    """ปรับแต่งรูปภาพเพื่อให้อ่านทั้งป้าย PAC และหน้าจอ LCD ได้แม่นยำที่สุด"""
    gray = img.convert('L')
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(2.5)
    brightness = ImageEnhance.Brightness(enhanced)
    bright_img = brightness.enhance(1.2)
    return bright_img

def run_app():
    st.title("🔍 ระบบอ่านตัวเลขจากรูปภาพ PAC 1 / PAC 3")
    st.write("เวอร์ชันปรับปรุงยืดหยุ่น: ดักจับเคส OCR อ่านเพี้ยน (เช่น AC l, PACI, PA C 1)")

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
                processed_img = process_image_for_lcd(original_img)
                
                # อ่านข้อความด้วยโหมดต่างๆ แล้วนำมารวมกัน
                raw_text_1 = pytesseract.image_to_string(processed_img, config=r'--oem 3 --psm 11')
                raw_text_2 = pytesseract.image_to_string(original_img, config=r'--oem 3 --psm 3')
                raw_text = raw_text_1 + "\n" + raw_text_2

                # 🎯 Regex ยืดหยุ่นพิเศษ:
                # ดักจับ: PAC 1, PAC1, AC 1, AC l, PACI, PAC 3, AC 3
                # (P มีหรือไม่มีก็ได้ / 1 อาจกลายเป็น 1, l, I)
                
                pattern_pac1 = r'P?AC\s*[-_]?\s*[1lI]\b'
                pattern_pac3 = r'P?AC\s*[-_]?\s*3\b'

                has_pac1 = bool(re.search(pattern_pac1, raw_text, re.IGNORECASE))
                has_pac3 = bool(re.search(pattern_pac3, raw_text, re.IGNORECASE))

                pac_found_type = "-"
                if has_pac1:
                    pac_found_type = "PAC 1"
                elif has_pac3:
                    pac_found_type = "PAC 3"

                if has_pac1 or has_pac3:
                    # ดึงตัวเลขทั้งหมดที่เจอในภาพ
                    numbers_found = re.findall(r'\b\d+(?:\.\d+)?\b', raw_text)
                    numbers_combined = ", ".join(numbers_found) if numbers_found else "ไม่พบตัวเลข"
                    
                    all_extracted_data.append({
                        "ชื่อไฟล์": uploaded_file.name,
                        "ประเภทที่พบ": pac_found_type,
                        "สถานะ": "✅ ผ่าน (พบ " + pac_found_type + ")",
                        "ตัวเลขทั้งหมดในภาพ": numbers_combined,
                        "ข้อความดิบที่สแกนได้": raw_text.strip().replace('\n', ' | ')
                    })
                else:
                    all_extracted_data.append({
                        "ชื่อไฟล์": uploaded_file.name,
                        "ประเภทที่พบ": "-",
                        "สถานะ": "❌ ไม่ผ่าน (ไม่พบ PAC 1 หรือ PAC 3)",
                        "ตัวเลขทั้งหมดในภาพ": "-",
                        "ข้อความดิบที่สแกนได้": raw_text.strip().replace('\n', ' | ') if raw_text.strip() else "อ่านไม่ได้"
                    })
                    
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดกับไฟล์ {uploaded_file.name}: {str(e)}")

        # --- ส่วนแสดงตารางผลลัพธ์ ---
        if all_extracted_data:
            st.markdown("---")
            st.subheader("📋 ตารางสรุปผลข้อมูล")
            
            df = pd.DataFrame(all_extracted_data)
            st.dataframe(df, use_container_width=True)
            
            with st.expander("🔍 คลิกเพื่อดูข้อความดิบที่ OCR อ่านได้จากแต่ละรูป"):
                for idx, row in df.iterrows():
                    st.write(f"📁 **{row['ชื่อไฟล์']}** ({row['สถานะ']})")
                    st.code(row['ข้อความดิบที่สแกนได้'])
                    st.markdown("---")
            
            csv_data = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 ดาวน์โหลดข้อมูลทั้งหมดเป็น CSV",
                data=csv_data,
                file_name="pac_extracted_data.csv",
                mime="text/csv",
                use_container_width=True
            )
