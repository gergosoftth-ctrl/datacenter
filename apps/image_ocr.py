import streamlit as st
import pandas as pd
import re
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
import pytesseract

def preprocess_header_black_label(crop_img):
    """ปรับแต่งและแปลงป้ายสีดำตัวหนังสือขาว ให้คมชัด"""
    gray = np.array(crop_img.convert('L'))
    inverted = cv2.bitwise_not(gray)
    _, thresh = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(thresh)

def preprocess_lcd_clahe(crop_img):
    """ปรับแต่งหน้าจอ LCD สีเขียวด้วย CLAHE (ถนอมตัวหนังสือ Dot-matrix ไม่ให้แตกเป็นจุดรบกวน)"""
    img_np = np.array(crop_img)
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    
    # ขยายรูป 1.8 เท่า
    resized = cv2.resize(gray, None, fx=1.8, fy=1.8, interpolation=cv2.INTER_CUBIC)
    
    # ใช้ CLAHE ช่วยปรับความสว่างและคมชัดของตัวหนังสือ Dot-matrix
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(resized)
    
    return Image.fromarray(enhanced)

def check_black_label_pac(header_crop):
    """
    เงื่อนไขข้อ 1: ตรวจหาว่าใช่ PAC 1 หรือ PAC 3 จากป้ายกรอบดำตัวหนังสือขาวส่วนหัวเท่านั้น
    """
    processed_header = preprocess_header_black_label(header_crop)
    
    # สแกนด้วย PSM 11, PSM 6 และ PSM 3 เพื่อเก็บข้อความครบทุกบรรทัด
    t11 = pytesseract.image_to_string(processed_header, config=r'--oem 3 --psm 11')
    t6 = pytesseract.image_to_string(processed_header, config=r'--oem 3 --psm 6')
    t3 = pytesseract.image_to_string(processed_header, config=r'--oem 3 --psm 3')
    
    raw_text = f"{t11}\n{t6}\n{t3}"
    
    # รวมข้อความ บรรทัด และลบอักขระพิเศษเพื่อทำความสะอาดก่อนสแกน Regex
    clean_text = re.sub(r'[\r\n\t]+', ' ', raw_text)
    clean_text = re.sub(r'[^a-zA-Z0-9\s]', ' ', clean_text)
    clean_text = re.sub(r'\s+', ' ', clean_text)

    # เช็คเฉพาะ PAC 1 และ PAC 3 (รองรับ PAC 1, PAC1, PAC 001003, PAC 3, PAC3 ฯลฯ)
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
    เงื่อนไขข้อ 2: สกัดเฉพาะตัวเลขจากจอสีเขียว และตัดเลข 0 ข้างหน้าออก (เช่น 004674 -> 4674, 000000 -> 0)
    """
    metrics = {}
    
    # รายการ Label บนหน้าจอ LCD และ Regex ยืดหยุ่นรองรับการอ่านเพี้ยนของ OCR
    labels_config = [
        ("Active Operation", r"Acti[vea]?\s*O[pe]rat[io]n"),
        ("Cool Mode", r"Cool\s*Mode"),
        ("Heat Mode", r"Heat\s*Mode"),
        ("Humidify Mode", r"Humidif[y|ier]\s*Mode"),
        ("De-Humidify Mode", r"De-?\s*Humidif[y|ier]\s*Mode"),
        ("Fan Operation", r"Fan\s*O[pe]rat[io]n"),
        ("Cool 1 Operation", r"Cool\s*1\s*O[pe]rat[io]n"),
        ("Cool 2 Operation", r"Cool\s*2\s*O[pe]rat[io]n"),
        ("Heat 1 Operation", r"Heat\s*1\s*O[pe]rat[io]n"),
        ("Heat 2 Operation", r"Heat\s*2\s*O[pe]rat[io]n"),
        ("Heater 1 Operation", r"Heater\s*1\s*O[pe]rat[io]n"),
        ("Heater 2 Operation", r"Heater\s*2\s*O[pe]rat[io]n"),
        ("Humidifier Operation", r"Humidifi[er]?\s*O[pe]rat[io]n"),
    ]
    
    lines = raw_lcd_text.split('\n')
    
    for label_title, pattern in labels_config:
        for line in lines:
            if re.search(pattern, line, re.IGNORECASE):
                # ค้นหาชุดตัวเลขหลังคำอธิบาย
                # 0*(\d+) ช่วยละทิ้งเลข 0 ที่นำหน้า เช่น 004674 -> ได้ 4674, 000000 -> ได้ 0
                num_match = re.search(r'[:\s]+0*(\d+)\s*(?:hrs)?', line, re.IGNORECASE)
                if num_match:
                    val_str = num_match.group(1)
                    val_int = int(val_str)
                    metrics[label_title] = val_int
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

                    # 🎯 โซน 1: Crop ป้ายกรอบดำตัวหนังสือขาวด้านบน (40% ด้านบน)
                    header_crop = original_img.crop((0, 0, width, int(height * 0.40)))
                    pac_type, raw_header_text = check_black_label_pac(header_crop)

                    # 🎯 เงื่อนไขข้อ 1 & 3: หากพบ PAC 1 หรือ PAC 3 จากป้ายกรอบดำ ให้ดึงข้อมูลบนจอสีเขียว
                    if pac_type is not None:
                        # Crop หน้าจอ LCD สีเขียว
                        lcd_crop = original_img.crop((int(width * 0.15), int(height * 0.35), int(width * 0.85), int(height * 0.75)))
                        processed_lcd = preprocess_lcd_clahe(lcd_crop)
                        
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
