import streamlit as st
import re

def run_app():
    st.title("🧹 เครื่องมือจัดเรียงและทำความสะอาดข้อความ")
    st.write("ระบบจะลบเครื่องหมาย ~, \", อักขระพิเศษต่างดาว และบรรทัดว่างออกให้โดยอัตโนมัติ")

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
            
            # เคลียร์รอบสุดท้าย: ไล่ดูทีละบรรทัด ตัดช่องว่างหัวท้าย และลบบรรทัดที่ว่างทิ้งไป
            lines = [line.strip() for line in cleaned_text.split('\n')]
            # กรองเอาเฉพาะบรรทัดที่มีข้อความจริงๆ (ไม่เป็นค่าว่าง)
            non_empty_lines = [line for line in lines if line]
            
            # ประกอบข้อความกลับมาโดยคั่นด้วยการขึ้นบรรทัดใหม่
            cleaned_text = '\n'.join(non_empty_lines)
        
        # กล่องแสดงผลลัพธ์ที่ทำความสะอาดและจัดเรียงแถวใหม่แล้ว
        st.text_area("ข้อความที่ทำความสะอาดแล้ว:", value=cleaned_text, height=280)
        
        if input_text:
            st.success("✨ ทำความสะอาด 3 เงื่อนไข และจัดเรียงบรรทัดใหม่เรียบร้อย!")
