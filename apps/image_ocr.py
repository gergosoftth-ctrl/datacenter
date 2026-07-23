import streamlit as st
import pandas as pd
import re
import numpy as np
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import pytesseract

def get_pac_header_text(img):
    """สแกนป้าย PAC 1 / PAC 3 สีดำ-ขาว ด้านบน"""
    width, height = img.size
    # Crop โซนป้ายสีดำด้านบน 35% แรก
    header_crop = img.crop((0, 0, width, int(height * 0.35)))
    
    # เร่ง Contrast สำหรับป้ายดำ-ขาว
    gray = header_crop.convert('L')
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(3.0)
    
    text = pytesseract.image_to_string(enhanced, config=r'--oem 3 --psm 6')
    return text

def process_lcd_for_ocr(lcd_crop):
    """ปรับแต่งภาพจอ LCD สีเขียวดอทเมตริกซ์ ให้ตัวเลขเชื่อมติดกันและคมชัดที่สุด"""
    # 1. ขยายขนาดรูปภาพ 3 เท่า ให้พิกเซลจุดเชื่อมกัน
    width, height = lcd_crop.size
    lcd_crop = lcd_crop.resize((width * 3, height * 3), Image.Resampling.LANCZOS)
    
    # 2. แปลงเป็น Grayscale
    gray = lcd_crop.convert('L')
    
    # 3. เพิ่ม Contrast และ Sharpen
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(3.5)
    sharpened = enhanced.filter(ImageFilter.SHARPEN)
    
    # 4. ทำ Thresholding แปลงเป็น ขาว-ดำ เด็ดขาด (Binary Image)
    # ตัดแสงสะท้อนกระจก และทำให้ตัวหนังสือ LCD ดำเข้ม
    fn = lambda x : 255 if x > 110 else 0
    binary_img = sharpened.point(fn, mode='1')
    
    return binary_img

def get_lcd_numbers(img):
    """ดึงตัวเลขจากหน้าจอ LCD สีเขียว"""
    width, height = img.size
    # ตัดกรอบเน้นเฉพาะพื้นที่จอ LCD ตรงกลาง (30% ถึง 72% ของรูป)
    lcd_crop = img.crop((int(width * 0.10), int(height * 0.30), int(width * 0.90), int(height * 0.72)))
    
    # ปรับแต่งภาพด้วยฟังก์ชันปรับปรุงพิเศษสำหรับจอ LCD
    processed_lcd = process_lcd_for_ocr(lcd_crop)
    
    # 1. อ่านข้อความรวมทั้งหมดในจอ (PSM 6)
    config_all = r'--oem 3 --psm 6'
    lcd_text = pytesseract.image_to_string(processed_lcd, config=config_all)
    
    # 2. อ่านเน้นหาตัวเลขแบบเจาะจง (Digits Config)
    config_digits = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789'
    digits_only_text = pytesseract.image_to_string(processed_lcd, config=config_digits)
    
    # รวมข้อความดิบ
    combined_raw = lcd_text + "\n--- Digits Mode ---\n" + digits_only_text
    
    # 🎯 สกัดเฉพาะกลุ่มตัวเลขที่มีความยาวตั้งแต่ 2 หลักขึ้นไป (เช่น 004674, 003085, 121604)
    numbers_found = re.findall(r'\b\d{2,8}\b', combined_raw)
    
    # ลบตัวเลขที่ซ้ำกันออกโดยยังคงลำดับไว้
    unique_numbers = list(dict.fromkeys(numbers_found))
    
    return combined_raw, unique_numbers, processed_lcd

