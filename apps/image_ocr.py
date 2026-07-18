import streamlit as st

def run_app():
    st.title("🔍 ระบบอ่านตัวเลขจากรูปภาพ (Image OCR)")
    st.write("อัปโหลดไฟล์รูปภาพของคุณเพื่อทำการแปลงข้อมูลและจัดเรียงเป็นตาราง CSV")

    # ส่วนอัปโหลดรูป
    uploaded_file = st.file_uploader("📥 เลือกไฟล์รูปภาพ (PNG, JPG, JPEG):", type=["png", "jpg", "jpeg"])

    if uploaded_file is not None:
        # แสดงรูปภาพที่อัปโหลด
        st.image(uploaded_file, caption="รูปภาพที่อัปโหลดเข้ามา", use_container_width=True)
        
        st.info("🚧 ระบบได้รับรูปภาพเรียบร้อยแล้ว รอรับเงื่อนไขในการดึงตัวเลขและจัดเรียงคอลัมน์ในสเต็ปถัดไป")
        
        # ตัวอย่างโครงตารางผลลัพธ์ที่จะโชว์ในอนาคต
        st.subheader("📋 ตัวอย่างผลลัพธ์ที่จะส่งออกเป็น CSV")
        st.warning("เมื่อกำหนดเงื่อนไขแล้ว ตารางข้อมูลจะแสดงตรงนี้พร้อมปุ่มดาวน์โหลดไฟล์ทันทีครับ")
