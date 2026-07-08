import streamlit as st
from datetime import datetime

# 1. ตั้งค่าหน้าจอหลัก
st.set_page_config(
    page_title="My Workspace Hub",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="collapsed" # ยุบแถบข้างไว้ก่อนเพื่อให้ตรงกลางเด่นเหมือน Gemini
)

# --- ส่วนที่ 2: ส่วนหัวของหน้าจอ (Header Zone - บนซ้าย และ บนขวา) ---
header_col1, header_col2 = st.columns([1, 1])

with header_col1:
    # บนซ้าย: กล่องงานฝาก (Placeholder รอทำแอปในอนาคต)
    st.info("📦 **กล่องงานฝาก (Todo App)**\n\n*(พื้นที่สำหรับพัฒนาระบบฝากงานในอนาคต)*")

with header_col2:
    # บนขวา: แสดงวันที่และเวลาปัจจุบันแบบ Real-time (อัปเดตเมื่อรีเฟรชหน้า)
    current_time = datetime.now().strftime("%Aที่ %d %B %Y | เวลา %H:%M น.")
    st.markdown(
        f"<div style='text-align: right; color: #666; font-size: 14px; padding-top: 10px;'>"
        f"📅 {current_time}"
        f"</div>", 
        unsafe_allow_allowed=True, unsafe_allow_html=True
    )

st.markdown("---")

# --- ส่วนที่ 3: โครงสร้างข้อมูลแอปทั้งหมดในระบบ (สำหรับใช้ค้นหาและเชื่อมโยง) ---
# อนาคตสร้างแอปใหม่ ให้มาเพิ่มชื่อแอป (title) และตัวเรียกฟังก์ชัน (key) ตรงนี้ได้เลยครับ
apps_directory = [
    {
        "title": "🧹 เครื่องมือจัดการข้อความ (Text Cleaner)",
        "key": "text_cleaner",
        "description": "ลบเครื่องหมาย ~, \", อักขระต่างดาว และจัดระเบียบบรรทัดว่างอัตโนมัติ"
    },
    {
        "title": "🗂️ ระบบจัดการข้อมูลหลังบ้าน (Supabase Database)",
        "key": "supabase_db",
        "description": "ระบบเพิ่ม แก้ไข ลบข้อมูลหลังบ้าน และดาวน์โหลดไฟล์ออกมาเป็น CSV"
    }
]

# --- ส่วนที่ 4: ตรงกลางหน้าจอ สไตล์ Gemini Search ---
# ตรวจสอบว่ายูสเซอร์เคยคลิกเลือกแอปไปหรือยัง ถ้ายังไม่เลือกจะแสดงหน้าค้นหาก่อน
if "selected_app" not in st.session_state:
    st.session_state.selected_app = None

# ถ้ายังไม่มีการเลือกแอป -> แสดงหน้าโฮมสไตล์ Gemini
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
        placeholder="พิมพ์คำค้นหา เช่น ข้อความ, คลีน, database, จัดเก็บ...",
        label_visibility="collapsed"
    )
    
    # ค้นหาคำที่ใกล้เคียงกับคำใน st.title
    matched_apps = []
    for app in apps_directory:
        # ถ้าไม่ได้พิมพ์อะไรเลย ให้โชว์แอปทั้งหมด หรือถ้าพิมพ์ ให้เช็คคำที่ใกล้เคียง (ไม่สนพิมพ์เล็ก-ใหญ่)
        if not search_query or search_query.lower() in app["title"].lower() or search_query.lower() in app["description"].lower():
            matched_apps.append(app)
            
    # แสดงผลการค้นหาเป็นกล่องการ์ดสวยๆ ใต้ช่องค้นหา
    st.markdown("<br>", unsafe_allow_html=True)
    if matched_apps:
        # แสดงผลแบบ Grid ลิสต์รายการลงมา
        for app in matched_apps:
            with st.container():
                st.markdown(
                    f"<div style='border: 1px solid #e0e0e0; border-radius: 10px; padding: 15px; margin-bottom: 10px; background-color: #fafafa;'>"
                    f"<h4>{app['title']}</h4>"
                    f"<p style='color: #666; font-size: 14px;'>{app['description']}</p>"
                    f"</div>", 
                    unsafe_allow_html=True
                )
                # ปุ่มสำหรับกดเข้าแอปนั้นๆ
                if st.button(f"เปิดใช้งาน {app['title']}", key=f"btn_{app['key']}"):
                    st.session_state.selected_app = app["key"]
                    st.rerun()
    else:
        st.warning("😔 ไม่พบเครื่องมือที่ตรงกับคำค้นหาของคุณ ลองเปลี่ยนคีย์เวิร์ดดูนะคร้าบ")

# --- ส่วนที่ 5: หน้าตาเมื่อเปิดแอปพลิเคชันขึ้นมาทำงาน ---
else:
    # ปุ่มย้อนกลับไปหน้าค้นหาหลัก (เสมือนกดโลโก้เพื่อกลับหน้าแรก)
    if st.button("⬅️ กลับไปหน้าหลัก (ค้นหาเครื่องมือ)"):
        st.session_state.selected_app = None
        st.rerun()
        
    st.markdown("---")
    
    # เรียกใช้แอปพลิเคชันตามคีย์ที่เลือก
    if st.session_state.selected_app == "text_cleaner":
        try:
            import text_cleaner
            text_cleaner.run_app()
        except ModuleNotFoundError:
            st.error("❌ ไม่พบไฟล์ `text_cleaner.py` ในระบบ")
            
    elif st.session_state.selected_app == "supabase_db":
        st.title("🗂️ ระบบจัดการข้อมูลหลังบ้าน (Supabase)")
        st.warning("🚧 แอปพลิเคชันนี้กำลังเปิดระบบหลังบ้าน (อยู่ในช่วงพักสถานะชั่วคราว)")
