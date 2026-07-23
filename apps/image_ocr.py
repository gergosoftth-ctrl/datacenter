import streamlit as st
import pandas as pd
import re
from PIL import Image, ImageEnhance
import pytesseract

def process_image_for_lcd(img):
    """ปรับแต่งรูปภาพเพื่อให้อ่านทั้งป้าย PAC และหน้าจอ LCD ได้แม่นยำที่สุด"""
    # 1. แปลงเป็นขาวดำ
    gray = img.convert('L')
    
    # 2. เร่งความคมชัด (Contrast)
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(2.5)
    
    # 3. เร่งความสว่าง (Brightness) เพื่อลดเงาสะท้อน
    brightness = ImageEnhance.Brightness(enhanced)
    bright_img = brightness.enhance(1.2)
    
    return bright_img

def run_app():
    st.title("🔍 ระบบอ่านตัวเลขจากรูปภาพ PAC 1 / PAC 3")
    st.write("เวอร์ชันปรับปรุงพิเศษ: รองรับการอ่านป้าย PAC และหน้าจอ LCD เครื่องปรับอากาศ Liebert")

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
                
                # ลองอ่านด้วยโหมด psm 11 (หาข้อความทั้งหมดที่กระจายอยู่)
                custom_config = r'--oem 3 --psm 11'
                raw_text = pytesseract.image_to_string(processed_img, config=custom_config)
                
                # อ่านสำรองด้วยรูปต้นฉบับเผื่อกรณีป้ายใหญ่
                if "PAC" not in raw_text and "pac" not in raw_text:
                    raw_text_orig = pytesseract.image_to_string(original_img, config=r'--oem 3 --psm 3')
                    raw_text += "\n" + raw_text_orig

                # 🎯 เงื่อนไข: เช็คเฉพาะ PAC 1 หรือ PAC 3 เท่านั้น!
                pac_pattern = r'pac\s*[-_]?\s*[13]\b'
                has_pac = bool(re.search(pac_pattern, raw_text, re.IGNORECASE))
                
                # ค้นหาว่าเป็น PAC 1 หรือ PAC 3
                pac_found_type = "-"
                match = re.search(r'pac\s*[-_]?\s*([13])\b', raw_text, re.IGNORECASE)
                if match:
                    pac_found_type = f"PAC {match.group(1)}"

                if has_pac:
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
            
            # เปิดดูข้อความดิบที่สแกนได้เพื่อเช็คความถูกต้อง (แก้ไขชื่อคอลัมน์ให้ตรงกันแล้ว)
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
