import streamlit as st
import pandas as pd
import re
import numpy as np
from PIL import Image, ImageEnhance
import easyocr

@st.cache_resource
def load_ocr_reader():
    return easyocr.Reader(['en'], gpu=False)

def run_app():
    st.title("🔍 ระบบอ่านตัวเลขจากรูปภาพ PAC 1 / PAC 3")
    st.caption("เวอร์ชัน Crop เจาะจงโซน: แยกสแกนป้าย PAC ด้านบน และจอ LCD ตรงกลาง")

    reader = load_ocr_reader()

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
                # 🎯 โซนที่ 1: Crop ป้าย PAC ด้านบน (พื้นที่ 0% - 35% ของความสูงภาพ)
                # -------------------------------------------------------------
                header_crop = original_img.crop((0, 0, width, int(height * 0.35)))
                header_results = reader.readtext(np.array(header_crop), detail=0)
                header_text = " ".join(header_results)

                # ดักจับ PAC 1 หรือ PAC 3 (รองรับ AC 1, AC l, PACI, PAC 1, PAC 3)
                has_pac1 = bool(re.search(r'P?AC\s*[-_]?\s*[1lI]\b', header_text, re.IGNORECASE))
                has_pac3 = bool(re.search(r'P?AC\s*[-_]?\s*3\b', header_text, re.IGNORECASE))

                pac_found_type = "-"
                if has_pac1:
                    pac_found_type = "PAC 1"
                elif has_pac3:
                    pac_found_type = "PAC 3"

                # -------------------------------------------------------------
                # 🎯 โซนที่ 2: Crop หน้าจอ LCD สีเขียวตรงกลาง (พื้นที่ 35% - 70% ของความสูง)
                # -------------------------------------------------------------
                if has_pac1 or has_pac3:
                    lcd_crop = original_img.crop((int(width * 0.15), int(height * 0.35), int(width * 0.85), int(height * 0.70)))
                    
                    # เร่ง Contrast ในโซนจอ LCD ให้ตัวเลขเข้มชัดขึ้น
                    enhancer = ImageEnhance.Contrast(lcd_crop)
                    lcd_enhanced = enhancer.enhance(2.0)
                    
                    lcd_results = reader.readtext(np.array(lcd_enhanced), detail=0)
                    lcd_text = " ".join(lcd_results)

                    # ดึงเฉพาะกลุ่มตัวเลขบนหน้าจอ LCD
                    numbers_found = re.findall(r'\b\d{2,8}\b', lcd_text)
                    unique_numbers = list(dict.fromkeys(numbers_found))
                    numbers_combined = ", ".join(unique_numbers) if unique_numbers else "ไม่พบตัวเลขในจอ"

                    all_extracted_data.append({
                        "ชื่อไฟล์": uploaded_file.name,
                        "ประเภทที่พบ": pac_found_type,
                        "สถานะ": "✅ ผ่าน (พบ " + pac_found_type + ")",
                        "ตัวเลขบนจอ LCD": numbers_combined,
                        "ข้อความป้ายส่วนบน": header_text,
                        "ข้อความในจอ LCD": lcd_text
                    })
                else:
                    all_extracted_data.append({
                        "ชื่อไฟล์": uploaded_file.name,
                        "ประเภทที่พบ": "-",
                        "สถานะ": "❌ ไม่ผ่าน (ไม่พบป้าย PAC 1 หรือ PAC 3)",
                        "ตัวเลขบนจอ LCD": "-",
                        "ข้อความป้ายส่วนบน": header_text if header_text else "อ่านไม่ได้",
                        "ข้อความในจอ LCD": "ข้ามการอ่าน"
                    })
                    
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดกับไฟล์ {uploaded_file.name}: {str(e)}")

        # --- ส่วนแสดงตารางผลลัพธ์ ---
        if all_extracted_data:
            st.markdown("---")
            st.subheader("📋 ตารางสรุปผลข้อมูล")
            
            df = pd.DataFrame(all_extracted_data)
            # แสดงเฉพาะคอลัมน์หลักในตาราง
            st.dataframe(df[["ชื่อไฟล์", "ประเภทที่พบ", "สถานะ", "ตัวเลขบนจอ LCD"]], width="stretch")
            
            with st.expander("🔍 คลิกเพื่อดูรายละเอียดข้อความที่ AI อ่านได้แยกตามโซน"):
                for idx, row in df.iterrows():
                    st.write(f"📁 **{row['ชื่อไฟล์']}** ({row['สถานะ']})")
                    st.write(f"🏷️ **ข้อความโซนป้ายบน:** `{row['ข้อความป้ายส่วนบน']}`")
                    st.write(f"📟 **ข้อความโซนจอ LCD:** `{row['ข้อความในจอ LCD']}`")
                    st.markdown("---")
            
            csv_data = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 ดาวน์โหลดข้อมูลทั้งหมดเป็น CSV",
                data=csv_data,
                file_name="pac_crop_ocr_data.csv",
                mime="text/csv",
                width="stretch"
            )
