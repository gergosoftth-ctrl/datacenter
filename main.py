import ssl
import httpx
import warnings
import urllib3
import json

# 🎯 1. ซ่อน SSL Warnings & บังคับข้ามการตรวจ SSL Certificate
ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

from nicegui import ui, app, run
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
import asyncio
import re
from supabase import create_client, Client, ClientOptions

TZ_TH = pytz.timezone('Asia/Bangkok')

# --- CONFIG & SECRETS ---
SUPABASE_URL = "https://yckwiewglfnuojpnbafz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inlja3dpZXdnbGZudW9qcG5iYWZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM0NTY0MzQsImV4cCI6MjA5OTAzMjQzNH0.XBq4KTL9dVGcGhOVpN90mlaez3SD65qTFWe6o4RsgHI"
DYNATRACE_URL = "https://lss67296.apps.dynatrace.com"
DYNATRACE_TOKEN = "dt0c01.YYB3CLQRXUNBH6LTBHXJTP2V.OOJYZ5FYJEFUSXB4VEJYIANSBZUWFKVHTOXGK6N7OACC2HYYGS6L65PICFIHTIS7"

# 🎯 สร้าง Supabase Client แบบข้ามการตรวจ SSL
supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
    options=ClientOptions(
        httpx_client=httpx.Client(verify=False)
    )
)

# Memory State
state = {
    'active_items': [],
    'resolved_items': [],
    'handover_tasks': [],
    'raw_api_data': {}
}

# ==========================================
# 🟢 HELPER FUNCTIONS
# ==========================================
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

def is_start_within_last_1_hour(start_date_str: str) -> bool:
    if not start_date_str or start_date_str == "-":
        return False
    try:
        now_th = datetime.now(TZ_TH)
        dt_obj = datetime.strptime(f"{now_th.year} {start_date_str}", '%Y %b %d %H:%M')
        dt_obj = dt_obj.replace(tzinfo=TZ_TH)
        return 0 <= (now_th - dt_obj).total_seconds() <= 3600
    except Exception:
        return True

def extract_problem_number(display_id: str) -> int:
    nums = re.findall(r'\d+', str(display_id))
    return int(nums[0]) if nums else 999999999

# ==========================================
# 🟢 DYNATRACE API & DB WORKERS
# ==========================================
def fetch_latest_comment_from_dt(internal_id: str) -> str:
    if not internal_id: return None
    candidate_urls = [
        f"https://lss67296.live.dynatrace.com/api/v2/problems/{internal_id}/comments",
        f"{DYNATRACE_URL}/api/v2/problems/{internal_id}/comments"
    ]
    headers = {"Authorization": f"Api-Token {DYNATRACE_TOKEN}", "Content-Type": "application/json"}
    
    for endpoint in candidate_urls:
        try:
            res = requests.get(endpoint, headers=headers, timeout=3, verify=False)
            if res.status_code == 200:
                comments = res.json().get("comments") or []
                if comments:
                    sorted_comments = sorted(comments, key=lambda x: (x or {}).get("createdAt", 0), reverse=True)
                    first_comment = sorted_comments[0] or {}
                    return str(first_comment.get("content", "")).strip()
        except Exception:
            continue
    return None

def post_comment_to_dynatrace(internal_id: str, comment_text: str) -> bool:
    if not internal_id or not comment_text: return False
    candidate_urls = [
        f"https://lss67296.live.dynatrace.com/api/v2/problems/{internal_id}/comments",
        f"{DYNATRACE_URL}/api/v2/problems/{internal_id}/comments"
    ]
    headers = {"Authorization": f"Api-Token {DYNATRACE_TOKEN}", "Content-Type": "application/json"}
    
    for endpoint in candidate_urls:
        try:
            res = requests.post(endpoint, headers=headers, json={"message": comment_text}, timeout=4, verify=False)
            if res.status_code in [200, 201]:
                return True
        except Exception:
            continue
    return False

