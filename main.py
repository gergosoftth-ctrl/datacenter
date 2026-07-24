import streamlit as st

st.set_page_config(
    page_title="Data Center Dashboard",
    page_icon="🖥️",
    layout="wide"
)

# --- Sidebar Navigation ---
st.sidebar.title("📌 เมนูใช้งาน")

app_options = {
    "dashboard": "🏠 หน้าแรก & ค้นหางานฝาก",
    "text_cleaner": "🧹 ระบบทำความสะอาดข้อความ (Text Cleaner)"
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

# 🏠 1. หน้าแรก & ค้นหางานฝาก
if st.session_state.selected_app == "dashboard":
    st.title("🖥️ ระบบจัดการข้อมูล Data Center")
    st.write("ยินดีต้อนรับสู่ระบบค้นหาและติดตามงานฝาก")

    # --- โซนค้นหา (Search Zone) ---
    st.subheader("🔍 ค้นหาข้อมูลงาน")
    col_search1, col_search2 = st.columns([3, 1])
    
    with col_search1:
        search_query = st.text_input("พิมพ์คำค้นหา (เช่น ชื่ออุปกรณ์, เลข PAC, หรือรหัสงาน):", placeholder="กรอกคำค้นหาที่นี่...")
    with col_search2:
        search_category = st.selectbox("หมวดหมู่:", ["ทั้งหมด", "งานฝาก", "อุปกรณ์", "สถานะ"])

    if search_query:
        st.success(f"🔎 ผลการค้นหาสำหรับ: '{search_query}' (หมวดหมู่: {search_category})")
        # สามารถเชื่อมต่อการดึงข้อมูลจาก Database หรือ DataFrame ได้ตรงนี้
    
    st.markdown("---")

    # --- โซนกล่องงานฝาก (Pending Tasks / Deposit Box) ---
    st.subheader("📦 กล่องงานฝาก / งานรอการประมวลผล")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(label="📥 งานฝากทั้งหมด", value="12 รายการ", delta="2 รายการวันนี้")
    with col2:
        st.metric(label="⏳ กำลังดำเนินการ", value="5 รายการ", delta="-1 รายการ")
    with col3:
        st.metric(label="✅ ดำเนินการเสร็จสิ้น", value="7 รายการ", delta="+3 รายการ")

    st.markdown("### 📋 รายการงานฝากล่าสุด")
    
    # ตัวอย่างตารางกล่องงานฝาก
    sample_data = [
        {"ID": "JOB-001", "รายการ": "ตรวจสอบตู้แอร์ PAC 1", "ผู้ฝาก": "ช่าง A", "สถานะ": "กำลังดำเนินการ", "วันที่": "2026-07-24"},
        {"ID": "JOB-002", "รายการ": "ทำความสะอาดข้อมูล Log", "ผู้ฝาก": "ช่าง B", "สถานะ": "เสร็จสิ้น", "วันที่": "2026-07-24"},
        {"ID": "JOB-003", "รายการ": "เช็คสถานะไฟสำรอง UPS", "ผู้ฝาก": "ช่าง C", "สถานะ": "รอดำเนินการ", "วันที่": "2026-07-23"},
    ]
    st.dataframe(sample_data, width="stretch")

# 🧹 2. หน้า Text Cleaner
elif st.session_state.selected_app == "text_cleaner":
    try:
        from apps import text_cleaner
        text_cleaner.run_app()
    except ModuleNotFoundError:
        st.error("❌ ไม่พบไฟล์ `text_cleaner.py` ในโฟลเดอร์ `apps`")
        st.info("กรุณาตรวจสอบว่ามีไฟล์ `apps/text_cleaner.py` ใน GitHub เรียบร้อยแล้ว")
