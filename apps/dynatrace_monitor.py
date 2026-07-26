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
    
    endpoint = f"{dt_url}/api/v2/problems?problemSelector=status(\"OPEN\")&fields=title,status,severityLevel,impactLevel,startTime"
    
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
def post_comment_to_dynatrace(problem_id: str, comment_text: str, author: str):
    dt_url = get_dt_base_url()
    token = st.secrets["dynatrace"]["API_TOKEN"]
    
    headers = {
        "Authorization": f"Api-Token {token}",
        "Content-Type": "application/json"
    }
    
    endpoint = f"{dt_url}/api/v2/problems/{problem_id}/comments"
    payload = {
        "message": f"[{author} via Dashboard]: {comment_text}"
    }
    
    try:
        res = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        return res.status_code in [200, 201]
    except Exception as e:
        st.error(f"❌ Error sending comment: {str(e)}")
        return False

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
        title = prob.get("title")
        severity = prob.get("severityLevel", "UNKNOWN")
        start_time_ms = prob.get("startTime", 0)
        
        start_dt = datetime.fromtimestamp(start_time_ms / 1000.0, tz=TZ_TH).strftime('%d-%m-%Y %H:%M:%S')
        badge_color = "🔴" if severity in ["AVAILABILITY", "ERROR", "CRITICAL"] else "🟠"

        with st.expander(f"{badge_color} **[{prob_id}]** {title} — (เริ่มเมื่อ: {start_dt})", expanded=False):
            st.write(f"**Problem ID:** `{prob_id}`")
            st.write(f"**Severity Level:** {severity}")
            st.write(f"**Impact Level:** {prob.get('impactLevel')}")
            
            # ลิงก์ยิงตรงไปหน้า Classic Problems บน Dynatrace
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
                    st.info(f"👤 **{c['author']}** ({c_time}): {c['comment_text']}")
            else:
                st.caption("ยังไม่มี Comment สำหรับ Alarm นี้")

            # --- ฟอร์มส่ง Comment ใหม่ ---
            st.markdown("✏️ **เพิ่ม Comment ใหม่ (ส่งตรงเข้า Dynatrace & DB):**")
            with st.form(key=f"form_comment_{prob_id}", clear_on_submit=True):
                col_a, col_b = st.columns([1, 2])
                with col_a:
                    author_name = st.text_input("ชื่อผู้ลง Comment:", key=f"author_{prob_id}")
                with col_b:
                    comment_input = st.text_input("ข้อความ Comment / การแก้ไขปัญหา:", key=f"msg_{prob_id}")

                btn_submit = st.form_submit_button("🚀 ส่ง Comment เข้า Dynatrace & บันทึก DB")

                if btn_submit:
                    if author_name and comment_input:
                        dt_success = post_comment_to_dynatrace(prob_id, comment_input, author_name)
                        
                        if dt_success:
                            # บันทึกลง Supabase
                            supabase.table("alarm_comments").insert({
                                "problem_id": prob_id,
                                "comment_text": comment_input,
                                "author": author_name
                            }).execute()
                            
                            st.success("✅ ส่ง Comment เข้า Dynatrace และบันทึกลง Database เรียบร้อยแล้ว!")
                            st.rerun()
                        else:
                            st.error("❌ ไม่สามารถส่ง Comment ไปยัง Dynatrace ได้ กรุณาตรวจสอบสิทธิ์ Write Problems ของ Token")
                    else:
                        st.warning("⚠️ กรุณากรอกทั้งชื่อผู้ลง Comment และข้อความด้วยครับ")
