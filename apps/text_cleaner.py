import streamlit as st

def run_app():
    st.title("🧹 เครื่องมือจัดเรียงและทำความสะอาดข้อความ")
    st.write("วางข้อความดิบที่มีเครื่องหมายหนอน (~) หรืออัญประกาศ (\") เพื่อลบออกและจัดรูปแบบให้เรียบร้อย")

    # แบ่งหน้าจอเป็น 2 คอลัมน์ (ซ้าย: อินพุต , ขวา: เอาต์พุต)
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📥 ข้อมูลเข้า")
        input_text = st.text_area("วางข้อความดิบที่นี่:", height=250, placeholder="ตัวอย่าง: ~ข้อความนี้มี \"เครื่องหมาย\" ที่ไม่ต้องการ~")
        
        # เพิ่มตัวเลือกเสริมสำหรับจัดระเบียบบรรทัด
        st.markdown("**การจัดเรียงเพิ่มเติม:**")
        remove_empty = st.checkbox("ลบบรรทัดว่างที่ไม่มีข้อความ", value=True)

    with col2:
        st.subheader("📤 ผลลัพธ์")
        
        cleaned_text = input_text
        
        if input_text:
            # 1. ลบเครื่องหมาย ~ ออกทั้งหมด
            cleaned_text = cleaned_text.replace('~', '')
            
            # 2. ลบเครื่องหมาย " ออกทั้งหมด
            cleaned_text = cleaned_text.replace('"', '')
            
            # 3. จัดการเรื่องบรรทัดว่าง (ถ้าติ๊กเลือกไว้)
            if remove_empty:
                lines = [line.strip() for line in cleaned_text.split('\n') if line.strip()]
                cleaned_text = '\n'.join(lines)
        
        # กล่องแสดงผลลัพธ์ที่ทำความสะอาดแล้ว
        st.text_area("ข้อความที่ทำความสะอาดแล้ว:", value=cleaned_text, height=250)
        
        if input_text:
            st.success("✨ ลบเครื่องหมาย ~ และ \" ออกเรียบร้อยแล้ว!")