def _sync_worker():
    candidate_urls = [
        "https://lss67296.live.dynatrace.com/api/v2/problems?from=-2h&pageSize=50",
        f"{DYNATRACE_URL}/api/v2/problems?from=-2h&pageSize=50",
        f"{DYNATRACE_URL}/platform/classic/environment-api/v2/problems?from=-2h&pageSize=50"
    ]
    headers = {"Authorization": f"Api-Token {DYNATRACE_TOKEN}", "Content-Type": "application/json"}
    
    problems = []
    for endpoint in candidate_urls:
        try:
            res = requests.get(endpoint, headers=headers, timeout=3, verify=False)
            if res.status_code == 200:
                problems = res.json().get("problems") or []
                break
        except Exception:
            continue

    if not problems:
        return

    grouped_problems = {}
    for prob in problems:
        if not isinstance(prob, dict): continue
        root_entity = prob.get("rootCauseEntity") or {}
        root_key = root_entity.get("id") or root_entity.get("name")
        
        if not root_key:
            root_key = f"SINGLE_{prob.get('problemId')}"
            
        if root_key not in grouped_problems:
            grouped_problems[root_key] = []
        grouped_problems[root_key].append(prob)

    for root_key, prob_group in grouped_problems.items():
        sorted_group = sorted(prob_group, key=lambda x: extract_problem_number(x.get("displayId") or x.get("problemId") or ""))
        primary_prob = sorted_group[0]

        internal_id = primary_prob.get("problemId")
        display_id = primary_prob.get("displayId") or f"P-{internal_id}"

        state['raw_api_data'][display_id] = primary_prob

        raw_status = str(primary_prob.get("status", "")).upper()
        dt_status = "ACTIVE" if raw_status == "OPEN" else "RESOLVED"
        start_ms = primary_prob.get("startTime", 0)
        end_ms = primary_prob.get("endTime", -1)
        
        start_dt_str = datetime.fromtimestamp(start_ms / 1000.0, tz=TZ_TH).strftime('%b %d %H:%M') if start_ms else "-"
        resolve_dt_str = datetime.fromtimestamp(end_ms / 1000.0, tz=TZ_TH).strftime('%b %d %H:%M') if end_ms and end_ms > 0 else "-"
        duration_str = calculate_duration(start_ms, end_ms)
        
        mz_list = [mz.get("name") for mz in (primary_prob.get("managementZones") or []) if isinstance(mz, dict) and mz.get("name")]
        services_str = ", ".join(mz_list) if mz_list else "Default"
        title = primary_prob.get("title") or "Unknown Problem"

        all_impacted_entities = []
        for p in prob_group:
            for ent in (p.get("impactedEntities") or []):
                if isinstance(ent, dict):
                    ent_name = ent.get("name")
                    if ent_name and ent_name not in all_impacted_entities:
                        all_impacted_entities.append(ent_name)
        
        impact_str = ", ".join(all_impacted_entities) if all_impacted_entities else "-"

        latest_comment = fetch_latest_comment_from_dt(internal_id)

        try:
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
                "resolve_date": resolve_dt_str if end_ms and end_ms > 0 else None,
            }
            if latest_comment:
                db_payload["remark"] = latest_comment

            supabase.table("alarm_comments").upsert(db_payload, on_conflict="problem_id").execute()
        except Exception as e:
            print(f"⚠️ Supabase Sync DB Error: {str(e)}")
            continue

def _fetch_db_data_worker():
    try:
        _sync_worker()
        active_res = supabase.table("alarm_comments").select("*").eq("status", "ACTIVE").order("id", desc=True).execute().data or []
        raw_resolved = supabase.table("alarm_comments").select("*").eq("status", "RESOLVED").order("id", desc=True).execute().data or []
        resolved_res = [item for item in raw_resolved if is_start_within_last_1_hour(item.get("start_date"))]
        return active_res, resolved_res
    except Exception as e:
        print(f"❌ Worker Error: {str(e)}")
        return [], []

async def async_load_alarm_data():
    res = await run.io_bound(_fetch_db_data_worker)
    if isinstance(res, tuple) and len(res) == 2:
        state['active_items'], state['resolved_items'] = res
    else:
        state['active_items'], state['resolved_items'] = [], []

