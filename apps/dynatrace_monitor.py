import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz
from supabase import create_client, Client

TZ_TH = pytz.timezone('Asia/Bangkok')

@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["SUPABASE_URL"]
    key = st.secrets["supabase"]["SUPABASE_KEY"]
    return create_client(url, key)

def get_dt_base_url():
    """ แปลง URL ให้ตรงกับมาตรฐาน Dynatrace API Endpoint """
    raw_url = st.secrets["dynatrace"]["TENANT_URL"].rstrip('/')
    if "apps.dynatrace.com" in raw_url:
        tenant_id = raw_url.split("//")[1].split(".")[0]
        return f"https://{tenant_id}.live.dynatrace.com"
    return raw_url

# --- 1. ดึง Problems จาก Dynatrace ---
def fetch_dynatrace_problems():
    dt_url = get_dt_base_url()
    token = st.secrets["dynatrace"]["API_TOKEN"]
    
    headers = {
        "Authorization": f"Api-Token {token}",
        "Content-Type": "application/json"
    }
    
    # ยิงดึงปัญหาล่าสุด 30 รายการ
    endpoint = f"{dt_url}/api/v2/problems?pageSize=30"
    
    try:
        res = requests.get(endpoint, headers=headers, timeout=10)
        if res.status_code == 200:
            return res.json().get("problems", [])
        else:
            st.error(f"❌ ดึงข้อมูลจาก Dynatrace ไม่สำเร็จ (Status Code: {res.status_code})")
            return []
    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาดในการเชื่อมต่อ Dynatrace: {str(e)}")
        return []

# --- 2. ส่ง Comment เข้า Dynatrace ---
def post_comment_to_dynatrace(problem_id: str, comment_text: str):
    dt_url = get_dt_base_url()
    token = st.secrets["dynatrace"]["API_TOKEN"]
    
    headers = {
        "Authorization": f"Api-Token {token}",
        "Content-Type": "application/json"
    }
    
    endpoint = f"{dt_url}/api/v2/problems/{problem_id}/comments"
    payload = {"message": comment_text}
    
    try:
        res = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        return res.status_code in [200, 201]
    except Exception as e:
        st.error(f"❌ Error sending comment: {str(e)}")
        return False

# --- 3. คำนวณ Duration ---
def calculate_duration(start_ms, end_ms):
    if not end_ms or end_ms == -1:
        now_ms = datetime.now().timestamp() * 1000
        diff_sec = int((now_ms - start_ms) / 1000)
        suffix = " (Active)"
    else:
        diff_sec = int((end_ms - start_ms) / 1000)
        suffix = " (Closed)"

    hours = diff_sec // 3600
    minutes = (diff_sec % 3600) // 60
    
    if hours > 0:
        return f"{hours}h {minutes}m{suffix}"
    return f"{minutes}m{suffix}"

# --- 4. Sync สถานะ CLOSED และ Comment ลง Supabase DB ---
def sync_closed_status_to_db(supabase: Client, problems: list):
    for prob in problems:
        display_id = prob.get("displayId") or prob.get("problemId")
        dt_status = prob.get("status")
        start_ms = prob.get("startTime", 0)
        end_ms = prob.get("endTime", -1)

        # เช็กว่ามีอยู่ใน DB เราไหม
        existing = supabase.table("alarm_comments").select("*").eq("problem_id", display_id).execute().data
        
        if existing:
            duration_str = calculate_duration(start_ms, end_ms)
            update_data = {
                "status": dt_status,
                "duration": duration_str
            }
            supabase.table("alarm_comments").update(update_data).eq("problem_id", display_id).execute()

