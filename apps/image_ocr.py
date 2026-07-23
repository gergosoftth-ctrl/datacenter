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

def preprocess_lcd_clahe(crop_img):
    """ปรับแต่งภาพหน้าจอ LCD สีเขียว แบบ CLAHE"""
    img_np = np.array(crop_img)
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    resized = cv2.resize(gray, None, fx=2.2, fy=2.2, interpolation=cv2.INTER_CUBIC)
    clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(resized)
    return Image.fromarray(enhanced)

def preprocess_lcd_adaptive(crop_img):
    """ปรับแต่งภาพหน้าจอ LCD สีเขียว แบบ Adaptive Thresholding"""
    img_np = np.array(crop_img)
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    resized = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    thresh = cv2.adaptiveThreshold(resized, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 6)
    return Image.fromarray(thresh)

def clean_ocr_digits(val_str):
    """
    แปลงตัวอักษรที่ OCR อ่านเพี้ยนกลับเป็นตัวเลขบริสุทธิ์
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

def extract_lcd_metrics_detailed(raw_lcd_text):
    """
    เงื่อนไขข้อ 2: สกัดตารางรายละเอียดแบบเปรียบเทียบ
    - รายการ (Mode / Operation)
    - ค่าในรูปภาพดิบ (เช่น 004674 hrs)
    - ค่าที่สกัดได้ (ตัด 0 นำหน้า) (เช่น 4674)
    """
    detailed_rows = []
    summary_dict = {}
    
    labels_config = [
        ("Active Operation", [r"(?:Acti[vea]?|HeLive|Live)\s*O[pe]rat"]),
        ("Cool Mode", [r"Cool\s*Mo[de|ce]", r"Co[o0]l"]),
        ("Heat Mode", [r"Heat\s*Mo[de|se]"]),
        ("Humidify Mode", [r"Humidif[y|ier]\s*Mo[de|ck]"]),
        ("De-Humidify Mode", [r"De-?\s*Humidif[y|ier]\s*Mo[de|ac]"]),
        ("Fan Operation", [r"(?:Fan|Ean)\s*O[pe]rat"]),
        ("Cool 1 Operation", [r"(?:Cool|Geel|fool)\s*1\s*O[pe]rat"]),
        ("Cool 2 Operation", [r"(?:Cool|Geel|fool)\s*2\s*O[pe]rat"]),
        ("Heat 1 Operation", [r"Heat\s*1\s*O[pe]rat"]),
        ("Heat 2 Operation", [r"Heat\s*2\s*O[pe]rat"]),
        ("Humidifier Operation", [r"Humidifi[er]?\s*O[pe]rat"]),
    ]
    
    lines = raw_lcd_text.split('\n')
    
    for label_title, patterns in labels_config:
        raw_val_str = "-"
        clean_val_int = "-"
        
        for line in lines:
            matched = False
            for pat in patterns:
                if re.search(pat, line, re.IGNORECASE):
                    matched = True
                    break
            if matched:
                line_clean = re.sub(r'(\d)\s+(\d)', r'\1\2', line)
                line_clean = re.sub(r'([oOsiIl|eEsSzZbBqQg])\s+([0-9oOsiIl|eEsSzZbBqQg])', r'\1\2', line_clean)
                
                parts = re.split(r'[:\s]+', line_clean)
                if len(parts) >= 2:
                    for part in reversed(parts):
                        val_digit = clean_ocr_digits(part)
                        if val_digit is not None:
                            raw_val_str = part + " hrs" if not part.endswith("hrs") else part
                            clean_val_int = val_digit
                            break
                    if clean_val_int != "-":
                        break
                        
        detailed_rows.append({
            "รายการ (Mode / Operation)": label_title,
            "ค่าในรูปภาพดิบ": raw_val_str,
            "ค่าที่สกัดได้ (ตัด 0 นำหน้า)": clean_val_int
        })
        summary_dict[label_title] = clean_val_int
        
    return detailed_rows, summary_dict

def run_app():
    st.title("🔍 ระบบอ่านตัวเลขจากรูปภาพ PAC 1 / PAC 3")
    st.caption("ระบบตรวจสอบป้ายกรอบดำตัวหนังสือขาว PAC 1 / PAC 3 และสกัดตัวเลขจากจอสีเขียว")

    uploaded_files = st.file_uploader(
        "📥 เลือกไฟล์รูปภาพ (เลือกพร้อมกันได้หลายไฟล์):", 
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True
    )

    all_summary_data = []
    all_detailed_export = []

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
                        # Crop เฉพาะพื้นที่กรอบจอสีเขียวตรงกลาง
                        lcd_crop = original_img.crop((int(width * 0.20), int(height * 0.39), int(width * 0.80), int(height * 0.67)))
                        
                        img_clahe = preprocess_lcd_clahe(lcd_crop)
                        img_adaptive = preprocess_lcd_adaptive(lcd_crop)
                        
                        raw_lcd_clahe = pytesseract.image_to_string(img_clahe, config=r'--oem 3 --psm 6')
                        raw_lcd_adaptive = pytesseract.image_to_string(img_adaptive, config=r'--oem 3 --psm 6')
                        
                        combined_lcd = f"{raw_lcd_clahe}\n{raw_lcd_adaptive}"
                        detailed_rows, summary_dict = extract_lcd_metrics_detailed(combined_lcd)
                        
                        # ตรวจสอบว่าสกัดค่าสำเร็จหรือไม่
                        has_extracted_data = any(v != "-" for v in summary_dict.values())
                        
                        if has_extracted_data:
                            status_text = f"✅ ผ่าน (พบ {pac_type})"
                        else:
                            status_text = f"⚠️ พบป้าย {pac_type} แต่สกัดตัวเลขจอ LCD ไม่สำเร็จ"

                        # แสดงผลตารางเปรียบเทียบในรูปแบบแนวตั้งตามสั่งสำหรับแต่ละรูปภาพ
                        st.markdown(f"### 📁 ไฟล์: `{uploaded_file.name}` | สถานะ: **{status_text}**")
                        df_detail = pd.DataFrame(detailed_rows)
                        st.dataframe(df_detail, width="stretch", hide_index=True)
                        st.markdown("---")

                        # เก็บข้อมูลสำหรับส่งออก CSV
                        for row in detailed_rows:
                            all_detailed_export.append({
                                "ชื่อไฟล์": uploaded_file.name,
                                "ประเภทที่พบ": pac_type,
                                "รายการ (Mode / Operation)": row["รายการ (Mode / Operation)"],
                                "ค่าในรูปภาพดิบ": row["ค่าในรูปภาพดิบ"],
                                "ค่าที่สกัดได้ (ตัด 0 นำหน้า)": row["ค่าที่สกัดได้ (ตัด 0 นำหน้า)"]
                            })

                        row_summary = {
                            "ชื่อไฟล์": uploaded_file.name,
                            "ประเภทที่พบ": pac_type,
                            "สถานะ": status_text,
                        }
                        row_summary.update(summary_dict)
                        all_summary_data.append(row_summary)
                    
                    else:
                        # 🎯 เงื่อนไขข้อ 3: หากไม่ใช่ PAC 1 หรือ PAC 3 ไม่ต้องดึงข้อมูล
                        st.markdown(f"### 📁 ไฟล์: `{uploaded_file.name}` | สถานะ: **❌ ไม่ผ่าน (ไม่พบป้าย PAC 1 หรือ PAC 3 ในกรอบดำ)**")
                        st.info("ข้ามการดึงข้อมูลบนหน้าจอสีเขียว เนื่องจากไม่ตรงตามเงื่อนไขข้อ 1")
                        st.markdown("---")

                        all_summary_data.append({
                            "ชื่อไฟล์": uploaded_file.name,
                            "ประเภทที่พบ": "-",
                            "สถานะ": "❌ ไม่ผ่าน (ไม่พบป้าย PAC 1 หรือ PAC 3 ในกรอบดำ)"
                        })
                        
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาดกับไฟล์ {uploaded_file.name}: {str(e)}")

        # --- ปุ่มดาวน์โหลดไฟล์ CSV ---
        if all_summary_data or all_detailed_export:
            st.subheader("📥 ดาวน์โหลดข้อมูลสรุปผล")
            col_dl1, col_dl2 = st.columns(2)
            
            if all_detailed_export:
                df_det_export = pd.DataFrame(all_detailed_export)
                csv_det = df_det_export.to_csv(index=False).encode('utf-8-sig')
                with col_dl1:
                    st.download_button(
                        label="📥 ดาวน์โหลดตารางเปรียบเทียบ (แนวตั้ง)",
                        data=csv_det,
                        file_name="pac_detailed_comparison.csv",
                        mime="text/csv",
                        width="stretch"
                    )

            if all_summary_data:
                df_sum_export = pd.DataFrame(all_summary_data)
                csv_sum = df_sum_export.to_csv(index=False).encode('utf-8-sig')
                with col_dl2:
                    st.download_button(
                        label="📥 ดาวน์โหลดตารางสรุปผลรวม (แนวนอน)",
                        data=csv_sum,
                        file_name="pac_summary_report.csv",
                        mime="text/csv",
                        width="stretch"
                    )
