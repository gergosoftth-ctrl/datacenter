import streamlit as st
import pandas as pd
import re
from PIL import Image, ImageEnhance
import pytesseract

def get_pac_header_text(img):
    """ฟังก์ชันตัดเฉพาะส่วนบนของรูปภาพ (เพื่ออ่านป้าย PAC ใหญ่สีดำ-ขาว)"""
    width, height = img.size
    # ตัดรูปเอาเฉพาะโซนบน 35% แรกของภาพ
    header_crop = img.crop((0, 0, width, int(height * 0.35)))
    
    # เพิ่ม Contrast ให้ป้ายสีดำ-ขาวเด่นชัดขึ้น
    gray = header_crop.convert('L')
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(3.0)
    
    text = pytesseract.image_to_string(enhanced, config=r'--oem 3 --psm 6')
    return text

def get_lcd_numbers(img):
    """ฟังก์ชันตัดเฉพาะส่วนจอ LCD สีเขียวตรงกลาง เพื่อดึงตัวเลขในจอเท่านั้น"""
    width, height = img.size
    # ตัดรูปเอาเฉพาะพื้นที่ตรงกลางช่วง 30% - 70% ของภาพ (ตำแหน่งของจอ LCD)
    lcd_crop = img.crop((int(width * 0.15), int(height * 0.30), int(width * 0.85), int(height * 0.70)))
    
    # เร่งความสว่างและ Contrast ของหน้าจอดิจิทัล
    gray = lcd_crop.convert('L')
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(2.5)
    
    # อ่านข้อความเฉพาะในจอ LCD
    lcd_text = pytesseract.image_to_string(enhanced, config=r'--oem 3 --psm 6')
    
    # 🎯 สกัดเฉพาะตัวเลขที่มีความยาวตั้งแต่ 2 หลักขึ้นไปในจอ LCD (เช่น 004674, 003085, 121604)
    # ไม่เอาตัวเลขอุณหภูมิหรือตัวเลขเล็กๆ ข้างนอก
    lcd_numbers = re.findall(r'\b\d{2,8}\b', lcd_text)
    
    return lcd_text, lcd_numbers

def run_app():
    st.title("🔍 ระบบอ่านตัวเลขจากรูปภาพ PAC 1 / PAC 3")
    st.write("เวอร์ชันโฟกัสโซน: อ่านป้าย PAC จากกล่องสีดำด้านบน และสกัดเฉพาะตัวเลขในจอ LCD สีเขียว")

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
                
                # 1. อ่านป้าย PAC จากโซนบน (กล่องดำใหญ่)
                header_text = get_pac_header_text(original_img)
                
                # ตรวจหา PAC 1 หรือ PAC 3
                has_pac1 = bool(re.search(r'P?AC\s*[-_]?\s*[1lI]\b', header_text, re.IGNORECASE))
                has_pac3 = bool(re.search(r'P?AC\s*[-_]?\s*3\b', header_text, re.IGNORECASE))
                
                # ถ้าโซนบนสแกนไม่เจอ ลองสแกนทั้งรูปสำรองไว้
                if not has_pac1 and not has_pac3:
                    full_text = pytesseract.image_to_string(original_img, config=r'--oem 3 --psm 11')
                    has_pac1 = bool(re.search(r'P?AC\s*[-_]?\s*[1lI]\b', full_text, re.IGNORECASE))
                    has_pac3 = bool(re.search(r'P?AC\s*[-_]?\s*3\b', full_text, re.IGNORECASE))

                pac_found_type = "-"
                if has_pac1:
                    pac_found_type = "PAC 1"
                elif has_pac3:
                    pac_found_type = "PAC 3"

                # 2. ถ้ารูปนี้ตรงเงื่อนไข PAC 1 หรือ PAC 3 ให้ไปตัดโฟกัสเจาะอ่านเฉพาะจอ LCD สีเขียว
                if has_pac1 or has_pac3:
                    lcd_raw_text, lcd_numbers = get_lcd_numbers(original_img)
                    
                    numbers_combined = ", ".join(lcd_numbers) if lcd_numbers else "อ่านตัวเลขในจอ LCD ไม่ชัด"
                    
                    all_extracted_data.append({
                        "ชื่อไฟล์": uploaded_file.name,
                        "ประเภทที่พบ": pac_found_type,
                        "สถานะ": "✅ ผ่าน (พบ " + pac_found_type + ")",
                        "ตัวเลขเฉพาะในจอ LCD": numbers_combined,
                        "ข้อความดิบในจอ LCD": lcd_raw_text.strip().replace('\n', ' | ')
                    })
                else:
                    all_extracted_data.append({
                        "ชื่อไฟล์": uploaded_file.name,
                        "ประเภทที่พบ": "-",
                        "สถานะ": "❌ ไม่ผ่าน (ไม่พบป้าย PAC 1 หรือ PAC 3)",
                        "ตัวเลขเฉพาะในจอ LCD": "-",
                        "ข้อความดิบในจอ LCD": "ข้ามการอ่าน"
                    })
                    
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดกับไฟล์ {uploaded_file.name}: {str(e)}")

        # --- ส่วนแสดงตารางผลลัพธ์ ---
        if all_extracted_data:
            st.markdown("---")
            st.subheader("📋 ตารางสรุปผลข้อมูลเฉพาะจอ LCD")
            
            df = pd.DataFrame(all_extracted_data)
            st.dataframe(df, use_container_width=True)
            
            with st.expander("🔍 คลิกเพื่อดูข้อความดิบเฉพาะจอ LCD ที่สแกนได้"):
                for idx, row in df.iterrows():
                    st.write(f"📁 **{row['ชื่อไฟล์']}** ({row['สถานะ']})")
                    st.code(row['ข้อความดิบในจอ LCD'])
                    st.markdown("---")
            
            csv_data = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 ดาวน์โหลดข้อมูลทั้งหมดเป็น CSV",
                data=csv_data,
                file_name="pac_lcd_numbers.csv",
                mime="text/csv",
                use_container_width=True
            )
