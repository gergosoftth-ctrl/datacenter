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

    # --- 🎯 1. ส่วนควบคุม Pop-up กล่องข้อความแจ้งเตือนตรงกลาง ---
    if "show_popup" not in st.session_state:
        st.session_state.show_popup = False
    if "popup_text" not in st.session_state:
        st.session_state.popup_text = ""

    # หากมีสถานะสั่งโชว์ Pop-up ให้แสดงกล่องแจ้งเตือนเน้นๆ บนสุด
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
                    
                    # ตั้งค่าให้สั่งแสดง Pop-up
                    st.session_state.show_popup = True
                    st.session_state.popup_text = f"บันทึกรายการงานฝาก **{job_code} ({title})** ลงระบบเรียบร้อยแล้ว!"
                    st.rerun()
                else:
                    st.warning("⚠️ กรุณากรอกรอกรหัสงาน ชื่องาน และผู้ฝากงานให้ครบถ้วน")

    st.markdown("---")

    # --- 3. แสดงตารางข้อมูลพร้อมฟังก์ชันแก้ไข ---
    st.subheader("📋 รายการงานฝากทั้งหมดในระบบ")
    st.caption("💡 คุณสามารถ **คลิกเปลี่ยนสถานะ** หรือ **ดับเบิลคลิกแก้ไขรายละเอียด** ในตาราง แล้วกดปุ่มบันทึกด้านล่างได้เลยครับ")

    response = supabase.table("deposit_jobs").select("*").order("id", desc=True).execute()
    jobs_data = response.data

    if jobs_data:
        df = pd.DataFrame(jobs_data)
        df_edit = df[["id", "job_code", "title", "created_by", "status", "details"]].copy()

        edited_df = st.data_editor(
            df_edit,
            key="jobs_editor",
            width="stretch",
            hide_index=True,
            column_config={
                "id": None,
                "job_code": st.column_config.TextColumn("รหัสงาน", disabled=True),
                "title": st.column_config.TextColumn("รายการ", disabled=True),
                "created_by": st.column_config.TextColumn("ผู้ฝาก", disabled=True),
                "status": st.column_config.SelectboxColumn(
                    "สถานะ",
                    help="เลือกสถานะของงานฝาก",
                    options=["รอดำเนินการ", "กำลังดำเนินการ", "เสร็จสิ้น"],
                    required=True
                ),
                "details": st.column_config.TextColumn("รายละเอียด", help="ดับเบิลคลิกเพื่อแก้ไขข้อความ"),
            }
        )

        # ปุ่มบันทึกการแก้ไขลง Database
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
                    # ตั้งค่าเปิด Pop-up แจ้งเตือนเมื่ออัปเดตสำเร็จ
                    st.session_state.show_popup = True
                    st.session_state.popup_text = f"อัปเดตสถานะและรายละเอียดข้อมูลลง Database สำเร็จแล้ว **{changes_count} รายการ**"
                    st.rerun()
                else:
                    st.info("ℹ️ ไม่พบการเปลี่ยนแปลงข้อมูลในตาราง")
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาดในการอัปเดตข้อมูล: {str(e)}")

    else:
        st.info("💡 ยังไม่มีข้อมูลงานฝากในระบบ กดปุ่ม 'เพิ่มรายการงานฝากใหม่' ด้านบนเพื่อเริ่มเพิ่มข้อมูล")
