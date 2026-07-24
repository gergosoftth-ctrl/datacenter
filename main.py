import streamlit as st

st.set_page_config(
    page_title="Data Center Dashboard",
    page_icon="🖥️",
    layout="wide"
)

# --- Sidebar Navigation ---
st.sidebar.title("📌 เมนูใช้งาน")

app_options = {
    "dashboard": "🏠 หน้าแรก (งานฝาก)",
    "deposit_job": "📦 ระบบงานฝาก (ระบบใหม่)",
    "text_cleaner": "🧹 ร่าง Incident" #(Text Cleaner)
}

selected_app_key = st.sidebar.radio(
    "เลือกเครื่องมือที่ต้องการ:",
    options=list(app_options.keys()),
    format_func=lambda x: app_options[x]
)

st.session_state.selected_app = selected_app_key

st.sidebar.markdown("---")
st.sidebar.info("💡 เลือกเครื่องมือจากเมนูด้านบนเพื่อเริ่มใช้งาน")

# --- Routing / Render Selected App ---

# 🏠 1. หน้าแรก (เน้นเฉพาะกล่องงานฝาก)
if st.session_state.selected_app == "dashboard":
    st.title("🖥️ ระบบจัดการข้อมูล Data Center")
    st.write("ติดตามและจัดการรายการงานฝากทั้งหมด")

    # --- โซนกล่องงานฝาก (Deposit Box / Pending Tasks) ---
    st.subheader("📦 สรุปสถานะงานฝาก")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(label="📥 งานฝากทั้งหมด", value="12 รายการ", delta="2 รายการวันนี้")
    with col2:
        st.metric(label="⏳ กำลังดำเนินการ", value="5 รายการ", delta="-1 รายการ")
    with col3:
        st.metric(label="✅ ดำเนินการเสร็จสิ้น", value="7 รายการ", delta="+3 รายการ")

    st.markdown("---")
    st.subheader("📋 รายการงานฝากล่าสุด")
    
    # ตัวอย่างตารางแสดงรายการงานฝาก
    sample_data = [
        {"ID": "JOB-001", "รายการ": "ตรวจสอบตู้แอร์ PAC 1", "ผู้ฝาก": "ช่าง A", "สถานะ": "กำลังดำเนินการ", "วันที่": "2026-07-24"},
        {"ID": "JOB-002", "รายการ": "ทำความสะอาดข้อมูล Log", "ผู้ฝาก": "ช่าง B", "สถานะ": "เสร็จสิ้น", "วันที่": "2026-07-24"},
        {"ID": "JOB-003", "รายการ": "เช็คสถานะไฟสำรอง UPS", "ผู้ฝาก": "ช่าง C", "สถานะ": "รอดำเนินการ", "วันที่": "2026-07-23"},
    ]
    st.dataframe(sample_data, width="stretch")

# 📦 2. เมนูงานฝาก (ระบบใหม่ - รอการกำหนดฟังก์ชัน)
elif st.session_state.selected_app == "deposit_job":
    st.title("📦 ระบบงานฝาก")
    st.info("🚧 ฟังก์ชันนี้กำลังอยู่ระหว่างการพัฒนา (เตรียมไว้สำหรับกำหนดรายละเอียดเพิ่มในขั้นตอนถัดไป)")

# 🧹 3. หน้า Text Cleaner
elif st.session_state.selected_app == "text_cleaner":
    try:
        from apps import text_cleaner
        text_cleaner.run_app()
    except ModuleNotFoundError:
        st.error("❌ ไม่พบไฟล์ `text_cleaner.py` ในโฟลเดอร์ `apps`")
        st.info("กรุณาตรวจสอบว่ามีไฟล์ `apps/text_cleaner.py` ใน GitHub เรียบร้อยแล้ว")