# ==========================================
# 🟢 COMMON HEADER
# ==========================================
def render_header():
    dark_mode = ui.dark_mode()
    with ui.header().classes('bg-slate-800 text-white justify-between items-center px-6 py-2'):
        with ui.row().classes('items-center gap-3'):
            ui.icon('space_dashboard', size='md')
            ui.label("IT Operations Center").classes('text-xl font-bold')
        
        with ui.row().classes('items-center gap-2'):
            ui.button('🚨 Alarm Monitor', on_click=lambda: ui.navigate.to('/')).props('flat color=white')
            ui.button('🧹 Text Cleaner', on_click=lambda: ui.navigate.to('/cleaner')).props('flat color=white')
            ui.button('📦 กล่องงานฝาก', on_click=lambda: ui.navigate.to('/handover')).props('flat color=white')
            ui.separator().props('vertical color=slate-600').classes('mx-2')
            ui.button(icon='light_mode', on_click=dark_mode.toggle).props('flat round color=white').bind_icon_from(
                dark_mode, 'value', lambda v: 'dark_mode' if v else 'light_mode'
            ).tooltip('สลับ Dark / Light Mode')

# ==========================================
# 📌 PAGE 1: ALARM MONITOR (หน้าหลัก)
# ==========================================
@ui.page('/')
def alarm_page():
    render_header()
    ui.colors(primary='#1976d2')

    async def manual_refresh():
        spinner.visible = True
        await async_load_alarm_data()
        render_alarm_lists.refresh()
        spinner.visible = False

    with ui.column().classes('w-full p-6'):
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('items-center gap-2'):
                ui.label("🚨 Real-time Alarm Management").classes('text-2xl font-bold dark:text-white text-slate-800')
                spinner = ui.spinner(size='lg').props('color=primary')
                spinner.visible = False
            ui.button('🔄 Sync ทั้งหมด', on_click=manual_refresh).props('type=primary icon=refresh')

        @ui.refreshable
        def render_alarm_lists():
            with ui.tabs().classes('w-full') as tabs:
                t_active = ui.tab(f"🔴 Active ({len(state['active_items'])})")
                t_resolved = ui.tab(f"🟢 Resolved ({len(state['resolved_items'])})")

            with ui.tab_panels(tabs, value=t_active).classes('w-full mt-2 bg-transparent'):
                with ui.tab_panel(t_active):
                    if not state['active_items']:
                        ui.label("💡 ไม่มีรายการ Alarm สถานะ ACTIVE ในขณะนี้").classes('text-gray-500 italic mt-2')
                    for item in state['active_items']:
                        render_alarm_card(item, is_active=True, refresh_callback=manual_refresh)
                with ui.tab_panel(t_resolved):
                    if not state['resolved_items']:
                        ui.label("💡 ไม่มีรายการ Alarm สถานะ RESOLVED (ย้อนหลัง 1 ชม.) ในขณะนี้").classes('text-gray-500 italic mt-2')
                    for item in state['resolved_items']:
                        render_alarm_card(item, is_active=False, refresh_callback=manual_refresh)

        render_alarm_lists()
        ui.timer(0.1, manual_refresh, once=True)