def run_app():
    st.title("🔍 ระบบอ่านตัวเลขจากรูปภาพ PAC 1 / PAC 3")
    st.write("เวอร์ชันปรับปรุงจอ LCD: ใช้ Thresholding และขยายพิกเซลให้อ่านหน้าจอดอทเมตริกซ์ได้แม่นยำ")

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
                
                # 1. เช็คป้าย PAC 1 หรือ PAC 3 จากกล่องดำด้านบน
                header_text = get_pac_header_text(original_img)
                
                has_pac1 = bool(re.search(r'P?AC\s*[-_]?\s*[1lI]\b', header_text, re.IGNORECASE))
                has_pac3 = bool(re.search(r'P?AC\s*[-_]?\s*3\b', header_text, re.IGNORECASE))
                
                # สำรอง: ถ้ายอมอ่านทั้งรูปเผื่อกรณีตัดกรอบหลุด
                if not has_pac1 and not has_pac3:
                    full_text = pytesseract.image_to_string(original_img, config=r'--oem 3 --psm 11')
                    has_pac1 = bool(re.search(r'P?AC\s*[-_]?\s*[1lI]\b', full_text, re.IGNORECASE))
                    has_pac3 = bool(re.search(r'P?AC\s*[-_]?\s*3\b', full_text, re.IGNORECASE))

                pac_found_type = "-"
                if has_pac1:
                    pac_found_type = "PAC 1"
                elif has_pac3:
                    pac_found_type = "PAC 3"

                # 2. อ่านตัวเลขเฉพาะในจอ LCD
                if has_pac1 or has_pac3:
                    lcd_raw_text, lcd_numbers, processed_lcd_img = get_lcd_numbers(original_img)
                    
                    numbers_combined = ", ".join(lcd_numbers) if lcd_numbers else "อ่านตัวเลขในจอ LCD ไม่ชัด"
                    
                    all_extracted_data.append({
                        "ชื่อไฟล์": uploaded_file.name,
                        "ประเภทที่พบ": pac_found_type,
                        "สถานะ": "✅ ผ่าน (พบ " + pac_found_type + ")",
                        "ตัวเลขเฉพาะในจอ LCD": numbers_combined,
                        "ข้อความดิบในจอ LCD": lcd_raw_text.strip().replace('\n', ' | '),
                        "processed_img": processed_lcd_img
                    })
                else:
                    all_extracted_data.append({
                        "ชื่อไฟล์": uploaded_file.name,
                        "ประเภทที่พบ": "-",
                        "สถานะ": "❌ ไม่ผ่าน (ไม่พบป้าย PAC 1 หรือ PAC 3)",
                        "ตัวเลขเฉพาะในจอ LCD": "-",
                        "ข้อความดิบในจอ LCD": "ข้ามการอ่าน",
                        "processed_img": None
                    })
                    
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดกับไฟล์ {uploaded_file.name}: {str(e)}")

        # --- ส่วนแสดงตารางผลลัพธ์ ---
        if all_extracted_data:
            st.markdown("---")
            st.subheader("📋 ตารางสรุปผลข้อมูลเฉพาะจอ LCD")
            
            # ลบ column รูปภาพออกก่อนนำลงตารางแสดงผล
            df_display = pd.DataFrame(all_extracted_data).drop(columns=['processed_img'])
            st.dataframe(df_display, use_container_width=True)
            
            with st.expander("🔍 คลิกเพื่อดูภาพจอ LCD ที่ปรับปรุงแล้ว และข้อความดิบ"):
                for data in all_extracted_data:
                    st.write(f"📁 **{data['ชื่อไฟล์']}** ({data['สถานะ']})")
                    if data['processed_img'] is not None:
                        col_img, col_text = st.columns([1, 2])
                        with col_img:
                            st.image(data['processed_img'], caption="ภาพจอ LCD หลังปรับแต่ง (Thresholded)", use_container_width=True)
                        with col_text:
                            st.code(data['ข้อความดิบในจอ LCD'])
                    else:
                        st.write("ไม่มีภาพประมวลผล")
                    st.markdown("---")
            
            csv_data = df_display.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 ดาวน์โหลดข้อมูลทั้งหมดเป็น CSV",
                data=csv_data,
                file_name="pac_lcd_numbers.csv",
                mime="text/csv",
                use_container_width=True
            )
