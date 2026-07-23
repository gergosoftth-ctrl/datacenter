import streamlit as st
import pandas as pd
import re
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract

def preprocess_image(image):
    """ฟังก์ชันปรับแต่งรูปภาพก่อนส่งให้ OCR อ่าน เพื่อเพิ่มความแม่นยำสูงขึ้น"""
    # 1. แปลงรูปเป็นสีขาว-ดำ (Grayscale)
    img = image.convert('L')
    
    # 2. เพิ่มความคมชัด (Contrast) ให้ตัวอักษรเข้มขึ้น
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    
    # 3. ขยายขนาดรูปเป็น 2 เท่า ให้ตัวอักษรใหญ่และอ่านง่ายขึ้น
    width, height = img.size
    img = img.resize((width * 2, height * 2), Image.Resampling.LANCZOS)
    
    return img

def run_app():
    st.title("🔍 ระบบอ่านตัวเลขจากรูปภาพ (Image OCR - Enhanced)")
    st.write("เวอร์ชันเพิ่มความแม่นยำ: รองรับ PAC1, PAC3, PAC5 (รวมถึงแบบมีเว้นวรรค เช่น PAC 1)")

    uploaded_files = st.file_uploader(
        "📥 เลือกไฟล์รูปภาพ (สามารถเลือกพร้อมกันได้หลายไฟล์):", 
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True
    )

    all_extracted_data = []

    if uploaded_files:
        st.markdown(f"📸 **กำลังประมวลผลรูปภาพทั้งหมด {len(uploaded_files)} ไฟล์...**")
        
        for uploaded_file in uploaded_files:
            try:
                # เปิดรูปภาพต้นฉบับ
                original_img = Image.open(uploaded_file)
                
                # 1. ปรับแต่งรูปภาพให้คมชัดก่อนอ่าน
                processed_img = preprocess_image(original_img)
                
                # 2. สั่งอ่านข้อความด้วย Tesseract พร้อมตั้งค่า psm 6 (อ่านข้อความแบบอิสระ)
                custom_config = r'--oem 3 --psm 6'
                raw_text = pytesseract.image_to_string(processed_img, config=custom_config)
                
                # ถ้ารายงานรอบแรกไม่เจอ ลองอ่านด้วยโหมด psm 11 แบบสำรอง
                if not raw_text.strip():
                    raw_text = pytesseract.image_to_string(processed_img, config=r'--oem 3 --psm 11')

                # 3. ใช้ Regex เช็คเงื่อนไข: ดักจับคำว่า PAC ตามด้วยเลข 1, 3 หรือ 5 (ยอมให้มีช่องว่างหรือขีดได้)
                # เช่น จับคำว่า: pac1, pac 1, pac-1, pac3, pac 3, pac5
                pac_pattern = r'PAC\s*[-_]?\s*[135]'
                has_pac = bool(re.search(pac_pattern, raw_text, re.IGNORECASE))

                if has_pac:
                    # ดึงตัวเลขทั้งหมดที่มีอยู่ในภาพออกมา
                    numbers_found = re.findall(r'\d+(?:\.\d+)?', raw_text)
                    numbers_combined = ", ".join(numbers_found) if numbers_found else "พบคำตามเงื่อนไข แต่ไม่พบตัวเลขอื่น"
                    
                    all_extracted_data.append({
                        "ชื่อไฟล์": uploaded_file.name,
                        "สถานะเงื่อนไข": "✅ ผ่าน (พบ PAC1/PAC3/PAC5)",
                        "ตัวเลขทั้งหมดที่พบ": numbers_combined,
                        "ข้อความดิบที่สแกนได้": raw_text.strip().replace('\n', ' ')
                    })
                else:
                    all_extracted_data.append({
                        "ชื่อไฟล์": uploaded_file.name,
                        "สถานะเงื่อนไข": "❌ ไม่ผ่าน (สแกนไม่เจอ PAC1/3/5)",
                        "ตัวเลขทั้งหมดที่พบ": "-",
                        "ข้อความดิบที่สแกนได้": raw_text.strip().replace('\n', ' ') if raw_text.strip() else "อ่านข้อความไม่ได้"
                    })
                    
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดกับไฟล์ {uploaded_file.name}: {str(e)}")

        # --- ส่วนแสดงผลตารางผลลัพธ์ ---
        if all_extracted_data:
            st.markdown("---")
            st.subheader("📋 ตารางสรุปผลข้อมูล")
            
            df = pd.DataFrame(all_extracted_data)
            st.dataframe(df, use_container_width=True)
            
            # โชว์ข้อความดิบให้เราเช็คดูได้ด้วยว่า OCR อ่านอะไรออกมาได้บ้าง
            with st.expander("🔍 ดูข้อความดิบทั้งหมดที่ OCR สแกนได้ (สำหรับตรวจสอบ Debug)"):
                for idx, row in df.iterrows():
                    st.write(f"**ไฟล์:** {row['ชื่อไฟล์']}")
                    st.code(row['ข้อความดิบที่สแกนได้'])
                    st.markdown("---")
            
            csv_data = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 ดาวน์โหลดข้อมูลทั้งหมดเป็น CSV",
                data=csv_data,
                file_name="ocr_extracted_numbers.csv",
                mime="text/csv",
                use_container_width=True
            )
