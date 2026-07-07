import streamlit as st

# ตั้งค่าหน้าจอ Dashboard
st.set_page_config(page_title="Data Center Dashboard", layout="wide")

st.sidebar.title("Data Center Tools")
st.sidebar.write("เลือก Tool ที่ต้องการใช้งานด้านล่าง:")

# เมนูสำหรับเลือกแอป (ในอนาคตสามารถมาเพิ่มรายชื่อตรงนี้ได้เลย)
app_mode = st.sidebar.radio(
    "Tools:",
    ["🧹 ร่างข้อความ incident", "➕ แอปอื่น ๆ ในอนาคต"]
)

# เรียกใช้งานแอปตามที่ยูสเซอร์เลือก
if app_mode == "🧹 ร่างข้อความ incident":
    # ดึงโค้ดจากไฟล์แอปย่อยมาทำงาน
    from apps import text_cleaner
    text_cleaner.run_app()
    
elif app_mode == "➕ แอปอื่น ๆ ในอนาคต":
    st.title("🚧 กำลังพัฒนา")
    st.write("รอไปก่อนตอนนี้ขี้เกียจ zZ")
