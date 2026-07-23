import streamlit as st
import pandas as pd
import re
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
import pytesseract

def preprocess_header_black_label(crop_img):
    """ปรับแต่งและกลับสีป้ายสีดำตัวหนังสือขาว"""
    gray = crop_img.convert('L')
    inverted = ImageOps.invert(gray)
    enhancer = ImageEnhance.Contrast(inverted)
    return enhancer.enhance(2.5)

def preprocess_header_normal(crop_img):
    """ปรับแต่งป้ายสีปกติ (ไม่กลับสี)"""
    gray = crop_img.convert('L')
    enhancer = ImageEnhance.Contrast(gray)
    return enhancer.enhance(2.0)

def preprocess_lcd_fast(crop_img):
    """ปรับแต่งภาพหน้าจอ LCD แบบเบาพิเศษ (ประมวลผลไว ไม่กิน CPU)"""
    img_np = np.array(crop_img)
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    
    # ขยายรูปเล็กน้อยพอให้อ่านออก (1.5 เท่า) เพื่อลดภาระการคำนวณ
    resized = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_LINEAR)
    
    # เร่ง Contrast คมชัดแบบสเปกเบา
    enhanced = cv2.equalizeHist(resized)
    return enhanced

def extract_lcd_metrics(raw_lcd_text):
    """สกัดจับคู่ Key-Value หัวข้อและตัวเลขชั่วโมง"""
    metrics = {}
    
    labels = [
        "Active Operation",
        "Cool Mode",
        "Heat Mode",
        "Humidify Mode",
        "De-Humidify Mode",
        "Fan Operation",
        "Cool 1 Operation",
        "Cool 2 Operation",
        "Heat 1 Operation",
        "Heat 2 Operation",
        "Humidifier Operation"
    ]
    
    for label in labels:
        pattern = re.escape(label).replace(r'\ ', r'\s*') + r'.*?\b0*(\d+)\s*(?:hrs)?'
        match = re.search(pattern, raw_lcd_text, re.IGNORECASE)
        if match:
            value = match.group(1)
            metrics[label] = int(value) if value else 0
            
    return metrics

def detect_pac_type(filename, header_crop):
    """
    ตรวจสอบระบุประเภท PAC 1 หรือ PAC 3
    ลำดับการตรวจสอบ:
    1. จากชื่อไฟล์ (เช่น PAC1_2026.jpg, PAC 3.png)
    2. จากป้ายส่วนหัว (แบบกลับสีสำหรับป้ายดำ)
    3. จากป้ายส่วนหัว (แบบปกติสำหรับป้ายสว่าง)
    """
    # 1. ตรวจสอบจากชื่อไฟล์ก่อน
    fn_match = re.search(r'pac\s*[-_.]?\s*([13])\b', filename, re.IGNORECASE)
    if fn_match:
        return f"PAC {fn_match.group(1)}", "ตรวจพบจากชื่อไฟล์"

    # 2. สแกนป้ายส่วนหัว (แบบกลับสี)
    inverted_header = preprocess_header_black_label(header_crop)
    text_inv = pytesseract.image_to_string(inverted_header, config=r'--oem 3 --psm 6')

    # 3. สแกนป้ายส่วนหัว (แบบไม่กลับสี)
    normal_header = preprocess_header_normal(header_crop)
    text_norm = pytesseract.image_to_string(normal_header, config=r'--oem 3 --psm 6')

    combined_text = f"{text_inv}\n{text_norm}"

    # รูปแบบ Regex ที่ยืดหยุ่นขึ้น (รองรับ PAC1, PAC 1, PAC-1, PAC_1, P4C1, ฯลฯ)
    has_pac1 = bool(re.search(r'p[a4]c\s*[-_.]?\s*[1lI|]\b', combined_text, re.IGNORECASE))
    has_pac3 = bool(re.search(r'p[a4]c\s*[-_.]?\s*3\b', combined_text, re.IGNORECASE))

    if has_pac1 and not has_pac3:
        return "PAC 1", "ตรวจพบจากป้ายรูปภาพ"
    elif has_pac3 and not has_pac1:
        return "PAC 3", "ตรวจพบจากป้ายรูปภาพ"
    elif has_pac1 and has_pac3:
        return "PAC 1 / PAC 3", "ตรวจพบจากป้ายรูปภาพ"

    return "-", f"ข้อความป้ายส่วนหัวที่อ่านได้: '{combined_text.strip()}'"

