import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
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

# --- 1. ดึงข้อมูลแบบแยก OPEN และ RESOLVED ล่าสุด ---
def fetch_dynatrace_problems():
    dt_url = get_dt_base_url()
    token = st.secrets["dynatrace"]["API_TOKEN"]
    headers = {"Authorization": f"Api-Token {token}", "Content-Type": "application/json"}
    
    fields_query = "comments,displayId,problemId,title,status,startTime,endTime,managementZones,impactedEntities"
    all_problems = []

    # 1.1 ดึงรายการที่ยัง OPEN อยู่ทั้งหมด (ไม่จำกัดเวลา)
    endpoint_open = f"{dt_url}/api/v2/problems?problemSelector=status(\"OPEN\")&fields={fields_query}&pageSize=50"
    try:
        res_open = requests.get(endpoint_open, headers=headers, timeout=10)
        if res_open.status_code == 200:
            all_problems.extend(res_open.json().get("problems", []))
    except Exception:
        pass

    # 1.2 ดึงรายการที่ RESOLVED/CLOSED ย้อนหลัง 24 ชั่วโมง
    endpoint_resolved = f"{dt_url}/api/v2/problems?problemSelector=status(\"RESOLVED\",\"CLOSED\")&from=-24h&fields={fields_query}&pageSize=50"
    try:
        res_resolved = requests.get(endpoint_resolved, headers=headers, timeout=10)
        if res_resolved.status_code == 200:
            all_problems.extend(res_resolved.json().get("problems", []))
    except Exception:
        pass

    return all_problems

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

def is_within_last_1_hour(start_date_str: str) -> bool:
    if not start_date_str or start_date_str == "-":
        return False
    try:
        now_th = datetime.now(TZ_TH)
        dt_obj = datetime.strptime(start_date_str, '%b %d %H:%M')
        dt_obj = dt_obj.replace(year=now_th.year, tzinfo=TZ_TH)
        diff = now_th - dt_obj
        return 0 <= diff.total_seconds() <= 3600
    except Exception:
        return True

