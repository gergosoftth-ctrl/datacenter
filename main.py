import streamlit as st
from datetime import datetime

# 1. ตั้งค่าหน้าจอหลัก (เปิด sidebar ไว้ตามปกติเพื่อให้ชิดซ้ายและยืดเข้าออกได้)
st.set_page_config(
    page_title="My Workspace Hub",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded" # เปิดไว้เพื่อให้เห็นเมนูชิดซ้าย สามารถกดพับเก็บเองได้ที่มุมบนซ้าย
)

# --- ส่วนที่ 2: ส่วนหัวของหน้าจอ (Header Zone - บนซ้าย และ บนขวา) ---
header_col1, header_col2 = st.columns([1, 1])

with header_col1:
    # บนซ้าย: กล่องงานฝาก
    st.info("📦 **กล่องงานฝาก (Todo App)**\n\n*(พื้นที่สำหรับพัฒนาระบบฝากงานในอนาคต)*")

with header_col2:
    # บนขวา: แสดงวันที่และเวลาปัจจุบัน
    current_time = datetime.now().strftime("%Aที่ %d %B %Y | เวลา %H:%M น.")
    st.markdown(
        f"<div style='text-align: right; color: #666; font-size: 14px; padding-top: 10px;'>"
        f"📅 {current_time}"
        f"</div>", 
        unsafe_allow_html=True
    )

st.markdown("---")

# --- ส่วนที่ 3: โครงสร้างข้อมูลแอปทั้งหมดในระบบ ---
# ผมเปลี่ยนชื่อแอปแรกตามตัวอย่างของคุณ เพื่อให้ทดสอบพิมพ์ค้นหาคำว่า "ร่าง", "incident" ได้เลยครับ
apps_directory = [
    {
        "title": "🧹 ร่างข้อความ Incident (Text Cleaner)",
        "key": "text_cleaner",
        "description": "ลบเครื่องหมาย ~, \", อักขระต่างดาว และจัดระเบียบบรรทัดว่างสำหรับข้อความ Incident"
    },
    {
        "title": "🗂️ ระบบจัดการข้อมูลหลังบ้าน (Supabase Database)",
        "key": "supabase_db",
        "description": "ระบบเพิ่ม แก้ไข ลบข้อมูลหลังบ้าน และดาวน์โหลดไฟล์ออกมาเป็น CSV"
    }
]

# --- ส่วนที่ 4: แถบเมนูด้านข้าง (Sidebar) ชิดซ้าย ---
st.sidebar.title("🎮 เมนูทางเลือก")
st.sidebar.write("เลือกแอปพลิเคชันโดยตรง:")

# ตัวแปรควบคุมหน้าจอหลัก
if "selected_app" not in st.session_state:
    st.session_state.selected_app = None

# ปุ่มทางลัดใน Sidebar (กดปุ่มไหนจะสลับหน้าทันที)
if st.sidebar.button("🏠 กลับหน้าหลัก / ค้นหา", use_container_width=True):
    st.session_state.selected_app = None
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.write("**รายชื่อแอปทั้งหมด:**")

for app in apps_directory:
    if st.sidebar.button(app["title"], key=f"side_{app['key']}", use_container_width=True):
        st.session_state.selected_app = app["key"]
        st.rerun()


# --- ส่วนที่ 5: ตรงกลางหน้าจอ สไตล์ Gemini Search ---
if st.session_state.selected_app is None:
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # ข้อความทักทายตรงกลาง
    st.markdown(
        "<h1 style='text-align: center; font-size: 42px; background: linear-gradient(45deg, #4285F4, #9B51E0); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>สวัสดีครับ มีอะไรให้ช่วยจัดการวันนี้ไหม?</h1>", 
        unsafe_allow_html=True
    )
    st.markdown("<p style='text-align: center; color: #666;'>ค้นหาเครื่องมือหรือแอปพลิเคชันที่คุณต้องการใช้งานด้านล่าง</p>", unsafe_allow_html=True)
    
    # กล่อง Search ตรงกลางหน้าจอ
    search_query = st.text_input(
        "🔍 ค้นหาแอปพลิเคชัน...", 
        placeholder="พิมพ์คำค้นหา เช่น ร่าง, ข้อความ, incident, database...",
        label_visibility="collapsed"
    )
    
    # ระบบค้นหาอัจฉริยะ (จะทำงานต่อเมื่อยูสเซอร์พิมพ์ข้อความลงไปเท่านั้น)
    if search_query:
        st.markdown("<br>", unsafe_allow_html=True)
        matched_apps = []
        
        # ค้นหาแบบละเอียดยิ่งขึ้น (แปลงเป็นพิมพ์เล็ก และเช็คคำบางส่วน)
        query_clean = search_query.strip().lower()
        for app in apps_directory:
            if (query_clean in app["title"].lower()) or (query_clean in app["description"].lower()):
                matched_apps.append(app)
                
        # แสดงผลการค้นหาเฉพาะที่ตรงเงื่อนไข
        if matched_apps:
            st.markdown(f"<p style='color: #666;'>🔍 พบเครื่องมือที่ใกล้เคียงกับ '{search_query}':</p>", unsafe_allow_html=True)
            for app in matched_apps:
                with st.container():
                    st.markdown(
                        f"<div style='border: 1px solid #e0e0e0; border-radius: 10px; padding: 15px; margin-bottom: 10px; background-color: #fafafa;'>"
                        f"<h4>{app['title']}</h4>"
                        f"<p style='color: #666; font-size: 14px;'>{app['description']}</p>"
                        f"</div>", 
                        unsafe_allow_html=True
                    )
                    if st.button(f"เปิดใช้งาน {app['title']}", key=f"btn_{app['key']}"):
                        st.session_state.selected_app = app["key"]
                        st.rerun()
        else:
            st.warning(f"😔 ไม่พบเครื่องมือที่ตรงกับคำว่า '{search_query}' ลองเปลี่ยนคีย์เวิร์ดดูนะคร้าบ")


# --- ส่วนที่ 6: หน้าตาเมื่อเปิดแอปพลิเคชันขึ้นมาทำงาน ---
else:
    if st.button("⬅️ กลับไปหน้าหลัก (ค้นหาเครื่องมือ)"):
        st.session_state.selected_app = None
        st.rerun()
        
    st.markdown("---")
    
    # เรียกใช้แอปพลิเคชันตามคีย์ที่เลือก
    if st.session_state.selected_app == "text_cleaner":
    try:
        from apps import text_cleaner  # <-- เปลี่ยนเป็นดึงมาจากโฟลเดอร์ apps
        text_cleaner.run_app()
        except ModuleNotFoundError:
            st.error("❌ ไม่พบไฟล์ `text_cleaner.py` ในระบบ")
            
    elif st.session_state.selected_app == "supabase_db":
        st.title("🗂️ ระบบจัดการข้อมูลหลังบ้าน (Supabase)")
        st.warning("🚧 แอปพลิเคชันนี้กำลังเปิดระบบหลังบ้าน (อยู่ในช่วงพักสถานะชั่วคราว)")