def run_app():
    st.title("🔍 ระบบอ่านตัวเลขจากรูปภาพ PAC 1 / PAC 3")
    st.caption("เวอร์ชันปรับแต่งความแม่นยำและการตรวจจับป้าย PAC 1 / PAC 3")

    col_opt1, col_opt2 = st.columns([2, 1])
    with col_opt1:
        force_scan_lcd = st.checkbox("🔓 อนุญาตให้อ่านหน้าจอ LCD ทุกรูป (แม้อ่านป้าย PAC ไม่เจอ)", value=True)
    
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

                    # 🎯 โซน 1: Crop ป้าย PAC ด้านบน (ขยายความสูงเป็น 40% เผื่อตำแหน่งรูปถ่าย)
                    header_crop = original_img.crop((0, 0, width, int(height * 0.40)))
                    pac_found_type, pac_note = detect_pac_type(uploaded_file.name, header_crop)

                    is_pac_detected = pac_found_type != "-"

                    # 🎯 โซน 2: Crop หน้าจอ LCD สีเขียว
                    if is_pac_detected or force_scan_lcd:
                        lcd_crop = original_img.crop((int(width * 0.15), int(height * 0.35), int(width * 0.85), int(height * 0.75)))
                        processed_lcd = preprocess_lcd_fast(lcd_crop)
                        
                        # สแกนอ่านข้อความ LCD
                        lcd_raw_text = pytesseract.image_to_string(processed_lcd, config=r'--oem 3 --psm 6')
                        metrics = extract_lcd_metrics(lcd_raw_text)
                        
                        if metrics:
                            formatted_metrics = " | ".join([f"{k} = {v}" for k, v in metrics.items()])
                            status_text = "✅ ผ่าน (" + (pac_found_type if is_pac_detected else "อ่านจอ LCD สำเร็จ") + ")"
                        else:
                            formatted_metrics = "สแกนจอ LCD แล้ว แต่จับคู่ค่าชั่วโมงไม่สำเร็จ"
                            status_text = "⚠️ พบรูป (" + pac_found_type + ") แต่สกัดค่า LCD ไม่ครบ"

                        row_data = {
                            "ชื่อไฟล์": uploaded_file.name,
                            "ประเภทที่พบ": pac_found_type,
                            "ที่มาของประเภท": pac_note,
                            "สถานะ": status_text,
                            "สรุปค่าบนหน้าจอ LCD": formatted_metrics,
                            "ข้อความดิบ LCD": lcd_raw_text.strip()
                        }
                        
                        for k, v in metrics.items():
                            row_data[k] = v

                        all_extracted_data.append(row_data)
                    else:
                        all_extracted_data.append({
                            "ชื่อไฟล์": uploaded_file.name,
                            "ประเภทที่พบ": "-",
                            "ที่มาของประเภท": pac_note,
                            "สถานะ": "❌ ไม่ผ่าน (ไม่พบป้าย PAC 1 หรือ PAC 3)",
                            "สรุปค่าบนหน้าจอ LCD": "-",
                            "ข้อความดิบ LCD": "ข้ามการอ่าน"
                        })
                        
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาดกับไฟล์ {uploaded_file.name}: {str(e)}")

        # --- แสดงตารางผลลัพธ์ ---
        if all_extracted_data:
            st.markdown("---")
            st.subheader("📋 ตารางสรุปผลข้อมูล")
            
            df = pd.DataFrame(all_extracted_data)
            display_cols = ["ชื่อไฟล์", "ประเภทที่พบ", "ที่มาของประเภท", "สถานะ", "สรุปค่าบนหน้าจอ LCD"]
            st.dataframe(df[display_cols], width="stretch")
            
            with st.expander("🔍 คลิกเพื่อดูรายละเอียดข้อความดิบและผลการตรวจจับ"):
                for idx, row in df.iterrows():
                    st.write(f"📁 **{row['ชื่อไฟล์']}** | ประเภท: `{row['ประเภทที่พบ']}` ({row['ที่มาของประเภท']})")
                    st.code(f"--- ข้อความดิบ LCD ---\n{row['ข้อความดิบ LCD']}")
                    st.markdown("---")
            
            csv_data = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 ดาวน์โหลดข้อมูลสรุปทั้งหมดเป็น CSV",
                data=csv_data,
                file_name="pac_lcd_metrics.csv",
                mime="text/csv",
                width="stretch"
            )
