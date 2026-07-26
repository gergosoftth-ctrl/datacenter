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

# --- 1. ดึง Problems จาก Dynatrace (ดึง Fields พิเศษเพิ่ม) ---
def fetch_dynatrace_problems():
    dt_url = get_dt_base_url()
    token = st.secrets["dynatrace"]["API_TOKEN"]
    
    headers = {
        "Authorization": f"Api-Token {token}",
        "Content-Type": "application/json"
    }
    
    # เพิ่ม fields เพื่อดึง impactedEntities, managementZones, alertingProfiles, endTime
    fields_query = "title,status,severityLevel,impactLevel,startTime,endTime,impactedEntities,managementZones,alertingProfiles"
    endpoint = f"{dt_url}/api/v2/problems?problemSelector=status(\"OPEN\")&fields={fields_query}"
    
    try:
        res = requests.get(endpoint, headers=headers, timeout=10)
        if res.status_code == 200:
            return res.json().get("problems", [])
        else:
            st.error(f"❌ ดึงข้อมูลจาก Dynatrace ไม่สำเร็จ (Status Code: {res.status_code})")
            st.caption(f"Details: {res.text}")
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
    payload = {
        "message": comment_text
    }
    
    try:
        res = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        return res.status_code in [200, 201]
    except Exception as e:
        st.error(f"❌ Error sending comment: {str(e)}")
        return False

# --- ฟังก์ชันคำนวณ Duration ---
def calculate_duration(start_ms, end_ms):
    if not end_ms or end_ms == -1:
        # หากยังไม่ Resolve ให้คำนวณจาก Start จนถึง เวลาปัจจุบัน
        now_ms = datetime.now().timestamp() * 1000
        diff_sec = int((now_ms - start_ms) / 1000)
        suffix = " (Active)"
    else:
        diff_sec = int((end_ms - start_ms) / 1000)
        suffix = ""

    hours = diff_sec // 3600
    minutes = (diff_sec % 3600) // 60
    
    if hours > 0:
        return f"{hours}h {minutes}m{suffix}"
    return f"{minutes}m{suffix}"

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
        st.success("✅ ไม่พบ Alarm / Problem ที่เปิดอยู่บน Dynatrace ในขณะนี้")
        return

    st.subheader(f"⚠️ รายการ Alarm ที่กำลังเกิดขึ้น ({len(problems)} รายการ)")

    for prob in problems:
        prob_id = prob.get("problemId")
        title = prob.get("title")  # Problem Name
        severity = prob.get("severityLevel", "UNKNOWN")
        start_time_ms = prob.get("startTime", 0)
        end_time_ms = prob.get("endTime", -1)
        
        # 1. แปลง Start Date (รูปแบบ Jul 26 18:02)
        start_dt_obj = datetime.fromtimestamp(start_time_ms / 1000.0, tz=TZ_TH)
        start_date_str = start_dt_obj.strftime('%b %d %H:%M')
        start_date_iso = start_dt_obj.isoformat()

        # 2. คำนวณ Duration
        duration_str = calculate_duration(start_time_ms, end_time_ms)

        # 3. ดึง Management Zones
        mz_list = [mz.get("name") for mz in prob.get("managementZones", [])]
        mz_str = ", ".join(mz_list) if mz_list else "Default"

        # 4. ดึง Impacted Entity
        impacted_list = [ent.get("name") for ent in prob.get("impactedEntities", [])]
        impacted_str = ", ".join(impacted_list) if impacted_list else "-"

        # 5. ดึง Alerting Profiles
        profile_list = [ap.get("name") for ap in prob.get("alertingProfiles", [])]
        profile_str = ", ".join(profile_list) if profile_list else "Default"

        badge_color = "🔴" if severity in ["AVAILABILITY", "ERROR", "CRITICAL"] else "🟠"

        with st.expander(f"{badge_color} **[{prob_id}]** {title} — (เริ่มเมื่อ: {start_date_str})", expanded=False):
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
            
            # ลิงก์ยิงตรงไปหน้า Classic Problems
            dt_portal_link = f"https://lss67296.apps.dynatrace.com/ui/apps/dynatrace.classic.problems/#problems/problemdetails;gtf=-2h;gf=all;pid={prob_id}"
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
            with st.form(key=f"form_comment_{prob_id}", clear_on_submit=True):
                col_a, col_b = st.columns([1, 2])
                with col_a:
                    user_name = st.text_input("ชื่อผู้ลง Comment (User):", key=f"author_{prob_id}")
                with col_b:
                    comment_input = st.text_input("ข้อความ Comment:", key=f"msg_{prob_id}")

                btn_submit = st.form_submit_button("🚀 ส่ง Comment เข้า Dynatrace & บันทึก DB")

                if btn_submit:
                    if user_name and comment_input:
                        # 1. ยิงข้อความเพียวๆ เข้า Dynatrace
                        dt_success = post_comment_to_dynatrace(prob_id, comment_input)
                        
                        if dt_success:
                            # 2. บันทึกข้อมูลครบทุกลดทั้ง 8 ข้อลง Supabase DB
                            db_payload = {
                                "user_name": user_name,
                                "problem_id": prob_id,
                                "management_zones": mz_str,
                                "problem_name": title,
                                "impacted_entity": impacted_str,
                                "alerting_profiles": profile_str,
                                "start_date": start_date_iso,
                                "duration": duration_str,
                                "comment_text": comment_input
                            }
                            supabase.table("alarm_comments").insert(db_payload).execute()
                            
                            st.success("✅ บันทึกข้อมูลลง DB และส่ง Comment เข้า Dynatrace เรียบร้อยแล้ว!")
                            st.rerun()
                        else:
                            st.error("❌ ไม่สามารถส่ง Comment ไปยัง Dynatrace ได้ กรุณาตรวจสอบสิทธิ์ Write Problems")
                    else:
                        st.warning("⚠️ กรุณากรอกทั้งชื่อ User และข้อความ Comment ด้วยครับ")
