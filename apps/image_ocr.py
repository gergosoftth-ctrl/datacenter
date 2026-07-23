import streamlit as st
import pandas as pd
import re
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
import pytesseract

def preprocess_header_black_label(crop_img):
    """ปรับแต่งและแปลงป้ายสีดำตัวหนังสือขาว ให้คมชัดสูงสุด"""
    gray = np.array(crop_img.convert('L'))
    inverted = cv2.bitwise_not(gray)
    _, thresh = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(thresh)

def preprocess_lcd_clean(crop_img):
    """ปรับแต่งภาพหน้าจอ LCD สีเขียว (เน้นเพิ่มความคมชัดและขยายขนาดสำหรับจอ Liebert)"""
    img_np = np.array(crop_img)
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    
    # ขยายรูป 2.2 เท่า เพื่อให้ตัวหนังสือบนจอ LCD ชัดเจน
    resized = cv2.resize(gray, None, fx=2.2, fy=2.2, interpolation=cv2.INTER_CUBIC)
    
    # เร่ง Contrast ถนอมฟอนต์
    clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(resized)
    
    return Image.fromarray(enhanced)

def clean_ocr_digits(val_str):
    """
    เงื่อนไขข้อ 2: แปลงตัวอักษรที่ OCR อ่านเพี้ยนกลับเป็นตัวเลขบริสุทธิ์
    และตัดเลข 0 ข้างหน้าออก (เช่น 004674 -> 4674, 000000 -> 0)
    """
    charmap = {
        'o': '0', 'O': '0', 'D': '0', 'Q': '0',
        'i': '1', 'l': '1', 'I': '1', '|': '1', '!': '1',
        'z': '2', 'Z': '2',
        'e': '6', 'E': '6',
        's': '5', 'S': '5',
        'g': '9', 'q': '9',
        'b': '6', 'B': '8'
    }
    cleaned = ""
    for char in val_str:
        if char.isdigit():
            cleaned += char
        elif char in charmap:
            cleaned += charmap[char]
            
    if cleaned:
        try:
            return int(cleaned) # แปลงเป็น int ตัด 0 นำหน้าอัตโนมัติ
        except ValueError:
            return None
    return None

def check_black_label_pac(header_crop):
    """
    เงื่อนไขข้อ 1: ตรวจหาว่าใช่ PAC 1 หรือ PAC 3 จากป้ายกรอบดำตัวหนังสือขาวส่วนหัวเท่านั้น
    """
    processed_header = preprocess_header_black_label(header_crop)
    
    t11 = pytesseract.image_to_string(processed_header, config=r'--oem 3 --psm 11')
    t6 = pytesseract.image_to_string(processed_header, config=r'--oem 3 --psm 6')
    t3 = pytesseract.image_to_string(processed_header, config=r'--oem 3 --psm 3')
    
    raw_text = f"{t11}\n{t6}\n{t3}"
    
    clean_text = re.sub(r'[\r\n\t]+', ' ', raw_text)
    clean_text = re.sub(r'[^a-zA-Z0-9\s]', ' ', clean_text)
    clean_text = re.sub(r'\s+', ' ', clean_text)

    has_pac1 = bool(re.search(r'\bP[A4]C\s*0*1\b', clean_text, re.IGNORECASE))
    has_pac3 = bool(re.search(r'\bP[A4]C\s*0*3\b|\bP[A4]C.*?0*3\b', clean_text, re.IGNORECASE))

    if has_pac1 and not has_pac3:
        return "PAC 1", t6.strip() if t6.strip() else raw_text.strip()
    elif has_pac3 and not has_pac1:
        return "PAC 3", t6.strip() if t6.strip() else raw_text.strip()
    elif has_pac1 and has_pac3:
        return "PAC 1 / PAC 3", t6.strip() if t6.strip() else raw_text.strip()

    return None, t6.strip() if t6.strip() else raw_text.strip()

def extract_lcd_metrics(raw_lcd_text):
    """
    เงื่อนไขข้อ 2: สกัดตัวเลขจากจอ LCD ยืดหยุ่นสูงสุด
    """
    metrics = {}
    
    labels_config = [
        ("Active Operation", r"(?:Acti[vea]?|Aelive)\s*O[pe]rat"),
        ("Cool Mode", r"Cool\s*Mode"),
        ("Heat Mode", r"Heat\s*Mode"),
        ("Humidify Mode", r"Humidif[y|ier]\s*Mode"),
        ("De-Humidify Mode", r"De-?\s*Humidif[y|ier]\s*Mod"),
        ("Fan Operation", r"Fan\s*O[pe]rat"),
        ("Cool 1 Operation", r"(?:Cool|Geel)\s*1\s*O[pe]rat"),
        ("Cool 2 Operation", r"(?:Cool|Geel)\s*2\s*O[pe]rat"),
        ("Heat 1 Operation", r"Heat\s*1\s*O[pe]rat"),
        ("Heat 2 Operation", r"Heat\s*2\s*O[pe]rat"),
        ("Heater 1 Operation", r"Heater\s*1\s*O[pe]rat"),
        ("Heater 2 Operation", r"Heater\s*2\s*O[pe]rat"),
        ("Humidifier Operation", r"Humidifi[er]?\s*O[pe]rat"),
    ]
    
    lines = raw_lcd_text.split('\n')
    
    for label_title, pattern in labels_config:
        for line in lines:
            if re.search(pattern, line, re.IGNORECASE):
                # สกัดข้อความส่วนท้ายหลังคำอธิบาย
                parts = re.split(r'[:\s]+', line)
                if len(parts) >= 2:
                    # หาพาร์ทที่เป็นชุดตัวเลขหรือตัวเลขผสมอักษรเพี้ยน
                    for part in reversed(parts):
                        val_digit = clean_ocr_digits(part)
                        if val_digit is not None:
                            metrics[label_title] = val_digit
                            break
                    if label_title in metrics:
                        break
                    
    return metrics

