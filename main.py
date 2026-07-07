import streamlit as st

# ตั้งค่าหน้าจอ Dashboard
st.set_page_config(page_title="Data Center Dashboard", layout="wide")

st.sidebar.title("🚀 ศูนย์รวมแอปพลิเคชัน")
st.sidebar.write("เลือกเครื่องมือที่ต้องการใช้งานด้านล่าง:")

# เมนูสำหรับเลือกแอป (ในอนาคตสามารถมาเพิ่มรายชื่อตรงนี้ได้เลย)
app_mode = st.sidebar.radio(
    "แอปที่มีให้ใช้งาน:",
    ["🧹 เครื่องมือจัดการข้อความ (Text Cleaner)", "➕ แอปอื่น ๆ ในอนาคต"]
)

# เรียกใช้งานแอปตามที่ยูสเซอร์เลือก
if app_mode == "🧹 เครื่องมือจัดการข้อความ (Text Cleaner)":
    # ดึงโค้ดจากไฟล์แอปย่อยมาทำงาน
    from apps import text_cleaner
    text_cleaner.run_app()
    
elif app_mode == "➕ แอปอื่น ๆ ในอนาคต":
    st.title("🚧 กำลังพัฒนา")
    st.write("พื้นที่นี้รองรับสำหรับแอปพลิเคชันใหม่ของคุณในอนาคต สามารถเพิ่มเข้ามาได้เรื่อย ๆ ครับ!")
