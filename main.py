import streamlit as st
import pandas as pd
from supabase import create_client, Client

st.set_page_config(
    page_title="Data Center Dashboard",
    page_icon="🖥️",
    layout="wide"
)

# --- ฟังก์ชันดึงการเชื่อมต่อ Supabase ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["SUPABASE_URL"]
    key = st.secrets["supabase"]["SUPABASE_KEY"]
    return create_client(url, key)

# --- Sidebar Navigation ---
st.sidebar.title("📌 เมนูใช้งาน")

app_options = {
    "dashboard": "🏠 หน้าแรก (งานฝาก)",
    "deposit_job": "📦 ระบบงานฝาก (Supabase)",
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

# 🏠 1. หน้าแรก (ดึงข้อมูลจริงจาก Supabase)
if st.session_state.selected_app == "dashboard":
    st.title("🖥️ ระบบจัดการข้อมูล Data Center")
    st.write("ติดตามและจัดการรายการงานฝากทั้งหมดในระบบ")

    try:
        supabase = init_supabase()
        
        # ดึงข้อมูลทั้งหมดจากตาราง deposit_jobs
        response = supabase.table("deposit_jobs").select("*").order("id", desc=True).execute()
        jobs_data = response.data

        # --- คำนวณค่า Metric จากข้อมูลจริงใน DB ---
        total_count = len(jobs_data) if jobs_data else 0
        in_progress_count = sum(1 for j in jobs_data if j.get("status") == "กำลังดำเนินการ") if jobs_data else 0
        completed_count = sum(1 for j in jobs_data if j.get("status") == "เสร็จสิ้น") if jobs_data else 0

        # --- แสดงผลการคำนวณบน Metric Cards ---
        st.subheader("📦 สรุปสถานะงานฝาก")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(label="📥 งานฝากทั้งหมด", value=f"{total_count} รายการ")
        with col2:
            st.metric(label="⏳ กำลังดำเนินการ", value=f"{in_progress_count} รายการ")
        with col3:
            st.metric(label="✅ ดำเนินการเสร็จสิ้น", value=f"{completed_count} รายการ")

        st.markdown("---")
        st.subheader("📋 รายการงานฝากล่าสุด")

        # --- แสดงตารางข้อมูลจริงจาก DB ---
        if jobs_data:
            df = pd.DataFrame(jobs_data)
            
            # ปรับแต่งและเลือกเฉพาะคอลัมน์ที่ต้องการแสดง
            df_display = df.rename(columns={
                "job_code": "รหัสงาน",
                "title": "รายการ",
                "created_by": "ผู้ฝาก",
                "status": "สถานะ",
                "details": "รายละเอียด",
                "created_at": "วันที่สร้าง"
            })
            
            # ตกแต่งให้รูปแบบวันที่อ่านง่ายขึ้น
            if "วันที่สร้าง" in df_display.columns:
                df_display["วันที่สร้าง"] = pd.to_datetime(df_display["วันที่สร้าง"]).dt.strftime('%Y-%m-%d %H:%M')

            st.dataframe(
                df_display[["รหัสงาน", "รายการ", "ผู้ฝาก", "สถานะ", "รายละเอียด", "วันที่สร้าง"]], 
                width="stretch"
            )
        else:
            st.info("💡 ยังไม่มีข้อมูลงานฝากในระบบ สามารถไปที่เมนู '📦 ระบบงานฝาก' เพื่อเริ่มเพิ่มรายการได้เลยครับ")

    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาดในการเชื่อมต่อฐานข้อมูล: {str(e)}")
        st.info("💡 กรุณาตรวจสอบว่าตั้งค่า Secrets (SUPABASE_URL และ SUPABASE_KEY) เรียบร้อยแล้ว")

# 📦 2. เมนูงานฝาก (Supabase)
elif st.session_state.selected_app == "deposit_job":
    try:
        from apps import deposit_job
        deposit_job.run_app()
    except ModuleNotFoundError:
        st.error("❌ ไม่พบไฟล์ `deposit_job.py` ในโฟลเดอร์ `apps`")
        st.info("กรุณาตรวจสอบว่ามีไฟล์ `apps/deposit_job.py` บน GitHub เรียบร้อยแล้ว")

# 🧹 3. หน้า Text Cleaner
elif st.session_state.selected_app == "text_cleaner":
    try:
        from apps import text_cleaner
        text_cleaner.run_app()
    except ModuleNotFoundError:
        st.error("❌ ไม่พบไฟล์ `text_cleaner.py` ในโฟลเดอร์ `apps`")
        st.info("กรุณาตรวจสอบว่ามีไฟล์ `apps/text_cleaner.py` ใน GitHub เรียบร้อยแล้ว")
