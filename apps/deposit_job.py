import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
from supabase import create_client, Client

# ตั้งค่า Timezone ประเทศไทย (GMT+7)
TZ_TH = pytz.timezone('Asia/Bangkok')

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

    # --- 🎯 1. ส่วน Pop-up แจ้งเตือน ---
    if "show_popup" not in st.session_state:
        st.session_state.show_popup = False
    if "popup_text" not in st.session_state:
        st.session_state.popup_text = ""

    if st.session_state.show_popup:
        with st.container():
            st.markdown("---")
            st.success(f"### 🎉 แจ้งเตือนการบันทึกข้อมูล\n\n{st.session_state.popup_text}")
            if st.button("❌ ปิดหน้าต่างแจ้งเตือน", type="primary", use_container_width=True):
                st.session_state.show_popup = False
                st.session_state.popup_text = ""
                st.rerun()
            st.markdown("---")

    # --- 2. ฟอร์มเพิ่มงานฝากใหม่ ---
    with st.expander("➕ เพิ่มรายการงานฝากใหม่", expanded=False):
        with st.form("add_job_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                # ข้อ 2: รายการมีให้เลือกแค่ Deployment กับ Refreshment
                title = st.selectbox("รายการฝาก:", ["Deployment", "Refreshment"])
                created_by = st.text_input("ชื่อผู้ฝากงาน:")
                status = st.selectbox("สถานะเริ่มต้น:", ["รอดำเนินการ", "กำลังดำเนินการ", "เสร็จสิ้น"])
            
            with col2:
                # ข้อ 3: วันเวลา Start Date และ End Date
                start_date_val = st.date_input("วันที่เริ่มต้น (Start Date):")
                start_time_val = st.time_input("เวลาเริ่มต้น:", value=datetime.now().time())
                
                end_date_val = st.date_input("วันที่สิ้นสุด (End Date):")
                end_time_val = st.time_input("เวลาสิ้นสุด:", value=datetime.now().time())

            details = st.text_area("รายละเอียดเพิ่มเติม:")
            submitted = st.form_submit_button("💾 บันทึกงานฝาก")

            if submitted:
                if title and created_by:
                    # รวม Date + Time และแปลงเป็น ISO Format สำหรับเก็บใน Supabase
                    start_dt = datetime.combine(start_date_val, start_time_val).astimezone(TZ_TH).isoformat()
                    end_dt = datetime.combine(end_date_val, end_time_val).astimezone(TZ_TH).isoformat()

                    payload = {
                        "title": title,
                        "created_by": created_by,
                        "status": status,
                        "start_date": start_dt,
                        "end_date": end_dt,
                        "details": details
                    }
                    supabase.table("deposit_jobs").insert(payload).execute()
                    
                    st.session_state.show_popup = True
                    st.session_state.popup_text = f"บันทึกรายการ **{title}** โดยคุณ {created_by} เรียบร้อยแล้ว!"
                    st.rerun()
                else:
                    st.warning("⚠️ กรุณากรอกชื่อผู้ฝากงานให้ครบถ้วน")

    st.markdown("---")

    # --- 3. แสดงตารางข้อมูล (ดึงเฉพาะงานที่ยังไม่หมดอายุ) ---
    st.subheader("📋 รายการงานฝากที่กำลังใช้งาน")
    st.caption("💡 ระบบจะแสดงเฉพาะรายการที่ยังไม่หมดอายุ (End Date เกินปัจจุบันจะถูกซ่อนจากหน้าจออัตโนมัติ)")

    # ข้อ 4: ดึงเฉพาะรายการที่ end_date >= วันเวลาปัจจุบัน
    now_iso = datetime.now(TZ_TH).isoformat()
    response = supabase.table("deposit_jobs").select("*").gte("end_date", now_iso).order("id", desc=True).execute()
    jobs_data = response.data

    if jobs_data:
        df = pd.DataFrame(jobs_data)

        # ข้อ 5: แปลงฟอร์แมตวันเวลาเป็น DD-MM-YYYY HH:MM (24hr)
        if "start_date" in df.columns and "end_date" in df.columns:
            df["start_date_fmt"] = pd.to_datetime(df["start_date"]).dt.tz_convert('Asia/Bangkok').dt.strftime('%d-%m-%Y %H:%M')
            df["end_date_fmt"] = pd.to_datetime(df["end_date"]).dt.tz_convert('Asia/Bangkok').dt.strftime('%d-%m-%Y %H:%M')

        # ข้อ 1: เอารหัสพนักงาน/รหัสงานออก เลือกแสดงเฉพาะคอลัมน์ที่ต้องการ
        df_edit = df[["id", "title", "created_by", "status", "start_date_fmt", "end_date_fmt", "details"]].copy()

        edited_df = st.data_editor(
            df_edit,
            key="jobs_editor",
            width="stretch",
            hide_index=True,
            column_config={
                "id": None,
                "title": st.column_config.TextColumn("รายการ", disabled=True),
                "created_by": st.column_config.TextColumn("ผู้ฝาก", disabled=True),
                "start_date_fmt": st.column_config.TextColumn("Start Date", disabled=True),
                "end_date_fmt": st.column_config.TextColumn("End Date", disabled=True),
                "status": st.column_config.SelectboxColumn(
                    "สถานะ",
                    options=["รอดำเนินการ", "กำลังดำเนินการ", "เสร็จสิ้น"],
                    required=True
                ),
                "details": st.column_config.TextColumn("รายละเอียด"),
            }
        )

        if st.button("💾 บันทึกการแก้ไขลง Database", type="primary"):
            try:
                changes_count = 0
                for index, row in edited_df.iterrows():
                    original_row = df_edit.loc[index]
                    
                    if (row["status"] != original_row["status"]) or (row["details"] != original_row["details"]):
                        supabase.table("deposit_jobs").update({
                            "status": row["status"],
                            "details": row["details"]
                        }).eq("id", row["id"]).execute()
                        changes_count += 1

                if changes_count > 0:
                    st.session_state.show_popup = True
                    st.session_state.popup_text = f"อัปเดตข้อมูลสำเร็จแล้ว **{changes_count} รายการ**"
                    st.rerun()
                else:
                    st.info("ℹ️ ไม่พบการเปลี่ยนแปลงข้อมูลในตาราง")
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาดในการอัปเดตข้อมูล: {str(e)}")

    else:
        st.info("💡 ไม่พบรายการงานฝากที่เปิดใช้งานอยู่ (หรือรายการทั้งหมดหมดอายุแล้ว)")
