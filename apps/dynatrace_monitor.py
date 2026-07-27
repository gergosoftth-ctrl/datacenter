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
    raw_url = st.secrets["dynatrace"]["TENANT_URL"].rstrip('/')
    if "apps.dynatrace.com" in raw_url:
        tenant_id = raw_url.split("//")[1].split(".")[0]
        return f"https://{tenant_id}.live.dynatrace.com"
    return raw_url

def fetch_dynatrace_problems():
    dt_url = get_dt_base_url()
    token = st.secrets["dynatrace"]["API_TOKEN"]
    headers = {"Authorization": f"Api-Token {token}", "Content-Type": "application/json"}
    endpoint = f"{dt_url}/api/v2/problems?pageSize=30"
    
    try:
        res = requests.get(endpoint, headers=headers, timeout=10)
        if res.status_code == 200:
            return res.json().get("problems", [])
        return []
    except Exception:
        return []

def post_comment_to_dynatrace(problem_id: str, comment_text: str):
    dt_url = get_dt_base_url()
    token = st.secrets["dynatrace"]["API_TOKEN"]
    headers = {"Authorization": f"Api-Token {token}", "Content-Type": "application/json"}
    endpoint = f"{dt_url}/api/v2/problems/{problem_id}/comments"
    
    try:
        res = requests.post(endpoint, headers=headers, json={"message": comment_text}, timeout=10)
        return res.status_code in [200, 201]
    except Exception:
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
    return f"{hours}h {minutes}m{suffix}" if hours > 0 else f"{minutes}m{suffix}"

def sync_dynatrace_to_db(supabase: Client, problems: list):
    """ ดึง Alarm จาก Dynatrace เข้า Supabase โดยกรองรายการซ้ำให้อัตโนมัติ """
    # 1. กรองปัญหากลุ่มเดียวกันใน Dynatrace ไม่ให้ประมวลผลซ้ำ
    seen_ids = set()
    unique_problems = []
    for p in problems:
        pid = p.get("displayId") or p.get("problemId")
        if pid not in seen_ids:
            seen_ids.add(pid)
            unique_problems.append(p)

    # 2. นำรายการเข้า Database
    for prob in unique_problems:
        internal_id = prob.get("problemId")
        display_id = prob.get("displayId", f"P-{internal_id}")
        dt_status = "ACTIVE" if prob.get("status") == "OPEN" else "RESOLVED"
        
        start_ms = prob.get("startTime", 0)
        end_ms = prob.get("endTime", -1)
        
        start_dt_str = datetime.fromtimestamp(start_ms / 1000.0, tz=TZ_TH).strftime('%b %d %H:%M') if start_ms else "-"
        resolve_dt_str = datetime.fromtimestamp(end_ms / 1000.0, tz=TZ_TH).strftime('%b %d %H:%M') if end_ms > 0 else "-"
        duration_str = calculate_duration(start_ms, end_ms)

        mz_list = [mz.get("name") for mz in prob.get("managementZones", [])] if prob.get("managementZones") else []
        services_str = ", ".join(mz_list) if mz_list else "Default"
        title = prob.get("title", "Unknown Problem")

        # เช็กกับ Supabase DB ว่ามี Problem ID นี้อยู่แล้วหรือยัง
        existing = supabase.table("alarm_comments").select("id").eq("problem_id", display_id).execute().data

        if not existing:
            # ถ้ายังไม่มีใน DB ให้ทำการ Insert ใหม่เพียงครั้งเดียว
            db_payload = {
                "problem_id": display_id,
                "internal_id": internal_id,
                "status": dt_status,
                "services": services_str,
                "problem_name": title,
                "start_date": start_dt_str,
                "duration": duration_str,
                "resolve_date": resolve_dt_str if end_ms > 0 else None,
                "ack": None,
                "remark": None,
                "incident": None
            }
            try:
                supabase.table("alarm_comments").insert(db_payload).execute()
            except Exception:
                pass
        else:
            # ถ้ามีอยู่แล้ว ให้ทำเฉพาะการ Update สถานะ + Duration
            update_payload = {
                "status": dt_status,
                "duration": duration_str,
                "resolve_date": resolve_dt_str if end_ms > 0 else None
            }
            supabase.table("alarm_comments").update(update_payload).eq("problem_id", display_id).execute()