def render_alarm_card(item, is_active: bool, refresh_callback):
    db_id, prob_id, internal_id = item["id"], item["problem_id"], item.get("internal_id")
    status_icon = "🔴" if is_active else "🟢"

    # Dialog สำหรับกรอก/แก้ไข Incident ID
    with ui.dialog() as inc_dialog, ui.card().classes('w-80'):
        ui.label('📝 ระบุ Incident ID').classes('text-lg font-bold')
        inc_input = ui.input('Incident Number', value=item.get('incident') or '').classes('w-full')
        with ui.row().classes('w-full justify-end mt-2'):
            ui.button('ยกเลิก', on_click=inc_dialog.close).props('flat')
            ui.button('บันทึก', on_click=lambda: [
                inc_dialog.close(),
                update_alarm(db_id, {"incident": inc_input.value}, refresh_callback)
            ]).props('color=primary')

    # Dialog สำหรับเพิ่ม/แก้ไข Remark (Comment)
    with ui.dialog() as remark_dialog, ui.card().classes('w-96'):
        ui.label('💬 เพิ่ม Remark / Comment ไปที่ Dynatrace').classes('text-lg font-bold')
        remark_input = ui.textarea('ข้อความ Comment', value=item.get('remark') or '').classes('w-full').props('rows=4')
        
        async def submit_comment():
            val = remark_input.value.strip() if remark_input.value else ""
            if not val:
                ui.notify("⚠️ กรุณากรอกข้อความ Comment", color="warning")
                return
            
            remark_dialog.close()
            ui.notify("⏳ กำลังส่ง Comment ไปยัง Dynatrace...", color="info")
            success = await run.io_bound(lambda: post_comment_to_dynatrace(internal_id, val))
            await run.io_bound(lambda: supabase.table("alarm_comments").update({"remark": val}).eq("id", db_id).execute())
            
            if success:
                ui.notify("✅ ส่ง Comment ไปยัง Dynatrace และบันทึกเรียบร้อย!", color="positive")
            else:
                ui.notify("⚠️ บันทึกลง DB สำเร็จ แต่ยิงไป Dynatrace ไม่สำเร็จ", color="warning")
                
            if refresh_callback:
                await refresh_callback()

        with ui.row().classes('w-full justify-end mt-2'):
            ui.button('ยกเลิก', on_click=remark_dialog.close).props('flat')
            ui.button('ส่ง Comment', on_click=submit_comment).props('color=primary')

    # Dialog สำหรับ Debug แสดงผล JSON ดิบ
    raw_json = state['raw_api_data'].get(prob_id)
    json_formatted = json.dumps(raw_json, indent=2, ensure_ascii=False) if raw_json else "⚠️ ไม่พบข้อมูล Raw API (ลองกด Sync อีกครั้ง)"
    
    with ui.dialog() as debug_dialog, ui.card().classes('w-[800px] max-w-full'):
        ui.label(f'🔍 Debug Raw API Data ({prob_id})').classes('text-lg font-bold')
        ui.code(json_formatted).classes('w-full bg-slate-900 text-green-400 p-4 rounded max-h-[500px] overflow-auto text-xs')
        with ui.row().classes('w-full justify-end mt-2'):
            ui.button('ปิดหน้าต่าง', on_click=debug_dialog.close).props('flat')

    # URL ปัญหา Dynatrace
    dt_link_url = item.get('url') or (raw_json.get('problemUrl') if isinstance(raw_json, dict) else None) or f"https://lss67296.live.dynatrace.com/#problems/problemdetails;pid={internal_id}"

    with ui.expansion().classes('w-full dark:bg-slate-800 bg-white border dark:border-slate-700 rounded mb-2') as exp:
        with exp.add_slot('header'):
            with ui.row().classes('w-full items-center justify-between'):
                lbl = ui.label(f"{status_icon} [{item.get('type', 'Dynatrace')}] {ack_prefix(item)}[{prob_id}] {item['problem_name']} | Service: {item.get('services', 'Default')}").classes('font-bold text-sm py-2 cursor-pointer w-full dark:text-slate-100')
                
                # 🎯 ใช้ ui.context_menu() แก้ไข Warning / Error touch-position
                with ui.context_menu():
                    ui.menu_item('🔗 เปิดใน Dynatrace', on_click=lambda: ui.run_javascript(f'window.open("{dt_link_url}", "_blank");'))
                    ui.menu_item('🔍 Debug JSON (API)', on_click=debug_dialog.open)
                    ui.menu_item('💬 เพิ่ม Remark / Comment', on_click=remark_dialog.open)
                    ui.menu_item('📝 เพิ่ม/แก้ไข Incident ID', on_click=inc_dialog.open)
                    ui.menu_item('✅ ACK Alert', on_click=lambda: update_alarm(db_id, {"ack": "TEST"}, refresh_callback))
                    ui.menu_item('🧹 Clear Status (RESOLVED)', on_click=lambda: update_alarm(db_id, {"status": "RESOLVED"}, refresh_callback))

        # กล่องรายละเอียด Alert
        with ui.column().classes('p-4 dark:bg-slate-900/50 bg-gray-50 gap-3 w-full border-t dark:border-slate-700'):
            with ui.grid(columns=3).classes('w-full gap-4 text-sm'):
                with ui.column().classes('gap-1'):
                    ui.label("📌 Status:").classes('font-bold text-gray-500 text-xs')
                    ui.badge(item.get('status', '-'), color='red' if is_active else 'green').classes('w-fit')

                with ui.column().classes('gap-1'):
                    ui.label("🛠️ Services:").classes('font-bold text-gray-500 text-xs')
                    ui.label(item.get('services') or '-').classes('font-medium dark:text-slate-200 text-slate-800')

                with ui.column().classes('gap-1'):
                    ui.label("🎫 Incident ID:").classes('font-bold text-gray-500 text-xs')
                    ui.label(item.get('incident') or '- None -').classes('font-semibold text-blue-500')

                with ui.column().classes('gap-1'):
                    ui.label("🕒 Start Date:").classes('font-bold text-gray-500 text-xs')
                    ui.label(item.get('start_date') or '-').classes('dark:text-slate-300 text-slate-700')

                with ui.column().classes('gap-1'):
                    ui.label("🏁 Resolve Date:").classes('font-bold text-gray-500 text-xs')
                    ui.label(item.get('resolve_date') or '- (Active)').classes('dark:text-slate-300 text-slate-700')

                with ui.column().classes('gap-1'):
                    ui.label("⏱️ Duration:").classes('font-bold text-gray-500 text-xs')
                    ui.label(item.get('duration') or '-').classes('dark:text-slate-300 text-slate-700')

                with ui.column().classes('gap-1 col-span-2'):
                    ui.label("💥 Impact:").classes('font-bold text-gray-500 text-xs')
                    ui.label(item.get('impact') or '-').classes('dark:text-slate-200 text-slate-800')

                with ui.column().classes('gap-1'):
                    ui.label("👤 Acknowledge By:").classes('font-bold text-gray-500 text-xs')
                    ui.label(item.get('ack') or '- Unacknowledged -').classes('font-bold text-amber-500')

            # ปุ่มเปิด Dynatrace
            with ui.row().classes('w-full items-center justify-between dark:bg-slate-800 bg-blue-50 p-2.5 rounded border dark:border-slate-700 border-blue-100 mt-1'):
                with ui.row().classes('items-center gap-2 overflow-hidden'):
                    ui.icon('link', size='xs').classes('text-blue-500')
                    ui.label("Dynatrace Problem Link:").classes('font-bold text-xs dark:text-blue-400 text-blue-900')
                    ui.label(dt_link_url).classes('text-xs dark:text-blue-300 text-blue-700 truncate max-w-md')
                
                ui.html(f'''
                    <a href="{dt_link_url}" 
                       target="_blank" 
                       rel="noopener noreferrer" 
                       onclick="event.stopPropagation();"
                       style="display: inline-flex; align-items: center; background-color: #1976d2; color: white; padding: 6px 14px; border-radius: 4px; font-size: 12px; font-weight: bold; text-decoration: none;">
                       เปิดใน Dynatrace ↗
                    </a>
                ''')

            with ui.column().classes('w-full gap-1 mt-1'):
                ui.label("💬 Remark / Comment:").classes('font-bold text-gray-500 text-xs')
                ui.code(item.get('remark') or '- None -').classes('w-full bg-slate-900 text-green-400 p-2.5 rounded text-xs')

