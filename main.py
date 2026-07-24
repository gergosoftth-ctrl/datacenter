import streamlit as st

st.set_page_config(
    page_title="Data Center Dashboard",
    page_icon="🖥️",
    layout="wide"
)

# --- Sidebar Navigation ---
st.sidebar.title("📌 เมนูใช้งาน")

# รายการเมนูที่เหลือเปิดใช้งานปกติ (เอา image_ocr ออกแล้ว)
app_options = {
    "text_cleaner": "🧹 ระบบทำความสะอาดข้อความ (Text Cleaner)"
}

selected_app_key = st.sidebar.radio(
    "เลือกเครื่องมือที่ต้องการ:",
    options=list(app_options.keys()),
    format_func=lambda x: app_options[x]
)

# เก็บค่าลง session state
st.session_state.selected_app = selected_app_key

st.sidebar.markdown("---")
st.sidebar.info("💡 เลือกเครื่องมือจากเมนูด้านบนเพื่อเริ่มใช้งาน")

# --- Routing / Render Selected App ---
if st.session_state.selected_app == "text_cleaner":
    try:
        from apps import text_cleaner
        text_cleaner.run_app()
    except ModuleNotFoundError:
        st.error("❌ ไม่พบไฟล์ `text_cleaner.py` ในโฟลเดอร์ `apps`")
        st.info("กรุณาตรวจสอบว่ามีไฟล์ `apps/text_cleaner.py` ใน GitHub เรียบร้อยแล้ว")

else:
    st.title("ยินดีต้อนรับสู่ Data Center Dashboard 🖥️")
    st.write("กรุณาเลือกเมนูที่ต้องการใช้งานจากแถบเมนูด้านซ้ายมือ")
