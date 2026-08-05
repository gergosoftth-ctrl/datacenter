from nicegui import ui, app
import requests
import pandas as pd
from datetime import datetime
import pytz
import asyncio
import re
from supabase import create_client, Client

TZ_TH = pytz.timezone('Asia/Bangkok')

# --- CONFIG & SECRETS ---
SUPABASE_URL = "https://yckwiewglfnuojpnbafz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inlja3dpZXdnbGZudW9qcG5iYWZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM0NTY0MzQsImV4cCI6MjA5OTAzMjQzNH0.XBq4KTL9dVGcGhOVpN90mlaez3SD65qTFWe6o4RsgHI"
DYNATRACE_URL = "https://lss67296.apps.dynatrace.com"
DYNATRACE_TOKEN = "dt0c01.YYB3CLQRXUNBH6LTBHXJTP2V.OOJYZ5FYJEFUSXB4VEJYIANSBZUWFKVHTOXGK6N7OACC2HYYGS6L65PICFIHTIS7"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Memory State
state = {
    'active_items': [],
    'resolved_items': [],
    'handover_tasks': []
}

# ==========================================
# 🟢 APP 1: DYNATRACE ALARM MONITOR FUNCTIONS
# ==========================================
def fetch_dynatrace_problems():
    endpoint = f"{DYNATRACE_URL}/api/v2/problems?from=-1h&pageSize=50"
    headers = {"Authorization": f"Api-Token {DYNATRACE_TOKEN}", "Content-Type": "application/json"}
    try:
        res = requests.get(endpoint, headers=headers, timeout=8)
        return res.json().get("problems", []) if res.status_code == 200 else []
    except Exception:
        return []

def fetch_latest_comment_from_dt(internal_id: str) -> str:
    if not internal_id: return None
    endpoint = f"{DYNATRACE_URL}/api/v2/problems/{internal_id}/comments"
    headers = {"Authorization": f"Api-Token {DYNATRACE_TOKEN}", "Content-Type": "application/json"}
    try:
        res = requests.get(endpoint, headers=headers, timeout=4)
        if res.status_code == 200:
            comments = res.json().get("comments", [])
            if comments:
                return comments[0].get("content", "").strip()
    except Exception:
        pass
    return None

def post_comment_to_dynatrace(problem_id: str, comment_text: str):
    endpoint = f"{DYNATRACE_URL}/api/v2/problems/{problem_id}/comments"
    headers = {"Authorization": f"Api-Token {DYNATRACE_TOKEN}", "Content-Type": "application/json"}
    try:
        res = requests.post(endpoint, headers=headers, json={"message": comment_text}, timeout=5)
        return res.status_code in [200, 201]
    except Exception:
        return False

def sync_dynatrace_to_db():
    problems = fetch_dynatrace_problems()
    if not problems: return
    seen_ids = set()
    for prob in problems:
        internal_id = prob.get("problemId")
        display_id = prob.get("displayId", f"P-{internal_id}")
        if display_id in seen_ids: continue
        seen_ids.add(display_id)

        raw_status = str(prob.get("status", "")).upper()
        dt_status = "ACTIVE" if raw_status == "OPEN" else "RESOLVED"
        start_ms = prob.get("startTime", 0)
        end_ms = prob.get("endTime", -1)
        
        start_dt_str = datetime.fromtimestamp(start_ms / 1000.0, tz=TZ_TH).strftime('%b %d %H:%M') if start_ms else "-"
        resolve_dt_str = datetime.fromtimestamp(end_ms / 1000.0, tz=TZ_TH).strftime('%b %d %H:%M') if end_ms > 0 else "-"
        
        mz_list = [mz.get("name") for mz in prob.get("managementZones", [])] if prob.get("managementZones") else []
        services_str = ", ".join(mz_list) if mz_list else "Default"
        title = prob.get("title", "Unknown Problem")
        impacted_list = [ent.get("name") for ent in prob.get("impactedEntities", [])] if prob.get("impactedEntities") else []
        impact_str = ", ".join(impacted_list) if impacted_list else "-"

        latest_comment = fetch_latest_comment_from_dt(internal_id)

        try:
            existing = supabase.table("alarm_comments").select("id").eq("problem_id", display_id).execute().data
            if not existing:
                db_payload = {
                    "type": "Dynatrace", "problem_id": display_id, "internal_id": internal_id,
                    "status": dt_status, "services": services_str, "problem_name": title,
                    "impact": impact_str, "start_date": start_dt_str, "duration": "-",
                    "resolve_date": resolve_dt_str if end_ms > 0 else None,
                    "ack": None, "remark": latest_comment, "incident": None
                }
                supabase.table("alarm_comments").insert(db_payload).execute()
            else:
                update_payload = {"status": dt_status, "impact": impact_str}
                if end_ms > 0: update_payload["resolve_date"] = resolve_dt_str
                if latest_comment: update_payload["remark"] = latest_comment
                supabase.table("alarm_comments").update(update_payload).eq("problem_id", display_id).execute()
        except Exception:
            continue