def ack_prefix(item):
    ack = f"[ACK: {item['ack']}] " if item.get('ack') else ""
    inc = f"[INC: {item['incident']}] " if item.get('incident') else ""
    return f"{ack}{inc}"

async def update_alarm(db_id, payload, refresh_callback):
    await run.io_bound(lambda: supabase.table("alarm_comments").update(payload).eq("id", db_id).execute())
    ui.notify("✅ อัปเดตข้อมูลสำเร็จ!", color="positive")
    if refresh_callback:
        await refresh_callback()

# ==========================================
# 📌 PAGE 2: TEXT CLEANER
# ==========================================
@ui.page('/cleaner')
def cleaner_page():
    render_header()
    
    with ui.column().classes('w-full p-6 max-w-5xl mx-auto gap-4'):
        ui.label("🧹 Text Cleaner Tool").classes('text-2xl font-bold dark:text-white text-slate-800')
        ui.label("เครื่องมือทำความสะอาดข้อความ ตัดช่องว่าง แปลงตัวพิมพ์ และจัด Format สำหรับงาน Ops").classes('text-sm text-gray-500')

        input_text = ui.textarea(label="ข้อความต้นทาง (Input Text)", placeholder="วางข้อความที่ต้องการ Clean ที่นี่...").classes('w-full').props('outlined rows=6')
        output_text = ui.textarea(label="ผลลัพธ์ (Cleaned Output)").classes('w-full dark:bg-slate-800 bg-gray-50').props('outlined rows=6 readonly')

        def clean_spaces():
            val = input_text.value or ""
            cleaned = re.sub(r'[ \t]+', ' ', val)
            cleaned = "\n".join([line.strip() for line in cleaned.splitlines()])
            output_text.value = cleaned
            ui.notify("✨ ลบเว้นวรรคซ้ำเรียบร้อย!", color="positive")

        def remove_empty_lines():
            val = input_text.value or ""
            lines = [line.strip() for line in val.splitlines() if line.strip()]
            output_text.value = "\n".join(lines)
            ui.notify("✨ ลบบรรทัดว่างเรียบร้อย!", color="positive")

        def to_uppercase():
            output_text.value = (input_text.value or "").upper()

        def to_lowercase():
            output_text.value = (input_text.value or "").lower()

        def copy_to_clipboard():
            ui.run_javascript(f'navigator.clipboard.writeText({repr(output_text.value)});')
            ui.notify("📋 ก๊อปปี้ผลลัพธ์ลง Clipboard แล้ว!", color="info")

        with ui.row().classes('gap-2 wrap'):
            ui.button('ลบเว้นวรรคซ้ำ', on_click=clean_spaces).props('color=primary')
            ui.button('ลบบรรทัดว่าง', on_click=remove_empty_lines).props('color=primary outline')
            ui.button('UPPERCASE', on_click=to_uppercase).props('color=secondary flat')
            ui.button('lowercase', on_click=to_lowercase).props('color=secondary flat')
            ui.button('📋 Copy ผลลัพธ์', on_click=copy_to_clipboard).props('color=positive icon=content_copy')

