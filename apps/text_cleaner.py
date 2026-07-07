import streamlit as st
import re

def run_app():
    st.title("🧹 เครื่องมือจัดเรียงและทำความสะอาดข้อความ")
    st.write("วางข้อความดิบของคุณลงในกล่องด้านล่าง เลือกตัวกรอง จากนั้นนำข้อความที่สะอาดแล้วไปใช้ได้ทันที")

    # แบ่งหน้าจอเป็น 2 คอลัมน์ (ซ้าย: กล่องรับข้อมูล/ควบคุม , ขวา: ผลลัพธ์)
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📥 ข้อมูลเข้าและตั้งค่า")
        input_text = st.text_area("วางข้อความดิบที่นี่:", height=200)
        
        # ตัวเลือกการกรองข้อมูล
        st.markdown("**ตัวเลือกการทำความสะอาด:**")
        remove_special = st.checkbox("ลบอักขระพิเศษ (เหลือแค่ข้อความทั่วไปและช่องว่าง)", value=True)
        remove_numbers = st.checkbox("ลบตัวเลข")
        remove_empty = st.checkbox("ลบบรรทัดว่างและจัดระเบียบ", value=True)

    with col2:
        st.subheader("📤 ผลลัพธ์")
        
        # ประมวลผลข้อมูล
        cleaned_text = input_text
        
        if input_text:
            if remove_special:
                # ลบอักขระพิเศษ ยกเว้นภาษาไทย ภาษาอังกฤษ ตัวเลข และช่องว่าง
                cleaned_text = re.sub(r'[^a-zA-Z0-9ก-๙\s]', '', cleaned_text)
            
            if remove_numbers:
                cleaned_text = re.sub(r'[0-9]', '', cleaned_text)
                
            if remove_empty:
                # ตัดช่องว่างหัวท้ายบรรทัด และคัดแยกบรรทัดที่ว่างออก
                lines = [line.strip() for line in cleaned_text.split('\n') if line.strip()]
                cleaned_text = '\n'.join(lines)
        
        # กล่องแสดงผลลัพธ์
        st.text_area("ข้อความที่คลีนเรียบร้อยแล้ว:", value=cleaned_text, height=200, disabled=False)
        
        if cleaned_text:
            st.success("✨ ประมวลผลสำเร็จ!")