def load_alarm_data():
    try:
        state['active_items'] = supabase.table("alarm_comments").select("*").eq("status", "ACTIVE").order("id", desc=True).execute().data
        state['resolved_items'] = supabase.table("alarm_comments").select("*").eq("status", "RESOLVED").order("id", desc=True).limit(30).execute().data
    except Exception:
        pass

# ==========================================
# 🟢 COMMON HEADER / NAVIGATION BAR
# ==========================================
def render_header():
    with ui.header().classes('bg-slate-800 text-white justify-between items-center px-6 py-2'):
        with ui.row().classes('items-center gap-3'):
            ui.icon('space_dashboard', size='md')
            ui.label("IT Operations Center").classes('text-xl font-bold')
        
        with ui.row().classes('gap-2'):
            ui.button('🚨 Alarm Monitor', on_click=lambda: ui.navigate.to('/')).props('flat color=white')
            ui.button('🧹 Text Cleaner', on_click=lambda: ui.navigate.to('/cleaner')).props('flat color=white')
            ui.button('📦 กล่องงานฝาก', on_click=lambda: ui.navigate.to('/handover')).props('flat color=white')

# ==========================================
# 📌 PAGE 1: ALARM MONITOR (หน้าหลัก)
# ==========================================
@ui.page('/')
def alarm_page():
    render_header()
    ui.colors(primary='#1976d2')

    with ui.column().classes('w-full p-6'):
        with ui.row().classes('w-full justify-between items-center mb-4'):
            ui.label("🚨 Real-time Alarm Management").classes('text-2xl font-bold text-slate-800')
            ui.button('🔄 Sync ทั้งหมด', on_click=lambda: [sync_dynatrace_to_db(), load_alarm_data(), render_alarm_lists.refresh()]).props('type=primary icon=refresh')

        @ui.refreshable
        def render_alarm_lists():
            with ui.tabs().classes('w-full') as tabs:
                t_active = ui.tab(f"🔴 Active ({len(state['active_items'])})")
                t_resolved = ui.tab(f"🟢 Resolved ({len(state['resolved_items'])})")

            with ui.tab_panels(tabs, value=t_active).classes('w-full mt-2'):
                with ui.tab_panel(t_active):
                    for item in state['active_items']:
                        render_alarm_card(item, is_active=True)
                with ui.tab_panel(t_resolved):
                    for item in state['resolved_items']:
                        render_alarm_card(item, is_active=False)

        render_alarm_lists()
        load_alarm_data()

def render_alarm_card(item, is_active: bool):
    db_id, prob_id, internal_id = item["id"], item["problem_id"], item.get("internal_id")
    status_icon = "🔴" if is_active else "🟢"
    ack_str = f"[ACK: {item['ack']}] " if item.get('ack') else ""
    inc_str = f"[INC: {item['incident']}] " if item.get('incident') else ""
    
    title_text = f"{status_icon} [{item.get('type', 'Dynatrace')}] {ack_prefix(item)}[{prob_id}] {item['problem_name']} | Service: {item['services']}"

    with ui.expansion().classes('w-full bg-white border rounded mb-2') as exp:
        with exp.add_slot('header'):
            lbl = ui.label(title_text).classes('font-bold text-sm py-2 cursor-pointer w-full')
            with ui.menu().bind_context_to(lbl): # Native Right-Click
                ui.menu_item('🧹 Clear Status (RESOLVED)', on_click=lambda: update_alarm(db_id, {"status": "RESOLVED"}))
                ui.menu_item('✅ ACK Alert', on_click=lambda: update_alarm(db_id, {"ack": "ACKED"}))

        with ui.column().classes('p-4 bg-gray-50 gap-2 w-full'):
            ui.label(f"Impact: {item.get('impact', '-')}")
            ui.code(item.get('remark') or '-').classes('w-full bg-slate-800 text-green-400 p-2 rounded')

def ack_prefix(item):
    ack = f"[ACK: {item['ack']}] " if item.get('ack') else ""
    inc = f"[INC: {item['incident']}] " if item.get('incident') else ""
    return f"{ack}{inc}"

def update_alarm(db_id, payload):
    supabase.table("alarm_comments").update(payload).eq("id", db_id).execute()
    ui.notify("✅ อัปเดตข้อมูลสำเร็จ!", color="positive")
    load_alarm_data()

