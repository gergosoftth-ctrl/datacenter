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

# --- ฟังก์ชันดึง Problems พร้อมเก็บ Debug Log ---
def fetch_dynatrace_problems_debug():
    dt_url = get_dt_base_url()
    token = st.secrets["dynatrace"]["API_TOKEN"]
    
    headers = {
        "Authorization": f"Api-Token {token}",
        "Content-Type": "application/json"
    }
    
    # ทดลองยิงดึง Problems Endpoint พื้นฐาน
    endpoint = f"{dt_url}/api/v2/problems?pageSize=20"
    
    try:
        res = requests.get(endpoint, headers=headers, timeout=10)
        return {
            "url_used": endpoint,
            "status_code": res.status_code,
            "response_text": res.text,
            "data": res.json() if res.status_code == 200 else {}
        }
    except Exception as e:
        return {
            "url_used": endpoint,
            "status_code": "ERROR",
            "response_text": str(e),
            "data": {}
        }

# --- ส่ง Comment เข้า Dynatrace ---
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

    # --- ดึงข้อมูลเพื่อ Debug ---
    with st.spinner("กำลังเชื่อมต่อ Dynatrace..."):
        debug_res = fetch_dynatrace_problems_debug()

    # แสดง Debug Box เพื่อดูว่า Dynatrace ตอบอะไรกลับมา
    with st.expander("🛠️ คลิกเพื่อดูรายละเอียดการเชื่อมต่อ API (Debug Log)", expanded=True):
        st.write(f"**URL ที่ยิงไป:** `{debug_res['url_used']}`")
        st.write(f"**Status Code:** `{debug_res['status_code']}`")
        st.code(debug_res['response_text'], language="json")

    problems = debug_res['data'].get("problems", []) if debug_res['status_code'] == 200 else []

    if not problems:
        st.info("💡 ไม่มีรายการ Alarm ส่งกลับมาจาก Dynatrace ตามการเชื่อมต่อข้างต้น")
        return

    st.subheader(f"⚠️ รายการ Alarm ทั้งหมดที่พบ ({len(problems)} รายการ)")

    for prob in problems:
        internal_id = prob.get("problemId")
        prob_id = prob.get("displayId") if prob.get("displayId") else f"P-{internal_id}"
        title = prob.get("title", "Unknown Problem")
        status = prob.get("status", "UNKNOWN")
        severity = prob.get("severityLevel", "UNKNOWN")
        start_time_ms = prob.get("startTime", 0)
        end_time_ms = prob.get("endTime", -1)
        
        start_dt_obj = datetime.fromtimestamp(start_time_ms / 1000.0, tz=TZ_TH) if start_time_ms else datetime.now(TZ_TH)
        start_date_str = start_dt_obj.strftime('%b %d %H:%M')
        duration_str = calculate_duration(start_time_ms, end_time_ms)

        badge_color = "🔴" if severity in ["AVAILABILITY", "ERROR", "CRITICAL"] else "🟠"

        with st.expander(f"{badge_color} **[{prob_id}]** {title} — Status: {status}", expanded=False):
            st.write(f"**Problem ID:** `{prob_id}`")
            st.write(f"**Status:** {status}")
            st.write(f"**Start Date:** {start_date_str}")
            st.write(f"**Duration:** {duration_str}")

            dt_portal_link = f"https://lss67296.apps.dynatrace.com/ui/apps/dynatrace.classic.problems/#problems/problemdetails;gtf=-2h;gf=all;pid={internal_id}"
            st.markdown(f"🔗 [เปิดดูรายละเอียดบน Dynatrace UI]({dt_portal_link})")

            st.markdown("---")

            # ฟอร์มลง Comment
            with st.form(key=f"form_comment_{internal_id}", clear_on_submit=True):
                col_a, col_b = st.columns([1, 2])
                with col_a:
                    user_name = st.text_input("ชื่อผู้ลง Comment (User):", key=f"author_{internal_id}")
                with col_b:
                    comment_input = st.text_input("ข้อความ Comment:", key=f"msg_{internal_id}")

                btn_submit = st.form_submit_button("🚀 ส่ง Comment เข้า Dynatrace & บันทึก DB")

                if btn_submit and user_name and comment_input:
                    dt_success = post_comment_to_dynatrace(internal_id, comment_input)
                    if dt_success:
                        db_payload = {
                            "user_name": user_name,
                            "problem_id": prob_id,
                            "problem_name": title,
                            "start_date": start_date_str,
                            "duration": duration_str,
                            "comment_text": comment_input,
                            "status": status
                        }
                        supabase.table("alarm_comments").insert(db_payload).execute()
                        st.success("✅ บันทึกข้อมูลเรียบร้อย!")
                        st.rerun()
                    else:
                        st.error("❌ ส่ง Comment ไม่สำเร็จ")
