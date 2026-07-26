import streamlit as st
import pandas as pd
from supabase import create_client, Client

# ดึงค่าการเชื่อมต่อจาก secrets
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["SUPABASE_URL"]
    key = st.secrets["supabase"]["SUPABASE_KEY"]
    return create_client(url, key)

def run_app():
    st.title("📦 ระบบจัดการงานฝาก (Supabase Database)")
    
    try:
        supabase = init_supabase()
    except Exception as e:
        st.error("❌ ไม่สามารถเชื่อมต่อกับ Supabase ได้ กรุณาตรวจสอบการตั้งค่า Secrets")
        return

    # --- ฟอร์มเพิ่มงานฝากใหม่ ---
    with st.expander("➕ เพิ่มรายการงานฝากใหม่", expanded=False):
        with st.form("add_job_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                job_code = st.text_input("รหัสงาน (เช่น JOB-001):")
                title = st.text_input("ชื่องาน / รายการฝาก:")
            with col2:
                created_by = st.text_input("ชื่อผู้ฝากงาน:")
                status = st.selectbox("สถานะเริ่มต้น:", ["รอดำเนินการ", "กำลังดำเนินการ", "เสร็จสิ้น"])
            
            details = st.text_area("รายละเอียดเพิ่มเติม:")
            submitted = st.form_submit_button("💾 บันทึกงานฝาก")

            if submitted:
                if job_code and title and created_by:
                    payload = {
                        "job_code": job_code,
                        "title": title,
                        "created_by": created_by,
                        "status": status,
                        "details": details
                    }
                    supabase.table("deposit_jobs").insert(payload).execute()
                    st.success("✅ บันทึกข้อมูลงานฝากลง Supabase เรียบร้อยแล้ว!")
                    st.rerun()
                else:
                    st.warning("⚠️ กรุณากรอกรอกรหัสงาน ชื่องาน และผู้ฝากงานให้ครบถ้วน")

    st.markdown("---")

    # --- ดึงข้อมูลมาแสดงผลบนตาราง ---
    st.subheader("📋 รายการงานฝากทั้งหมดในระบบ")
    
    response = supabase.table("deposit_jobs").select("*").order("id", desc=True).execute()
    jobs_data = response.data

    if jobs_data:
        df = pd.DataFrame(jobs_data)
        
        # ปรับแต่งชื่อคอลัมน์ให้อ่านง่าย
        df_display = df.rename(columns={
            "job_code": "รหัสงาน",
            "title": "รายการ",
            "created_by": "ผู้ฝาก",
            "status": "สถานะ",
            "details": "รายละเอียด",
            "created_at": "วันที่สร้าง"
        })
        
        st.dataframe(df_display[["รหัสงาน", "รายการ", "ผู้ฝาก", "สถานะ", "รายละเอียด", "วันที่สร้าง"]], width="stretch")
    else:
        st.info("💡 ยังไม่มีข้อมูลงานฝากในระบบ กดปุ่ม 'เพิ่มรายการงานฝากใหม่' ด้านบนเพื่อเริ่มเพิ่มข้อมูล")