def run_app():
    st.title("🚨 Real-time Alarm Management Table")
    st.caption("ตารางติดตามสถานะการแจ้งเตือนรองรับ Multi-Source Monitoring")

    try:
        supabase = init_supabase()
    except Exception:
        st.error("❌ ไม่สามารถเชื่อมต่อ Supabase ได้")
        return

    # ปุ่ม Manual Sync
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("🔄 Sync Real-time", type="primary", use_container_width=True):
            st.rerun()

    # Sync ข้อมูล Dynatrace ล่าสุดลง DB
    with st.spinner("กำลังอัปเดตข้อมูล Alarm จาก Dynatrace..."):
        dt_problems = fetch_dynatrace_problems()
        if dt_problems:
            sync_dynatrace_to_db(supabase, dt_problems)

    # ดึงรายการทั้งหมดจาก DB มาแสดงในตาราง
    res = supabase.table("alarm_comments").select("*").order("id", desc=True).execute()
    data = res.data

    if not data:
        st.info("💡 ไม่มีรายการ Alarm ในตารางขณะนี้")
        return

    st.subheader("📋 ตารางประวัติและสถานะ Alarm")

    # วนลูปสร้าง UI แบบการจัดการเรียงเป็นแถวตาราง
    for item in data:
        db_id = item["id"]
        prob_id = item["problem_id"]
        internal_id = item.get("internal_id")
        status_color = "🔴" if item["status"] == "ACTIVE" else "🟢"

        with st.expander(
            f"{status_color} **[{item['status']}]** {prob_id} | {item['problem_name']} | Service: {item['services']}",
            expanded=(item["status"] == "ACTIVE")
        ):
            # แสดงข้อมูลคอลัมน์เรียงตามโจทย์
            col_a, col_b, col_c, col_d = st.columns(4)
            with col_a:
                st.write(f"**Ack:** `{item['ack'] if item['ack'] else '-'}`")
                st.write(f"**Status:** {item['status']}")
            with col_b:
                st.write(f"**Services:** {item['services']}")
                st.write(f"**Problem:** {item['problem_name']}")
            with col_c:
                st.write(f"**Start Date:** {item['start_date']}")
                st.write(f"**Duration:** {item['duration']}")
            with col_d:
                st.write(f"**Resolve Date:** {item['resolve_date'] if item['resolve_date'] else '-'}")
                st.write(f"**Incident:** `{item['incident'] if item['incident'] else '-'}`")

            st.write(f"**Remark (Dynatrace Comment):** {item['remark'] if item['remark'] else '-'}")
            st.markdown("---")

            # --- โซนจัดการข้อมูล (Ack / Remark / Incident) ---
            st.markdown("🛠️ **จัดการข้อมูล Alert นี้:**")
            action_col1, action_col2, action_col3 = st.columns([1, 2, 2])

            # 1. ปุ่ม Ack (กดเพื่อใส่ชื่อ Test)
            with action_col1:
                st.write("**1. Acknowledge**")
                if not item['ack']:
                    if st.button("✅ ACK Alert", key=f"btn_ack_{db_id}", use_container_width=True):
                        supabase.table("alarm_comments").update({"ack": "Test"}).eq("id", db_id).execute()
                        st.success("บันทึก Ack: Test เรียบร้อย!")
                        st.rerun()
                else:
                    st.info(f"ACKED โดย: {item['ack']}")

            # 2. ฟอร์มเพิ่ม/อัปเดต Remark (ส่งเข้า Dynatrace + DB)
            with action_col2:
                st.write("**2. Remark (ส่งเข้า Dynatrace)**")
                with st.form(key=f"form_remark_{db_id}", clear_on_submit=True):
                    new_remark = st.text_input("กรอก Remark / Comment:", key=f"input_remark_{db_id}")
                    btn_remark = st.form_submit_button("🚀 ส่ง Remark")

                    if btn_remark and new_remark:
                        # ยิงเข้า Dynatrace
                        dt_ok = post_comment_to_dynatrace(internal_id, new_remark) if internal_id else True
                        if dt_ok:
                            supabase.table("alarm_comments").update({"remark": new_remark}).eq("id", db_id).execute()
                            st.success("บันทึก Remark สำเร็จ!")
                            st.rerun()
                        else:
                            st.error("❌ ไม่สามารถส่ง Remark ไปยัง Dynatrace ได้")

            # 3. ฟอร์มเพิ่ม Incident Number (ลง DB เท่านั้น)
            with action_col3:
                st.write("**3. Incident Number (ลง DB เท่านั้น)**")
                with st.form(key=f"form_incident_{db_id}", clear_on_submit=True):
                    new_inc = st.text_input("กรอกเลข Incident (เช่น INC12345):", key=f"input_inc_{db_id}")
                    btn_inc = st.form_submit_button("💾 บันทึก Incident")

                    if btn_inc and new_inc:
                        supabase.table("alarm_comments").update({"incident": new_inc}).eq("id", db_id).execute()
                        st.success("บันทึก Incident ลง DB สำเร็จ!")
                        st.rerun()