# ==========================================
# 📌 PAGE 3: กล่องงานฝาก (HANDOVER TASKS)
# ==========================================
@ui.page('/handover')
def handover_page():
    render_header()

    async def load_handover_tasks():
        def _fetch():
            try:
                return supabase.table("handover_tasks").select("*").order("id", desc=True).execute().data or []
            except Exception:
                return []
        state['handover_tasks'] = await run.io_bound(_fetch)

    async def add_task(title, detail, assignee, shift):
        if not title:
            ui.notify("⚠️ กรุณากรอกหัวข้องาน", color="warning")
            return
        payload = {
            "title": title, "detail": detail, "assignee": assignee,
            "shift": shift, "status": "PENDING",
            "created_at": datetime.now(TZ_TH).strftime('%Y-%m-%d %H:%M')
        }
        try:
            await run.io_bound(lambda: supabase.table("handover_tasks").insert(payload).execute())
            ui.notify("📌 บันทึกงานฝากเรียบร้อย!", color="positive")
            render_handover_list.refresh()
        except Exception as e:
            ui.notify(f"❌ Error: {str(e)}", color="negative")

    async def update_task_status(task_id, new_status):
        await run.io_bound(lambda: supabase.table("handover_tasks").update({"status": new_status}).eq("id", task_id).execute())
        ui.notify(f"อัปเดตสถานะเป็น {new_status}", color="info")
        render_handover_list.refresh()

    async def delete_task(task_id):
        await run.io_bound(lambda: supabase.table("handover_tasks").delete().eq("id", task_id).execute())
        ui.notify("🗑️ ลบงานฝากเรียบร้อย", color="negative")
        render_handover_list.refresh()

    with ui.column().classes('w-full p-6 max-w-6xl mx-auto gap-4'):
        with ui.row().classes('w-full justify-between items-center'):
            ui.label("📦 กล่องงานฝาก (Shift Handover Tasks)").classes('text-2xl font-bold dark:text-white text-slate-800')
            
            with ui.dialog() as dlg, ui.card().classes('w-96'):
                ui.label("ฝากงานใหม่ประจำกะ").classes('text-lg font-bold')
                t_in = ui.input(label="หัวข้องาน *").classes('w-full')
                d_in = ui.textarea(label="รายละเอียดงาน").classes('w-full')
                a_in = ui.input(label="ผู้ฝากงาน / ผู้รับผิดชอบ").classes('w-full')
                s_in = ui.select(['กะเช้า', 'กะบ่าย', 'กะดึก'], value='กะเช้า', label='รอบกะ').classes('w-full')
                
                with ui.row().classes('w-full justify-end mt-2'):
                    ui.button('ยกเลิก', on_click=dlg.close).props('flat')
                    ui.button('บันทึกงานฝาก', on_click=lambda: [add_task(t_in.value, d_in.value, a_in.value, s_in.value), dlg.close()]).props('color=primary')

            ui.button('➕ เพิ่มงานฝาก', on_click=dlg.open).props('color=primary icon=add')

        @ui.refreshable
        async def render_handover_list():
            await load_handover_tasks()
            if not state['handover_tasks']:
                ui.label("💡 ไม่มีงานฝากในระบบ").classes('text-gray-500 italic mt-4')
                return

            with ui.grid(columns=3).classes('w-full gap-4 mt-2'):
                for task in state['handover_tasks']:
                    t_id = task["id"]
                    status = task.get("status", "PENDING")
                    status_color = "warning" if status == "PENDING" else ("info" if status == "IN_PROGRESS" else "positive")
                    
                    with ui.card().classes('w-full dark:bg-slate-800 bg-white border dark:border-slate-700 shadow-sm p-4 relative'):
                        with ui.row().classes('justify-between items-center w-full'):
                            lbl_title = ui.label(task["title"]).classes('font-bold text-base cursor-pointer dark:text-white text-slate-800')
                            ui.badge(status, color=status_color)
                            
                            with lbl_title:
                                # 🎯 ใช้ ui.context_menu()
                                with ui.context_menu():
                                    ui.menu_item('🟡 กำลังรอ (Pending)', on_click=lambda id=t_id: update_task_status(id, "PENDING"))
                                    ui.menu_item('🔵 กำลังทำ (In Progress)', on_click=lambda id=t_id: update_task_status(id, "IN_PROGRESS"))
                                    ui.menu_item('🟢 เสร็จแล้ว (Done)', on_click=lambda id=t_id: update_task_status(id, "DONE"))
                                    ui.separator()
                                    ui.menu_item('🗑️ ลบงานนี้', on_click=lambda id=t_id: delete_task(id))

                        ui.label(task.get("detail") or "-").classes('text-sm dark:text-slate-300 text-gray-600 my-2')
                        
                        with ui.row().classes('w-full justify-between items-center text-xs text-gray-400 mt-2 border-t dark:border-slate-700 pt-2'):
                            ui.label(f"👤 {task.get('assignee') or 'ไม่ระบุ'} ({task.get('shift') or '-'})")
                            ui.label(f"🕒 {task.get('created_at') or '-'}")

        render_handover_list()

# Background Sync
app.on_startup(lambda: asyncio.create_task(background_db_sync()))

async def background_db_sync():
    while True:
        await asyncio.sleep(30)
        await run.io_bound(_sync_worker)

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="IT Operations Management Tool", port=8501, reload=False)