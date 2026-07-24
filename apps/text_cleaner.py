import streamlit as st
import re

def run_app():
    st.title("🧹 ร่าง Incident")
    st.write("ระบบจะลบเครื่องหมาย ~, \", อักขระต่างดาว และคัดกรองบรรทัดว่างอย่างแม่นยำ")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📥 ข้อมูลเข้า")
        input_text = st.text_area(
            "วางข้อความดิบที่นี่:", 
            height=280, 
            placeholder="วางข้อความลงไปได้เลย..."
        )

    with col2:
        st.subheader("📤 ผลลัพธ์")
        
        cleaned_text = input_text
        
        if input_text:
            # เงื่อนไขที่ 1-3: ลบอักขระที่ไม่ต้องการออกก่อน
            cleaned_text = cleaned_text.replace('~', '')
            cleaned_text = cleaned_text.replace('"', '')
            cleaned_text = re.sub(r'[\uE000-\uF8FF]', '', cleaned_text)
            
            # --- เริ่มขั้นตอนการคัดกรองบรรทัดว่างแบบมีเงื่อนไขตามสั่ง ---
            raw_lines = cleaned_text.split('\n')
            final_lines = []
            
            for i in range(len(raw_lines)):
                current_line = raw_lines[i].strip()
                
                # เช็คว่าบรรทัดปัจจุบันเป็นบรรทัดว่างหรือไม่
                if current_line == "":
                    # ตรวจสอบบรรทัดถัดไป (ถ้ามีบรรทัดถัดไปจริง)
                    if i + 1 < len(raw_lines):
                        next_line = raw_lines[i+1].strip().lower()
                        # กฎเหล็ก: ถ้าบรรทัดถัดไปขึ้นต้นด้วยคำว่า 'open' ให้เก็บความว่างนี้ไว้ ห้ามลบ!
                        if next_line.startswith("open"):
                            final_lines.append("")
                            continue
                    
                    # ถ้าบรรทัดถัดไปไม่ใช่ 'open' หรือเป็นบรรทัดว่างติดๆ กันเกินไป -> ให้ข้าม (ลบทิ้ง)
                    continue
                
                # ถ้าเป็นบรรทัดที่มีข้อความปกติ ให้ใส่ลงไปตามปกติ
                final_lines = [line for line in final_lines if line != "" or (final_lines and final_lines[-1] != "")] # กันไม่ให้มีช่องว่างซ้ำซ้อน
                final_lines.append(current_line)
            
            # เคลียร์ซับซ้อนรอบสุดท้าย: ปรับโครงสร้างข้อความ
            # นำมาประกอบกลับคืน
            cleaned_text = '\n'.join(final_lines)
            
            # ดักเคสพิเศษ: ถ้ามันติดกันอยู่แล้ว แต่ไม่มีบรรทัดว่าง แล้วเจอคำว่า open ให้แทรกเพิ่มให้ด้วย
            # (กันไว้ดีกว่าแก้ เผื่อต้นทางไม่ได้เว้นวรรคมา ระบบจะเว้นให้เองเลยครับ)
            lines_check = cleaned_text.split('\n')
            final_perfect = []
            for idx, line in enumerate(lines_check):
                if line.strip().lower().startswith("open") and idx > 0 and final_perfect[-1] != "":
                    final_perfect.append("")
                final_perfect.append(line)
                
            cleaned_text = '\n'.join(final_perfect)

        st.text_area("ข้อความที่ทำความสะอาดแล้ว:", value=cleaned_text, height=280)
        
        if input_text:
            st.success("✨ จัดรูปแบบบรรทัดว่างสำหรับกลุ่มคำ OPEN เรียบร้อยแล้ว!")
