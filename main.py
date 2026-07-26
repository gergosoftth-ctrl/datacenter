import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
from supabase import create_client, Client

TZ_TH = pytz.timezone('Asia/Bangkok')

st.set_page_config(
    page_title="Data Center Dashboard",
    page_icon="🖥️",
    layout="wide"
)

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
    "dynatrace_monitor": "🚨 Monitor Alarm (Dynatrace)",
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

# --- Routing ---

# 🏠 1. หน้าแรก
if st.session_state.selected_app == "dashboard":
    st.title("🖥️ ระบบจัดการข้อมูล Data Center")
    st.write("ติดตามและจัดการรายการงานฝากทั้งหมดในระบบ")

    try:
        supabase = init_supabase()
        now_iso = datetime.now(TZ_TH).isoformat()
        response = supabase.table("deposit_jobs").select("*").gte("end_date", now_iso).order("id", desc=True).execute()
        jobs_data = response.data

        total_count = len(jobs_data) if jobs_data else 0
        in_progress_count = sum(1 for j in jobs_data if j.get("status") == "กำลังดำเนินการ") if jobs_data else 0
        completed_count = sum(1 for j in jobs_data if j.get("status") == "เสร็จสิ้น") if jobs_data else 0

        st.subheader("📦 สรุปสถานะงานฝากปัจจุบัน")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(label="📥 งานฝากทั้งหมด", value=f"{total_count} รายการ")
        with col2:
            st.metric(label="⏳ กำลังดำเนินการ", value=f"{in_progress_count} รายการ")
        with col3:
            st.metric(label="✅ ดำเนินการเสร็จสิ้น", value=f"{completed_count} รายการ")

        st.markdown("---")
        st.subheader("📋 รายการงานฝากที่กำลังรันอยู่")

        if jobs_data:
            df = pd.DataFrame(jobs_data)
            if "start_date" in df.columns and "end_date" in df.columns:
                df["Start Date"] = pd.to_datetime(df["start_date"]).dt.tz_convert('Asia/Bangkok').dt.strftime('%d-%m-%Y %H:%M')
                df["End Date"] = pd.to_datetime(df["end_date"]).dt.tz_convert('Asia/Bangkok').dt.strftime('%d-%m-%Y %H:%M')

            df_display = df.rename(columns={
                "title": "รายการ",
                "created_by": "ผู้ฝาก",
                "status": "สถานะ",
                "details": "รายละเอียด"
            })

            st.dataframe(
                df_display[["รายการ", "ผู้ฝาก", "สถานะ", "Start Date", "End Date", "รายละเอียด"]], 
                width="stretch"
            )
        else:
            st.info("💡 ไม่มีรายการงานฝากที่อยู่ในช่วงเวลาปัจจุบัน")

    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาดในการเชื่อมต่อฐานข้อมูล: {str(e)}")

# 📦 2. เมนูงานฝาก
elif st.session_state.selected_app == "deposit_job":
    try:
        from apps import deposit_job
        deposit_job.run_app()
    except ModuleNotFoundError:
        st.error("❌ ไม่พบไฟล์ `deposit_job.py` ในโฟลเดอร์ `apps`")

# 🚨 3. เมนู Dynatrace Alarm Monitor (แอปใหม่)
elif st.session_state.selected_app == "dynatrace_monitor":
    try:
        from apps import dynatrace_monitor
        dynatrace_monitor.run_app()
    except ModuleNotFoundError:
        st.error("❌ ไม่พบไฟล์ `dynatrace_monitor.py` ในโฟลเดอร์ `apps`")

# 🧹 4. หน้า Text Cleaner
elif st.session_state.selected_app == "text_cleaner":
    try:
        from apps import text_cleaner
        text_cleaner.run_app()
    except ModuleNotFoundError:
        st.error("❌ ไม่พบไฟล์ `text_cleaner.py` ในโฟลเดอร์ `apps`")
