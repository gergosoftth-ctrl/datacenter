import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time
from supabase import create_client, Client
from streamlit_autorefresh import st_autorefresh

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

# --- 1. ดึงรายการ Problems จาก Dynatrace API ย้อนหลังแค่ 1 ชั่วโมง (-1h) ---
def fetch_dynatrace_problems():
    dt_url = get_dt_base_url()
    token = st.secrets["dynatrace"]["API_TOKEN"]
    headers = {"Authorization": f"Api-Token {token}", "Content-Type": "application/json"}
    
    endpoint = f"{dt_url}/api/v2/problems?from=-1h&pageSize=50"
    
    try:
        res = requests.get(endpoint, headers=headers, timeout=8)
        if res.status_code == 200:
            return res.json().get("problems", [])
        return []
    except Exception as e:
        st.warning(f"⚠️ ไม่สามารถเชื่อมต่อ Dynatrace API ได้ชั่วคราว: {str(e)}")
        return []

# --- 2. ดึง Comment ล่าสุดยิงตรงไปที่ Endpoint /comments ของแต่ละ Problem ---
def fetch_latest_comment_from_dt(internal_id: str) -> str:
    if not internal_id:
        return None
    dt_url = get_dt_base_url()
    token = st.secrets["dynatrace"]["API_TOKEN"]
    headers = {"Authorization": f"Api-Token {token}", "Content-Type": "application/json"}
    
    endpoint = f"{dt_url}/api/v2/problems/{internal_id}/comments"
    
    try:
        res = requests.get(endpoint, headers=headers, timeout=4)
        if res.status_code == 200:
            data = res.json()
            comments = data.get("comments", [])
            if comments:
                latest = comments[-1]
                author = latest.get("authorName") or latest.get("author") or "User"
                msg = latest.get("message", "").strip()
                if msg:
                    return f"[{author}]: {msg}" if author and author != "User" else msg
    except Exception:
        pass
    return None

# --- 3. ยิง Comment จาก Dashboard กลับไป Dynatrace ---
def post_comment_to_dynatrace(problem_id: str, comment_text: str):
    dt_url = get_dt_base_url()
    token = st.secrets["dynatrace"]["API_TOKEN"]
    headers = {"Authorization": f"Api-Token {token}", "Content-Type": "application/json"}
    endpoint = f"{dt_url}/api/v2/problems/{problem_id}/comments"
    
    try:
        res = requests.post(endpoint, headers=headers, json={"message": comment_text}, timeout=5)
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

# 🎯 ฟังก์ชันเช็กว่า Start Date อยู่ภายใน 1 ชั่วโมงล่าสุดหรือไม่
def is_start_within_last_1_hour(start_date_str: str) -> bool:
    if not start_date_str or start_date_str == "-":
        return False
    try:
        now_th = datetime.now(TZ_TH)
        # แปลงข้อความสตริงสตาร์ทเดท เช่น "Aug 04 11:30" เป็น datetime object
        dt_obj = datetime.strptime(start_date_str, '%b %d %H:%M')
        dt_obj = dt_obj.replace(year=now_th.year, tzinfo=TZ_TH)
        
        diff_seconds = (now_th - dt_obj).total_seconds()
        # เช็กว่าเวลาเกิดตั้งแต่ 0 ถึงไม่เกิน 3600 วินาที (1 ชั่วโมง)
        return 0 <= diff_seconds <= 3600
    except Exception:
        return True

# --- 4. Sync ข้อมูลลง DB ---
def sync_dynatrace_to_db(supabase: Client, problems: list):
    if not problems:
        return

    open_problem_ids = set()
    seen_ids = set()
    unique_problems = []

    for p in problems:
        display_id = p.get("displayId") or p.get("problemId")
        internal_id = p.get("problemId")
        
        if display_id not in seen_ids:
            seen_ids.add(display_id)
            unique_problems.append(p)
            
            if str(p.get("status", "")).upper() == "OPEN":
                open_problem_ids.add(display_id)
                open_problem_ids.add(internal_id)

    # บันทึก/อัปเดตลง DB
    for prob in unique_problems:
        internal_id = prob.get("problemId")
        display_id = prob.get("displayId", f"P-{internal_id}")
        raw_status = str(prob.get("status", "")).upper()
        
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

        # ดึง Comment ล่าสุด
        latest_comment = fetch_latest_comment_from_dt(internal_id)

        try:
            existing = supabase.table("alarm_comments").select("id, status, remark").eq("problem_id", display_id).execute().data

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
                    "remark": latest_comment,
                    "incident": None
                }
                supabase.table("alarm_comments").insert(db_payload).execute()
            else:
                update_payload = {
                    "status": dt_status,
                    "duration": duration_str,
                    "impact": impact_str
                }
                if end_ms > 0:
                    update_payload["resolve_date"] = resolve_dt_str
                
                if latest_comment:
                    update_payload["remark"] = latest_comment

                supabase.table("alarm_comments").update(update_payload).eq("problem_id", display_id).execute()
        except Exception:
            continue

# --- 5. Render หน้า UI ---
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

        type_tag = f"[{item.get('type', 'Dynatrace')}]"
        ack_prefix = f"[ACK: {item['ack']}] " if item.get('ack') else ""
        inc_prefix = f"[INC: {item['incident']}] " if item.get('incident') else ""
        
        expander_title = (
            f"{status_color} {type_tag} {ack_prefix}{inc_prefix}**[{prob_id}]** {item['problem_name']} | "
            f"Service: {item['services']} | Impact: {item.get('impact', '-')}"
        )

        with st.expander(expander_title, expanded=False):
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
            
            remark_text = item['remark'] if item['remark'] else '-'
            st.markdown(f"**Remark (Comment):**\n```\n{remark_text}\n
