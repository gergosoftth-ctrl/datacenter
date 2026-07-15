import streamlit as st
import re

def run_app():
    st.title("🧹 เครื่องมือจัดเรียงและทำความสะอาดข้อความ")
    st.write("ระบบจะลบเครื่องหมาย ~, \", อักขระพิเศษต่างดาว และบรรทัดว่างออกให้โดยอัตโนมัติ (พร้อมเว้นบรรทัดก่อนหน้าข้อความ OPEN Problem)")

    # แบ่งหน้าจอเป็น 2 คอลัมน์ (ซ้าย: อินพุต , ขวา: เอาต์พุต)
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📥 ข้อมูลเข้า")
        input_text = st.text_area(
            "วางข้อความดิบที่นี่:", 
            height=280, 
            placeholder="วางข้อความที่มี ~ , \" หรือสัญลักษณ์ปริศนาลงไปได้เลย..."
        )

    with col2:
        st.subheader("📤 ผลลัพธ์")
        
        cleaned_text = input_text
        
        if input_text:
            # เงื่อนไขที่ 1: ลบเครื่องหมาย ~
            cleaned_text = cleaned_text.replace('~', '')
            
            # เงื่อนไขที่ 2: ลบเครื่องหมาย "
            cleaned_text = cleaned_text.replace('"', '')
            
            # เงื่อนไขที่ 3: ลบอักขระพิเศษกลุ่มต่างดาว (Private Use Areas: U+E000 ถึง U+F8FF)
            cleaned_text = re.sub(r'[\uE000-\uF8FF]', '', cleaned_text)
            
            # --- เริ่มขั้นตอนการจัดระเบียบบรรทัดตามเงื่อนไขพิเศษ ---
            # 1. แตกข้อความออกมาดูทีละบรรทัด และลบช่องว่างส่วนเกินหัวท้ายออก
            raw_lines = [line.strip() for line in cleaned_text.split('\n')]
            
            # 2. กรองเอาเฉพาะบรรทัดที่มีข้อความจริง ๆ ออกมาก่อน (ลบบรรทัดว่างเดิมออกให้เกลี้ยง)
            filtered_lines = [line for line in raw_lines if line]
            
            # 3. ลูปตรวจเช็คเพื่อแทรกบรรทัดว่างกลับคืนเฉพาะจุด
            final_lines = []
            for line in filtered_lines:
                # เช็คว่าบรรทัดนี้ขึ้นต้นด้วยคำว่า "OPEN Problem P-" หรือไม่ (ตัวเล็ก/ตัวใหญ่จับได้หมด)
                if line.lower().startswith("open problem p-"):
                    # ถ้าไม่ใช่บรรทัดแรกสุดของข้อความทั้งหมด ให้แอบใส่ค่าว่างเข้าไปก่อนหน้า 1 บรรทัด
                    if final_lines:
                        final_lines.append("") 
                
                final_lines.append(line)
            
            # ประกอบข้อความทั้งหมดกลับคืนมา
            cleaned_text = '\n'.join(final_lines)
        
        # กล่องแสดงผลลัพธ์ที่ทำความสะอาดและจัดเรียงแถวใหม่แล้ว
        st.text_area("ข้อความที่ทำความสะอาดแล้ว:", value=cleaned_text, height=280)
        
        if input_text:
            st.success("✨ ทำความสะอาด จัดเรียงบรรทัด และเว้นวรรคกลุ่ม OPEN Problem ให้เรียบร้อยแล้ว!")