# ==========================================
# 📌 PAGE 2: TEXT CLEANER
# ==========================================
@ui.page('/cleaner')
def cleaner_page():
    render_header()
    
    with ui.column().classes('w-full p-6 max-w-5xl mx-auto gap-4'):
        ui.label("🧹 Text Cleaner Tool").classes('text-2xl font-bold text-slate-800')
        ui.label("เครื่องมือทำความสะอาดข้อความ ตัดช่องว่าง แปลงตัวพิมพ์ และจัด Format สำหรับงาน Ops").classes('text-sm text-gray-500')

        input_text = ui.textarea(label="ข้อความต้นทาง (Input Text)", placeholder="วางข้อความที่ต้องการ Clean ที่นี่...").classes('w-full').props('outlined rows=6')
        output_text = ui.textarea(label="ผลลัพธ์ (Cleaned Output)").classes('w-full bg-gray-50').props('outlined rows=6 readonly')

        # Functions Clean ข้อความ
        def clean_spaces():
            val = input_text.value or ""
            # ลบช่องว่างซ้ำ และ Trim
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

        # Action Buttons
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

    def load_handover_tasks():
        try:
            state['handover_tasks'] = supabase.table("handover_tasks").select("*").order("id", desc=True).execute().data
        except Exception:
            state['handover_tasks'] = []

    def add_task(title, detail, assignee, shift):
        if not title:
            ui.notify("⚠️ กรุณากรอกหัวข้องาน", color="warning")
            return
        payload = {
            "title": title, "detail": detail, "assignee": assignee,
            "shift": shift, "status": "PENDING",
            "created_at": datetime.now(TZ_TH).strftime('%Y-%m-%d %H:%M')
        }
        try:
            supabase.table("handover_tasks").insert(payload).execute()
            ui.notify("📌 บันทึกงานฝากเรียบร้อย!", color="positive")
            render_handover_list.refresh()
        except Exception as e:
            ui.notify(f"❌ Error: {str(e)}", color="negative")

    def update_task_status(task_id, new_status):
        supabase.table("handover_tasks").update({"status": new_status}).eq("id", task_id).execute()
        ui.notify(f"อัปเดตสถานะเป็น {new_status}", color="info")
        render_handover_list.refresh()

    def delete_task(task_id):
        supabase.table("handover_tasks").delete().eq("id", task_id).execute()
        ui.notify("🗑️ ลบงานฝากเรียบร้อย", color="negative")
        render_handover_list.refresh()

    with ui.column().classes('w-full p-6 max-w-6xl mx-auto gap-4'):
        with ui.row().classes('w-full justify-between items-center'):
            ui.label("📦 กล่องงานฝาก (Shift Handover Tasks)").classes('text-2xl font-bold text-slate-800')
            
            # Form ฝากงานใหม่
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

        # List แสดงรายการงานฝาก
        @ui.refreshable
        def render_handover_list():
            load_handover_tasks()
            if not state['handover_tasks']:
                ui.label("💡 ไม่มีงานฝากในระบบ").classes('text-gray-500 italic mt-4')
                return

            with ui.grid(columns=3).classes('w-full gap-4 mt-2'):
                for task in state['handover_tasks']:
                    t_id = task["id"]
                    status = task.get("status", "PENDING")
                    
                    status_color = "warning" if status == "PENDING" else ("info" if status == "IN_PROGRESS" else "positive")
                    
                    with ui.card().classes('w-full bg-white border shadow-sm p-4 relative'):
                        with ui.row().classes('justify-between items-center w-full'):
                            lbl_title = ui.label(task["title"]).classes('font-bold text-base cursor-pointer text-slate-800')
                            ui.badge(status, color=status_color)
                            
                            # 🎯 NATIVE RIGHT-CLICK CONTEXT MENU สำหรับงานฝาก
                            with ui.menu().bind_context_to(lbl_title):
                                ui.menu_item('🟡 กำลังรอ (Pending)', on_click=lambda id=t_id: update_task_status(id, "PENDING"))
                                ui.menu_item('🔵 กำลังทำ (In Progress)', on_click=lambda id=t_id: update_task_status(id, "IN_PROGRESS"))
                                ui.menu_item('🟢 เสร็จแล้ว (Done)', on_click=lambda id=t_id: update_task_status(id, "DONE"))
                                ui.separator()
                                ui.menu_item('🗑️ ลบงานนี้', on_click=lambda id=t_id: delete_task(id))

                        ui.label(task.get("detail") or "-").classes('text-sm text-gray-600 my-2')
                        
                        with ui.row().classes('w-full justify-between items-center text-xs text-gray-400 mt-2 border-t pt-2'):
                            ui.label(f"👤 {task.get('assignee') or 'ไม่ระบุ'} ({task.get('shift') or '-'})")
                            ui.label(f"🕒 {task.get('created_at') or '-'}")

        render_handover_list()

# --- AUTO BACKGROUND SYNC ---
app.on_startup(lambda: asyncio.create_task(auto_sync_loop()))

async def auto_sync_loop():
    while True:
        await asyncio.sleep(30)
        sync_dynatrace_to_db()
        load_alarm_data()

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="IT Operations Management Tool", port=8501, reload=False)