def run_app():
    st.title("🚨 Dynatrace Alarm Monitor & Comment Center")
    st.caption("เชื่อมต่อตรงกับ Dynatrace Tenant: `lss67296`")

    try:
        supabase = init_supabase()
    except Exception as e:
        st.error("❌ ไม่สามารถเชื่อมต่อ Supabase ได้ กรุณาตรวจสอบ Secrets")
        return

    # ปุ่ม Refresh
    col_title, col_btn = st.columns([4, 1])
    with col_btn:
        if st.button("🔄 อัปเดตข้อมูล Real-time", type="primary", use_container_width=True):
            st.rerun()

    # --- ดึงข้อมูลจาก Dynatrace ---
    with st.spinner("กำลังดึงข้อมูล Alarm ล่าสุดจาก Dynatrace..."):
        problems = fetch_dynatrace_problems()

    if not problems:
        st.success("✅ ไม่พบข้อมูล Alarm ในระบบขณะนี้")
        return

    # Sync สถานะ CLOSED ลง DB
    sync_closed_status_to_db(supabase, problems)

    # กรองเฉพาะรายการที่ยัง OPEN อยู่
    open_problems = [p for p in problems if p.get("status") == "OPEN"]

    st.subheader(f"⚠️ รายการ Alarm ที่กำลังเกิดขึ้น ({len(open_problems)} รายการ)")

    if not open_problems:
        st.success("✅ ไม่พบ Alarm สถานะ OPEN ในระบบขณะนี้ (รายการที่แก้ไขแล้ว/CLOSED ได้ถูกซิงค์ข้อมูลลง DB เรียบร้อยแล้ว)")
        return

    for prob in open_problems:
        internal_id = prob.get("problemId")
        prob_id = prob.get("displayId", f"P-{internal_id}")
        title = prob.get("title", "Unknown Problem")
        severity = prob.get("severityLevel", "UNKNOWN")
        start_time_ms = prob.get("startTime", 0)
        end_time_ms = prob.get("endTime", -1)
        
        # 1. วันเวลาเริ่ม (แปลง timestamp)
        start_dt_obj = datetime.fromtimestamp(start_time_ms / 1000.0, tz=TZ_TH) if start_time_ms else datetime.now(TZ_TH)
        start_date_str = start_dt_obj.strftime('%b %d %H:%M')

        # 2. Duration
        duration_str = calculate_duration(start_time_ms, end_time_ms)

        # 3. Management Zone (ดึงจากโครงสร้างจริง)
        mz_list = [mz.get("name") for mz in prob.get("managementZones", [])] if prob.get("managementZones") else []
        mz_str = ", ".join(mz_list) if mz_list else "Default"

        # 4. Impacted Entity (ดึงจากโครงสร้างจริง)
        impacted_list = [ent.get("name") for ent in prob.get("impactedEntities", [])] if prob.get("impactedEntities") else []
        impacted_str = ", ".join(impacted_list) if impacted_list else "-"

        # 5. Alerting Profiles
        profile_list = [ap.get("name") for ap in prob.get("problemFilters", [])] if prob.get("problemFilters") else []
        profile_str = ", ".join(profile_list) if profile_list else "Default"

        badge_color = "🔴" if severity in ["AVAILABILITY", "ERROR", "CRITICAL"] else "🟠"

        with st.expander(f"{badge_color} **[{prob_id}]** {title} — (เริ่มเมื่อ: {start_date_str})", expanded=True):
            col_info1, col_info2 = st.columns(2)
            with col_info1:
                st.write(f"**Problem ID:** `{prob_id}`")
                st.write(f"**Problem Name:** {title}")
                st.write(f"**Management Zone:** {mz_str}")
                st.write(f"**Impacted Entity:** `{impacted_str}`")
            with col_info2:
                st.write(f"**Alerting Profile:** {profile_str}")
                st.write(f"**Start Date:** {start_date_str}")
                st.write(f"**Duration:** {duration_str}")
            
            # ลิงก์ตรงเปิดดูใน Dynatrace UI
            dt_portal_link = f"https://lss67296.apps.dynatrace.com/ui/apps/dynatrace.classic.problems/#problems/problemdetails;gtf=-2h;gf=all;pid={internal_id}"
            st.markdown(f"🔗 [เปิดดูรายละเอียดบน Dynatrace UI]({dt_portal_link})")

            st.markdown("---")
            
            # --- แสดง History Comment จาก Supabase ---
            st.markdown("💬 **ประวัติ Comment ในระบบ (Supabase History):**")
            comments_res = supabase.table("alarm_comments").select("*").eq("problem_id", prob_id).order("id", desc=True).execute()
            comments_data = comments_res.data

            if comments_data:
                for c in comments_data:
                    c_time = datetime.fromisoformat(c['created_at']).astimezone(TZ_TH).strftime('%d-%m-%Y %H:%M')
                    st.info(f"👤 **{c.get('user_name', 'Unknown')}** ({c_time}): {c.get('comment_text')}")
            else:
                st.caption("ยังไม่มี Comment สำหรับ Alarm นี้")

            # --- ฟอร์มส่ง Comment ใหม่ ---
            st.markdown("✏️ **เพิ่ม Comment ใหม่ (ส่งตรงเข้า Dynatrace & DB):**")
            with st.form(key=f"form_comment_{internal_id}", clear_on_submit=True):
                col_a, col_b = st.columns([1, 2])
                with col_a:
                    user_name = st.text_input("ชื่อผู้ลง Comment (User):", key=f"author_{internal_id}")
                with col_b:
                    comment_input = st.text_input("ข้อความ Comment:", key=f"msg_{internal_id}")

                btn_submit = st.form_submit_button("🚀 ส่ง Comment เข้า Dynatrace & บันทึก DB")

                if btn_submit:
                    if user_name and comment_input:
                        dt_success = post_comment_to_dynatrace(internal_id, comment_input)
                        
                        if dt_success:
                            db_payload = {
                                "user_name": user_name,
                                "problem_id": prob_id,               # เช่น P-26074757
                                "management_zones": mz_str,           # เช่น COU_SEW_CSPOT_QA
                                "problem_name": title,                # เช่น [ITO] High Disk Utilization > 90%
                                "impacted_entity": impacted_str,      # เช่น csk8sdvqa02
                                "alerting_profiles": profile_str,     # เช่น ITO_Dynatrace_Alert-Profile
                                "start_date": start_date_str,         # เช่น Jul 27 ...
                                "duration": duration_str,             # เช่น 1h 20m (Active)
                                "comment_text": comment_input,
                                "status": "OPEN"
                            }
                            supabase.table("alarm_comments").insert(db_payload).execute()
                            
                            st.success("✅ บันทึกข้อมูลลง DB และส่ง Comment เข้า Dynatrace เรียบร้อยแล้ว!")
                            st.rerun()
                        else:
                            st.error("❌ ไม่สามารถส่ง Comment ไปยัง Dynatrace ได้")
                    else:
                        st.warning("⚠️ กรุณากรอกทั้งชื่อ User และข้อความ Comment ด้วยครับ")