def run_app():
    st.title("🔍 ระบบอ่านตัวเลขจากรูปภาพ PAC 1 / PAC 3")
    st.caption("ระบบตรวจสอบป้ายกรอบดำตัวหนังสือขาว PAC 1 / PAC 3 และสกัดตัวเลขจากจอสีเขียว")

    uploaded_files = st.file_uploader(
        "📥 เลือกไฟล์รูปภาพ (เลือกพร้อมกันได้หลายไฟล์):", 
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True
    )

    all_extracted_data = []

    if uploaded_files:
        st.markdown(f"📸 **กำลังประมวลผลรูปภาพทั้งหมด {len(uploaded_files)} ไฟล์...**")
        
        for uploaded_file in uploaded_files:
            with st.spinner(f"⏳ กำลังสแกนไฟล์ {uploaded_file.name}..."):
                try:
                    original_img = Image.open(uploaded_file).convert('RGB')
                    width, height = original_img.size

                    # 🎯 โซน 1: Crop ป้ายกรอบดำตัวหนังสือขาวด้านบน (38% ด้านบน)
                    header_crop = original_img.crop((0, 0, width, int(height * 0.38)))
                    pac_type, raw_header_text = check_black_label_pac(header_crop)

                    # 🎯 เงื่อนไขข้อ 1 & 3: หากพบ PAC 1 หรือ PAC 3 จากป้ายกรอบดำ ให้ดึงข้อมูลบนจอสีเขียว
                    if pac_type is not None:
                        # Crop เฉพาะพื้นที่กรอบจอสีเขียวตรงกลาง (เจาะจงไม่ให้ติดปุ่มกดหรือขอบพลาสติก)
                        lcd_crop = original_img.crop((int(width * 0.22), int(height * 0.40), int(width * 0.78), int(height * 0.66)))
                        processed_lcd = preprocess_lcd_clean(lcd_crop)
                        
                        # สแกนอ่านข้อความ LCD สองแบบเพื่อกันพลาด (PSM 6 และ PSM 4)
                        raw_lcd6 = pytesseract.image_to_string(processed_lcd, config=r'--oem 3 --psm 6')
                        raw_lcd4 = pytesseract.image_to_string(processed_lcd, config=r'--oem 3 --psm 4')
                        combined_lcd = f"{raw_lcd6}\n{raw_lcd4}"
                        
                        metrics = extract_lcd_metrics(combined_lcd)
                        
                        if metrics:
                            formatted_metrics = " | ".join([f"{k} = {v}" for k, v in metrics.items()])
                            status_text = f"✅ ผ่าน (พบ {pac_type})"
                        else:
                            formatted_metrics = "สแกนเจอจอ LCD แต่ไม่พบรูปแบบตัวเลข"
                            status_text = f"⚠️ พบป้าย {pac_type} แต่สกัดตัวเลขจอ LCD ไม่สำเร็จ"

                        row_data = {
                            "ชื่อไฟล์": uploaded_file.name,
                            "ประเภทที่พบ": pac_type,
                            "สถานะ": status_text,
                            "สรุปค่าบนหน้าจอ LCD": formatted_metrics,
                            "ข้อความดิบป้ายส่วนหัว": raw_header_text,
                            "ข้อความดิบ LCD": raw_lcd6.strip()
                        }
                        
                        for k, v in metrics.items():
                            row_data[k] = v

                        all_extracted_data.append(row_data)
                    
                    else:
                        # 🎯 เงื่อนไขข้อ 3: หากไม่ใช่ PAC 1 หรือ PAC 3 ไม่ต้องดึงข้อมูล
                        all_extracted_data.append({
                            "ชื่อไฟล์": uploaded_file.name,
                            "ประเภทที่พบ": "-",
                            "สถานะ": "❌ ไม่ผ่าน (ไม่พบป้าย PAC 1 หรือ PAC 3 ในกรอบดำ)",
                            "สรุปค่าบนหน้าจอ LCD": "-",
                            "ข้อความดิบป้ายส่วนหัว": raw_header_text if raw_header_text else "(อ่านไม่พบข้อความ)",
                            "ข้อความดิบ LCD": "ข้ามการอ่านข้อมูล (ไม่ตรงตามเงื่อนไขข้อ 1)"
                        })
                        
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาดกับไฟล์ {uploaded_file.name}: {str(e)}")

        # --- แสดงตารางผลลัพธ์ ---
        if all_extracted_data:
            st.markdown("---")
            st.subheader("📋 ตารางสรุปผลข้อมูล")
            
            df = pd.DataFrame(all_extracted_data)
            display_cols = ["ชื่อไฟล์", "ประเภทที่พบ", "สถานะ", "สรุปค่าบนหน้าจอ LCD"]
            st.dataframe(df[display_cols], width="stretch")
            
            with st.expander("🔍 คลิกเพื่อดูข้อความดิบที่สแกนได้"):
                for idx, row in df.iterrows():
                    st.write(f"📁 **{row['ชื่อไฟล์']}** ({row['สถานะ']})")
                    st.text(f"ข้อความบนป้ายส่วนหัว: '{row['ข้อความดิบป้ายส่วนหัว']}'")
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
