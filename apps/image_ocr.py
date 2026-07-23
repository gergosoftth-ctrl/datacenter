import streamlit as st
import pandas as pd
import re
from PIL import Image
import pytesseract

def run_app():
    st.title("🔍 ระบบอ่านตัวเลขจากรูปภาพ (Image OCR)")
    st.write("เวอร์ชันทดสอบ: อัปโหลดได้หลายรูปพร้อมกัน ดึงตัวเลขทั้งหมดเฉพาะรูปที่มีคำว่า PAC1 หรือ PAC3")

    # 1. ปรับช่องอัปโหลดให้รองรับหลายรูปพร้อมกันด้วย accept_multiple_files=True
    uploaded_files = st.file_uploader(
        "📥 เลือกไฟล์รูปภาพ (สามารถเลือกพร้อมกันได้หลายไฟล์):", 
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True
    )

    # เตรียมลิสต์ไว้เก็บข้อมูลของทุกรูปเพื่อแปลงเป็น CSV
    all_extracted_data = []

    if uploaded_files:
        st.markdown(f"📸 **กำลังประมวลผลรูปภาพทั้งหมด {len(uploaded_files)} ไฟล์...**")
        
        # วนลูปอ่านทีละรูปที่ยูสเซอร์อัปโหลดเข้ามา
        for uploaded_file in uploaded_files:
            try:
                # เปิดรูปภาพด้วย Pillow
                img = Image.open(uploaded_file)
                
                # สั่งให้ Pytesseract อ่านข้อความทั้งหมดในรูปออกมาเป็น String
                # (รองรับทั้งภาษาอังกฤษและตัวเลขเป็นหลัก)
                raw_text = pytesseract.image_to_string(img)
                
                # ตรวจเงื่อนไข: เช็คว่าในข้อความมีคำว่า PAC1 หรือ PAC5 หรือไม่ (ไม่สนพิมพ์เล็กพิมพ์ใหญ่)
                raw_text_lower = raw_text.lower()
                if "pac1" in raw_text_lower or "pac5" in raw_text_lower:
                    
                    # 🎯 ดึงตัวเลขทั้งหมดที่มีอยู่ในข้อความ (หาตัวเลขแบบต่อเนื่อง เช่น 123, 45.6)
                    numbers_found = re.findall(r'\d+(?:\.\d+)?', raw_text)
                    
                    # ถอดตัวเลขมารวมกันเป็นข้อความชุดเดียวคั่นด้วยเครื่องหมายจุลภาค (,) เพื่อให้ดูง่ายก่อน
                    numbers_combined = ", ".join(numbers_found) if numbers_found else "ไม่พบตัวเลขในภาพ"
                    
                    # เก็บผลลัพธ์ลงในลิสต์ข้อมูล
                    all_extracted_data.append({
                        "ชื่อไฟล์": uploaded_file.name,
                        "สถานะเงื่อนไข": "ผ่าน (พบ PAC1/PAC3)",
                        "ตัวเลขทั้งหมดที่พบ": numbers_combined,
                        "ข้อความดิบที่สแกนได้": raw_text.strip().replace('\n', ' ')
                    })
                else:
                    # ถ้ารูปนั้นไม่มีคำที่กำหนด ก็ข้ามไป หรือจะบันทึกไว้ว่าไม่ผ่านเงื่อนไขก็ได้ครับ
                    all_extracted_data.append({
                        "ชื่อไฟล์": uploaded_file.name,
                        "สถานะเงื่อนไข": "❌ ไม่ผ่าน (ไม่พบคำที่กำหนด)",
                        "ตัวเลขทั้งหมดที่พบ": "-",
                        "ข้อความดิบที่สแกนได้": "ข้ามการดึงตัวเลข"
                    })
                    
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดกับไฟล์ {uploaded_file.name}: {str(e)}")

        # --- ส่วนแสดงตารางผลลัพธ์และการดาวน์โหลด CSV ---
        if all_extracted_data:
            st.markdown("---")
            st.subheader("📋 ตารางสรุปผลข้อมูล")
            
            # แปลงข้อมูลเป็น DataFrame ของ Pandas เพื่อทำตารางและ CSV
            df = pd.DataFrame(all_extracted_data)
            
            # โชว์ตารางบนหน้าจอ Dashboard
            st.dataframe(df, use_container_width=True)
            
            # แปลงตารางเป็นไฟล์ CSV รูปแบบ UTF-8 รองรับภาษาไทย
            csv_data = df.to_csv(index=False).encode('utf-8-sig')
            
            # ปุ่มเสกไฟล์ดาวน์โหลด CSV ลงเครื่องคอมพิวเตอร์
            st.download_button(
                label="📥 ดาวน์โหลดข้อมูลทั้งหมดเป็น CSV",
                data=csv_data,
                file_name="ocr_extracted_numbers.csv",
                mime="text/csv",
                use_container_width=True
            )
            st.success("✨ ประมวลผลและเตรียมไฟล์ CSV สำเร็จเรียบร้อย!")
