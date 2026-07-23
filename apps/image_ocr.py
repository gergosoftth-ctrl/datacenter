import streamlit as st
import pandas as pd
import re
import numpy as np
from PIL import Image
import easyocr

# โหลด EasyOCR Reader เข้า Memory (ใช้ Cache เพื่อให้โหลดครั้งเดียวไวขึ้น)
@st.cache_resource
def load_ocr_reader():
    return easyocr.Reader(['en'], gpu=False)

def run_app():
    st.title("🔍 ระบบอ่านตัวเลขจากรูปภาพ PAC 1 / PAC 3")
    st.caption("powered by EasyOCR Deep Learning Engine")

    # ดึงตัว Reader มาเตรียมไว้
    reader = load_ocr_reader()

    uploaded_files = st.file_uploader(
        "📥 เลือกไฟล์รูปภาพ (เลือกพร้อมกันได้หลายไฟล์):", 
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True
    )

    all_extracted_data = []

    if uploaded_files:
        st.markdown(f"📸 **กำลังประมวลผลรูปภาพทั้งหมด {len(uploaded_files)} ไฟล์ด้วย AI...**")
        
        for uploaded_file in uploaded_files:
            try:
                # แปลงไฟล์รูปภาพเป็น numpy array ส่งให้ EasyOCR
                original_img = Image.open(uploaded_file).convert('RGB')
                img_np = np.array(original_img)
                
                # สั่ง EasyOCR อ่านข้อความทั้งหมดในภาพ
                results = reader.readtext(img_np, detail=0)
                full_text = " ".join(results)

                # 🎯 1. เช็คป้ายว่าเป็น PAC 1 หรือ PAC 3 หรือไม่
                has_pac1 = bool(re.search(r'P?AC\s*[-_]?\s*[1lI]\b', full_text, re.IGNORECASE))
                has_pac3 = bool(re.search(r'P?AC\s*[-_]?\s*3\b', full_text, re.IGNORECASE))

                pac_found_type = "-"
                if has_pac1:
                    pac_found_type = "PAC 1"
                elif has_pac3:
                    pac_found_type = "PAC 3"

                # 🎯 2. สกัดเอาเฉพาะชุดตัวเลขที่เป็นชั่วโมงการทำงานบนหน้าจอ LCD
                if has_pac1 or has_pac3:
                    # ดึงกลุ่มตัวเลขที่มีความยาวตั้งแต่ 3 ถึง 8 หลัก (คัดเอาเลขชั่วโมงบนจอ LCD)
                    numbers_found = re.findall(r'\b\d{3,8}\b', full_text)
                    
                    # ลบตัวเลขซ้ำ
                    unique_numbers = list(dict.fromkeys(numbers_found))
                    numbers_combined = ", ".join(unique_numbers) if unique_numbers else "ไม่พบตัวเลขในจอ"
                    
                    all_extracted_data.append({
                        "ชื่อไฟล์": uploaded_file.name,
                        "ประเภทที่พบ": pac_found_type,
                        "สถานะ": "✅ ผ่าน (พบ " + pac_found_type + ")",
                        "ตัวเลขบนจอ LCD": numbers_combined,
                        "ข้อความทั้งหมดที่ AI อ่านได้": full_text
                    })
                else:
                    all_extracted_data.append({
                        "ชื่อไฟล์": uploaded_file.name,
                        "ประเภทที่พบ": "-",
                        "สถานะ": "❌ ไม่ผ่าน (ไม่พบป้าย PAC 1 หรือ PAC 3)",
                        "ตัวเลขบนจอ LCD": "-",
                        "ข้อความทั้งหมดที่ AI อ่านได้": full_text if full_text else "อ่านไม่ได้"
                    })
                    
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดกับไฟล์ {uploaded_file.name}: {str(e)}")

        # --- ส่วนแสดงตารางผลลัพธ์ ---
        if all_extracted_data:
            st.markdown("---")
            st.subheader("📋 ตารางสรุปผลข้อมูล")
            
            df = pd.DataFrame(all_extracted_data)
            st.dataframe(df, width="stretch")
            
            with st.expander("🔍 คลิกเพื่อดูข้อความทั้งหมดที่ EasyOCR อ่านได้จากรูปภาพ"):
                for idx, row in df.iterrows():
                    st.write(f"📁 **{row['ชื่อไฟล์']}** ({row['สถานะ']})")
                    st.code(row['ข้อความทั้งหมดที่ AI อ่านได้'])
                    st.markdown("---")
            
            csv_data = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 ดาวน์โหลดข้อมูลทั้งหมดเป็น CSV",
                data=csv_data,
                file_name="pac_easyocr_data.csv",
                mime="text/csv",
                width="stretch"
            )