# --- 2. Sync และตรวจสอบสถานะกับ DB ---
def sync_dynatrace_to_db(supabase: Client, problems: list):
    """ ดึง Alarm จาก Dynatrace เข้า Supabase และสั่ง Auto-Resolve รายการที่ไม่อยู่ใน Open List """
    
    # ดึง ID ของปัญหาทั้งหมดที่ Dynatrace แจ้งว่ายัง OPEN อยู่
    open_problem_ids = set()
    
    seen_ids = set()
    unique_problems = []
    for p in problems:
        pid = p.get("displayId") or p.get("problemId")
        if pid not in seen_ids:
            seen_ids.add(pid)
            unique_problems.append(p)
            if p.get("status") == "OPEN":
                open_problem_ids.add(pid)

    # 1. อัปเดตข้อมูลจาก API เข้า DB
    for prob in unique_problems:
        internal_id = prob.get("problemId")
        display_id = prob.get("displayId", f"P-{internal_id}")
        raw_status = prob.get("status", "").upper()
        dt_status = "ACTIVE" if raw_status == "OPEN" else "RESOLVED"
        
        start_ms = prob.get("startTime", 0)
        end_ms = prob.get("endTime", -1)
        
        start_dt_str = datetime.fromtimestamp(start_ms / 1000.0, tz=TZ_TH).strftime('%b %d %H:%M') if start_ms else "-"
        resolve_dt_str = datetime.fromtimestamp(end_ms / 1000.0, tz=TZ_TH).strftime('%b %d %H:%M') if end_ms > 0 else "-"
        duration_str = calculate_duration(start_ms, end_ms)

        mz_list = [mz.get("name") for mz in prob.get("managementZones", [])] if prob.get("managementZones") else []
        services_str = ", ".join(mz_list) if mz_list else "Default"
        title = prob.get("title", "Unknown Problem")

        impacted_list = [ent.get("name") for ent in prob.get("impactedEntities", [])] if prob.get("impactedEntities") else []
        impact_str = ", ".join(impacted_list) if impacted_list else "-"

        dt_comments = prob.get("comments", [])
        latest_dt_comment = dt_comments[-1].get("message") if dt_comments else None

        existing = supabase.table("alarm_comments").select("id, status").eq("problem_id", display_id).execute().data

        if not existing:
            db_payload = {
                "type": "Dynatrace",
                "problem_id": display_id,
                "internal_id": internal_id,
                "status": dt_status,
                "services": services_str,
                "problem_name": title,
                "impact": impact_str,
                "start_date": start_dt_str,
                "duration": duration_str,
                "resolve_date": resolve_dt_str if end_ms > 0 else None,
                "ack": None,
                "remark": latest_dt_comment,
                "incident": None
            }
            try:
                supabase.table("alarm_comments").insert(db_payload).execute()
            except Exception:
                pass
        else:
            update_payload = {
                "status": dt_status,
                "duration": duration_str,
                "impact": impact_str
            }
            if end_ms > 0:
                update_payload["resolve_date"] = resolve_dt_str
            if dt_status == "RESOLVED" and latest_dt_comment:
                update_payload["remark"] = latest_dt_comment

            supabase.table("alarm_comments").update(update_payload).eq("problem_id", display_id).execute()

    # 2. เช็ก DB ฝั่ง ACTIVE: หากรายการไหนใน DB ไม่อยู่ใน open_problem_ids ของ Dynatrace แล้ว ให้สั่งเปลี่ยนเป็น RESOLVED ทันที
    active_in_db = supabase.table("alarm_comments").select("problem_id").eq("status", "ACTIVE").eq("type", "Dynatrace").execute().data
    for db_item in active_in_db:
        db_pid = db_item.get("problem_id")
        if db_pid not in open_problem_ids:
            now_str = datetime.now(TZ_TH).strftime('%b %d %H:%M')
            supabase.table("alarm_comments").update({
                "status": "RESOLVED",
                "resolve_date": now_str
            }).eq("problem_id", db_pid).execute()

