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

# --- 1. ดึง Problems จาก Dynatrace (เน้นเรียบง่ายและเสถียร) ---
def fetch_dynatrace_problems():
    dt_url = get_dt_base_url()
    token = st.secrets["dynatrace"]["API_TOKEN"]
    
    headers = {
        "Authorization": f"Api-Token {token}",
        "Content-Type": "application/json"
    }
    
    all_problems = []

    # 1.1 ดึงรายการ OPEN ย้อนหลัง 30 วัน (ดึง Basic Fields ป้องกัน API ปฏิเสธ)
    endpoint_open = f"{dt_url}/api/v2/problems?problemSelector=status(\"OPEN\")&from=-720h&pageSize=50"
    try:
        res_open = requests.get(endpoint_open, headers=headers, timeout=10)
        if res_open.status_code == 200:
            all_problems.extend(res_open.json().get("problems", []))
        else:
            st.error(f"❌ ดึงข้อมูล OPEN ไม่สำเร็จ (Status: {res_open.status_code})")
            st.caption(f"Details: {res_open.text}")
    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาดในการเชื่อมต่อ Dynatrace: {str(e)}")

    # 1.2 ดึงรายการ RESOLVED ย้อนหลัง 72 ชม. เพื่อนำไปอัปเดตสถานะใน DB
    endpoint_resolved = f"{dt_url}/api/v2/problems?problemSelector=status(\"RESOLVED\")&from=-72h&pageSize=50"
    try:
        res_resolved = requests.get(endpoint_resolved, headers=headers, timeout=10)
        if res_resolved.status_code == 200:
            all_problems.extend(res_resolved.json().get("problems", []))
    except Exception as e:
        pass

    return all_problems

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

# --- 3. คำนวณ Duration ( Start Date -> Resolve Date ) ---
def calculate_duration(start_ms, end_ms):
    if not end_ms or end_ms == -1:
        now_ms = datetime.now().timestamp() * 1000
        diff_sec = int((now_ms - start_ms) / 1000)
        suffix = " (Active)"
    else:
        diff_sec = int((end_ms - start_ms) / 1000)
        suffix = " (Resolved)"

    hours = diff_sec // 3600
    minutes = (diff_sec % 3600) // 60
    
    if hours > 0:
        return f"{hours}h {minutes}m{suffix}"
    return f"{minutes}m{suffix}"

# --- 4. ฟังก์ชัน Sync สภาวะ RESOLVED และ Comment ล่าสุดเข้า DB ---
def sync_resolved_status_to_db(supabase: Client, problems: list):
    for prob in problems:
        display_id = prob.get("displayId") or prob.get("problemId")
        dt_status = prob.get("status")
        start_ms = prob.get("startTime", 0)
        end_ms = prob.get("endTime", -1)
        
        dt_comments = prob.get("comments", [])
        latest_dt_comment = dt_comments[-1].get("message") if dt_comments else None

        existing = supabase.table("alarm_comments").select("*").eq("problem_id", display_id).execute().data
        
        if existing:
            duration_str = calculate_duration(start_ms, end_ms)
            end_date_str = datetime.fromtimestamp(end_ms / 1000.0, tz=TZ_TH).strftime('%b %d %H:%M') if end_ms > 0 else "-"

            update_data = {
                "status": dt_status,
                "duration": duration_str,
            }
            if end_ms > 0:
                update_data["end_date"] = end_date_str
            
            if latest_dt_comment:
                update_data["comment_text"] = latest_dt_comment

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

    if problems:
        sync_resolved_status_to_db(supabase, problems)

    # กรองแสดงเฉพาะรายการ OPEN บนหน้าแอป
    open_problems = [p for p in problems if p.get("status") == "OPEN"]

    st.subheader(f"⚠️ รายการ Alarm ที่กำลังเกิดขึ้น ({len(open_problems)} รายการ)")

    if not open_problems:
        st.success("✅ ไม่พบ Alarm สถานะ OPEN ในระบบขณะนี้ (หากมีรายการที่ Resolved แล้ว ระบบได้ทำการอัปเดตลง DB เรียบร้อยแล้ว)")
        return

    for prob in open_problems:
        internal_id = prob.get("problemId")
        # ดึง displayId หากไม่มีจะนำ displayId จาก Dynatrace หรือ fallback เป็น displayId Format
        prob_id = prob.get("displayId") if prob.get("displayId") else f"P-{internal_id}"
        
        title = prob.get("title", "Unknown Problem")
        severity = prob.get("severityLevel", "UNKNOWN")
        start_time_ms = prob.get("startTime", 0)
        end_time_ms = prob.get("endTime", -1)
        
        start_dt_obj = datetime.fromtimestamp(start_time_ms / 1000.0, tz=TZ_TH) if start_time_ms else datetime.now(TZ_TH)
        start_date_str = start_dt_obj.strftime('%b %d %H:%M')

        duration_str = calculate_duration(start_time_ms, end_time_ms)

        # จัดการ Management Zones
        mz_list = [mz.get("name") for mz in prob.get("managementZones", [])] if prob.get("managementZones") else []
        mz_str = ", ".join(mz_list) if mz_list else "Default"

        # จัดการ Impacted Entity
        impacted_list = [ent.get("name") for ent in prob.get("impactedEntities", [])] if prob.get("impactedEntities") else []
        impacted_str = ", ".join(impacted_list) if impacted_list else "-"

        # จัดการ Alerting Profiles
        profile_list = [ap.get("name") for ap in prob.get("alertingProfiles", [])] if prob.get("alertingProfiles") else []
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
                                "problem_id": prob_id,
                                "management_zones": mz_str,
                                "problem_name": title,
                                "impacted_entity": impacted_str,
                                "alerting_profiles": profile_str,
                                "start_date": start_date_str,
                                "duration": duration_str,
                                "comment_text": comment_input,
                                "status": "OPEN"
                            }
                            supabase.table("alarm_comments").insert(db_payload).execute()
                            
                            st.success("✅ บันทึกข้อมูลลง DB และส่ง Comment เข้า Dynatrace เรียบร้อยแล้ว!")
                            st.rerun()
                        else:
                            st.error("❌ ไม่สามารถส่ง Comment ไปยัง Dynatrace ได้ กรุณาตรวจสอบสิทธิ์ Write Problems")
                    else:
                        st.warning("⚠️ กรุณากรอกทั้งชื่อ User และข้อความ Comment ด้วยครับ")