def render_alarm_list(supabase: Client, items: list, is_active_tab: bool):
    if not items:
        status_label = "ACTIVE" if is_active_tab else "RESOLVED"
        st.info(f"💡 ไม่มีรายการ Alarm สถานะ {status_label} ในขณะนี้")
        return

    for item in items:
        db_id = item["id"]
        prob_id = item["problem_id"]
        internal_id = item.get("internal_id")
        status_color = "🔴" if is_active_tab else "🟢"

        # แท็ก Type
        type_tag = f"[{item.get('type', 'Dynatrace')}]"
        
        # แท็ก ACK และ INC
        ack_prefix = f"[ACK: {item['ack']}] " if item.get('ack') else ""
        inc_prefix = f"[INC: {item['incident']}] " if item.get('incident') else ""
        
        # แสดง Type ไว้หน้าสุด
        expander_title = (
            f"{status_color} {type_tag} {ack_prefix}{inc_prefix}**[{prob_id}]** {item['problem_name']} | "
            f"Service: {item['services']} | Impact: {item.get('impact', '-')}"
        )

        # 🎯 ปรับตรงนี้ให้ expanded=False (หุบไว้ก่อนเสมอนั่นเองครับ)
        with st.expander(expander_title, expanded=False):
            # แสดงรายละเอียดคอลัมน์
            col_type, col_a, col_b, col_c, col_d = st.columns([1, 1.5, 2, 2, 2])
            with col_type:
                st.write(f"**Type:** `{item.get('type', 'Dynatrace')}`")
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

            st.write(f"**Impact:** `{item.get('impact', '-')}`")
            st.write(f"**Remark (Dynatrace Comment):** {item['remark'] if item['remark'] else '-'}")
            
            if internal_id:
                dt_portal_link = f"https://lss67296.apps.dynatrace.com/ui/apps/dynatrace.classic.problems/#problems/problemdetails;gtf=-2h;gf=all;pid={internal_id}"
                st.markdown(f"🔗 [เปิดดูรายละเอียดบน Dynatrace UI]({dt_portal_link})")

            st.markdown("---")

            # --- โซนจัดการข้อมูล (Ack / Remark / Incident) ---
            st.markdown("🛠️ **จัดการข้อมูล Alert นี้:**")
            action_col1, action_col2, action_col3 = st.columns([1, 2, 2])

            with action_col1:
                st.write("**1. Acknowledge**")
                if not item['ack']:
                    if st.button("✅ ACK Alert", key=f"btn_ack_{db_id}", use_container_width=True):
                        supabase.table("alarm_comments").update({"ack": "Test"}).eq("id", db_id).execute()
                        st.success("บันทึก Ack: Test เรียบร้อย!")
                        st.rerun()
                else:
                    st.info(f"ACKED โดย: {item['ack']}")

            with action_col2:
                st.write("**2. Remark (ส่งเข้า Dynatrace)**")
                with st.form(key=f"form_remark_{db_id}", clear_on_submit=True):
                    new_remark = st.text_input("กรอก Remark / Comment:", key=f"input_remark_{db_id}")
                    btn_remark = st.form_submit_button("🚀 ส่ง Remark")

                    if btn_remark and new_remark:
                        dt_ok = post_comment_to_dynatrace(internal_id, new_remark) if internal_id else True
                        if dt_ok:
                            supabase.table("alarm_comments").update({"remark": new_remark}).eq("id", db_id).execute()
                            st.success("บันทึก Remark สำเร็จ!")
                            st.rerun()
                        else:
                            st.error("❌ ไม่สามารถส่ง Remark ไปยัง Dynatrace ได้")

            with action_col3:
                st.write("**3. Incident Number (ลง DB เท่านั้น)**")
                with st.form(key=f"form_incident_{db_id}", clear_on_submit=True):
                    new_inc = st.text_input("กรอกเลข Incident (เช่น INC12345):", key=f"input_inc_{db_id}")
                    btn_inc = st.form_submit_button("💾 บันทึก Incident")

                    if btn_inc and new_inc:
                        supabase.table("alarm_comments").update({"incident": new_inc}).eq("id", db_id).execute()
                        st.success("บันทึก Incident ลง DB สำเร็จ!")
                        st.rerun()

def run_app():
    st.title("🚨 Alarm Management Center")
    st.caption("ตารางติดตามสถานะการแจ้งเตือนรองรับ Multi-Source Monitoring")

    try:
        supabase = init_supabase()
    except Exception:
        st.error("❌ ไม่สามารถเชื่อมต่อ Supabase ได้")
        return

    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("🔄 Sync Real-time", type="primary", use_container_width=True):
            st.rerun()

    with st.spinner("กำลังอัปเดตข้อมูล Alarm จาก Dynatrace..."):
        dt_problems = fetch_dynatrace_problems()
        if dt_problems:
            sync_dynatrace_to_db(supabase, dt_problems)

    active_res = supabase.table("alarm_comments").select("*").eq("status", "ACTIVE").order("id", desc=True).execute().data
    
    raw_resolved = supabase.table("alarm_comments").select("*").eq("status", "RESOLVED").order("id", desc=True).execute().data
    resolved_res = [item for item in raw_resolved if is_within_last_1_hour(item.get("start_date"))]

    tab_active, tab_resolved = st.tabs([
        f"🔴 Active Alarms ({len(active_res)})", 
        f"🟢 Resolved History - ล่าสุด 1 ชม. ({len(resolved_res)})"
    ])

    with tab_active:
        st.subheader("⚠️ รายการ Alarm ที่กำลังเกิดขึ้น (Active)")
        render_alarm_list(supabase, active_res, is_active_tab=True)

    with tab_resolved:
        st.subheader("✅ ประวัติ Alarm ที่แก้ไขแล้ว (นับเฉพาะ Start Date ย้อนหลังไม่เกิน 1 ชั่วโมง)")
        render_alarm_list(supabase, resolved_res, is_active_tab=False)
