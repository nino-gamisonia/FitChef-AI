import os
os.environ["GEMINI_API_KEY"] = ""
import uuid
import requests
import streamlit as st
from langgraph.types import Command
from agent import build_agent
from vision import scan_fridge_and_make_recipe
from tools import DAILY_PLAN

st.set_page_config(page_title="FitChef AI", page_icon="🥗", layout="wide")

st.markdown("""<style>
.stExpander { border: 1px solid #334155 !important; border-radius: 12px !important; background-color: #162032 !important; margin-bottom: 10px !important; }
.plan-card { padding: 10px 14px; border-radius: 10px; background-color: rgba(16, 185, 129, 0.12); border-left: 4px solid #10B981; margin-bottom: 8px; font-size: 0.92rem; }
.weather-box { padding: 12px; border-radius: 10px; background-color: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); margin-top: 6px; }
</style>""", unsafe_allow_html=True)

@st.cache_data(ttl=600)
def fetch_sidebar_weather(city_name: str):
    try:
        geo = requests.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": city_name, "count": 1, "language": "en", "format": "json"}, timeout=10).json()
        results = geo.get("results")
        if not results: return None
        lat, lon, resolved = results[0]["latitude"], results[0]["longitude"], results[0]["name"]
        w = requests.get("https://api.open-meteo.com/v1/forecast", params={"latitude": lat, "longitude": lon, "current": "temperature_2m,precipitation"}, timeout=10).json()["current"]
        return {"city": resolved, "temp": w["temperature_2m"], "precip": w["precipitation"]}
    except Exception:
        return None

if not os.environ.get("GROQ_API_KEY"):
    api_key_input = st.sidebar.text_input("Groq API Key (gsk_...)", type="password")
    if api_key_input:
        os.environ["GROQ_API_KEY"] = api_key_input
    else:
        st.warning("გთხოვთ შეიყვანოთ GROQ_API_KEY გვერდითა პანელში.")
        st.stop()

if "agent" not in st.session_state or st.session_state.agent is None: st.session_state.agent = build_agent()
if "thread_id" not in st.session_state: st.session_state.thread_id = str(uuid.uuid4())
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "pending_interrupt" not in st.session_state: st.session_state.pending_interrupt = None
if "ui_lang" not in st.session_state: st.session_state.ui_lang = "ქართული"


def auto_sync_daily_plan(reply_text: str):
    if not reply_text:
        return
    # ვამოწმებთ შეიცავს თუ არა პასუხი ცხრილს (ვარჯიშის ან კვების გეგმას)
    for line in reply_text.splitlines():
        line_s = line.strip()
        if line_s.startswith("|") and line_s.endswith("|") and "---" not in line_s:
            cells = [c.strip().replace("**", "") for c in line_s.strip("|").split("|")]
            if len(cells) >= 2:
                col0, col1 = cells[0], cells[1]
                skip_headers = ["დრო", "კვება", "კვების დრო", "სავარჯიშო", "მოქმედება", "Time", "Meal", "Exercise"]
                if col0 not in skip_headers and col1 not in skip_headers and len(col1) > 2:
                    entry = f"• {col0}: {col1}"
                    if entry not in DAILY_PLAN and len(DAILY_PLAN) < 15:
                        DAILY_PLAN.append(entry)

config = {"configurable": {"thread_id": st.session_state.thread_id}}
is_en = st.session_state.ui_lang == "English"

with st.sidebar:
    sub_txt = "Personal Fitness & Nutrition Coach" if is_en else "პერსონალური ფიტნეს მწვრთნელი და ნუტრიციოლოგი"
    st.markdown(f"""<div style="padding: 4px 0 8px 0;"><div style="font-size: 1.5rem; font-weight: 700; letter-spacing: -0.4px;">🥗 FitChef AI</div><div style="font-size: 0.8rem; color: #94A3B8; margin-top: 2px;">{sub_txt}</div></div>""", unsafe_allow_html=True)

    with st.expander("🌤️ Current Weather" if is_en else "🌤️ მიმდინარე ამინდი", expanded=True):
        city = st.text_input("City (in English)" if is_en else "ქალაქი (ინგლისურად)", value="Tbilisi")
        w_info = fetch_sidebar_weather(city)
        if w_info:
            t, p = w_info["temp"], w_info["precip"]
            adv = ("☀️ Great for outdoor workout" if p == 0 and t >= 8 else "🏠 Better to train indoors") if is_en else ("☀️ მშვენიერია გარეთ ვარჯიშისთვის" if p == 0 and t >= 8 else "🏠 სჯობს სახლში ვარჯიში")
            p_lbl = f"Precipitation: {p} mm" if is_en else f"ნალექი: {p} მმ"
            st.markdown(f"""<div class="weather-box"><div style="font-size: 1.05rem; font-weight: 600;">📍 {w_info["city"]}: {t}°C</div><div style="font-size: 0.82rem; color: #94A3B8; margin-top: 2px;">{p_lbl}</div><div style="font-size: 0.82rem; color: #10B981; margin-top: 6px;">{adv}</div></div>""", unsafe_allow_html=True)
        else:
            st.caption("City not found." if is_en else "ქალაქი ვერ მოიძებნა.")

    cur_w = st.session_state.get("user_weight", 76)
    with st.expander("🎯 Goal & Timeline" if is_en else "🎯 მიზანი და ვადები", expanded=True):
        target_weight = st.number_input("Target Weight (kg)" if is_en else "სასურველი წონა (კგ)", min_value=35, max_value=200, value=max(35, int(cur_w) - 5))
        diff = target_weight - int(cur_w)
        if diff != 0:
            sign = "+" if diff > 0 else ""
            st.caption(f"🎯 {'Target change' if is_en else 'სამიზნე ცვლილება'}: **{sign}{diff} {'kg' if is_en else 'კგ'}**")
        goal = st.selectbox("Goal" if is_en else "მიზანი", ["წონის კლება (Weight loss)", "კუნთის მატება (Muscle gain)", "ფორმის შენარჩუნება (Fitness)"])
        timeframe = st.selectbox("Timeline" if is_en else "მიზნის მიღწევის ვადა", ["1 თვე", "2 თვე", "3 თვე", "6 თვე", "1 წელი"], index=2)
        time_avail = st.slider("Available Time (min/day)" if is_en else "თავისუფალი დრო (წუთი/დღე)", 10, 120, 45, step=5)
        if time_avail <= 20:
            s_col, t_hint = "#EF4444", ("🔴 Quick warm-up only" if is_en else "🔴 ცოტა დროა — მხოლოდ სწრაფი გახურება გამოვა")
        elif time_avail <= 40:
            s_col, t_hint = "#F59E0B", ("🟡 Good duration" if is_en else "🟡 ნორმალურია — ოპტიმალურ დროს უახლოვდები")
        elif time_avail <= 90:
            s_col, t_hint = "#10B981", ("🟢 Ideal workout duration!" if is_en else "🟢 იდეალური დროა სრულფასოვანი ვარჯიშისთვის!")
        else:
            s_col, t_hint = "#3B82F6", ("🔵 Intensive mode" if is_en else "🔵 ინტენსიური / ხანგრძლივი დატვირთვის რეჟიმი")
        st.markdown(f"""<style>section[data-testid="stSidebar"] div[data-testid="stSlider"] div[role="slider"] {{ background-color: {s_col} !important; border-color: {s_col} !important; }} section[data-testid="stSidebar"] div[data-testid="stSlider"] div[data-testid="stSliderThumbValue"] {{ color: {s_col} !important; font-weight: 700 !important; }} section[data-testid="stSidebar"] div[data-testid="stSlider"] div[data-baseweb="slider"] > div > div:nth-child(2) {{ background-color: {s_col} !important; }}</style><div style="font-size: 0.8rem; color: {s_col}; margin-top: -6px; margin-bottom: 4px;">{t_hint}</div>""", unsafe_allow_html=True)

    with st.expander("📸 Fridge Scanner" if is_en else "📸 მაცივრის სკანირება", expanded=False):
        fridge_file = st.file_uploader("Upload food photo" if is_en else "ატვირთე პროდუქტების ფოტო", type=["jpg", "jpeg", "png", "webp"], key="fridge_cam")
        if fridge_file is not None:
            st.image(fridge_file, use_container_width=True)
            if st.button("🔍 Scan & Make Recipe" if is_en else "🔍 ამოცნობა და რეცეპტი", use_container_width=True):
                with st.spinner("Scanning..." if is_en else "ვასკანირებ პროდუქტებს..."):
                    res = scan_fridge_and_make_recipe(fridge_file.getvalue(), "")
                    if res["ok"]:
                        u_msg = "[Fridge photo uploaded]" if is_en else "[მაცივრის ფოტო აიტვირთა]"
                        st.session_state.chat_history.append(("user", u_msg))
                        st.session_state.chat_history.append(("assistant", res["text"]))
                        st.session_state["fridge_context"] = res["text"]; auto_sync_daily_plan(res["text"])
                        st.rerun()
                    else:
                        st.error(res["text"])

    with st.expander(f"📋 Today's Plan ({len(DAILY_PLAN)})" if is_en else f"📋 დღევანდელი გეგმა ({len(DAILY_PLAN)})", expanded=False):
        if DAILY_PLAN:
            for item in DAILY_PLAN: st.markdown(f'<div class="plan-card">{item}</div>', unsafe_allow_html=True)
            if st.button("🧹 Clear Plan" if is_en else "🧹 გეგმის გასუფთავება", use_container_width=True):
                DAILY_PLAN.clear()
                st.rerun()
        else:
            st.caption("Plan is empty." if is_en else "გეგმა ჯერ ცარიელია.")

    if st.button("🗑️ New Chat" if is_en else "🗑️ ახალი საუბრის დაწყება", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.pending_interrupt = None
        st.rerun()

    st.divider()

    with st.expander("⚙️ Settings & Profile" if is_en else "⚙️ პარამეტრები და პროფილი", expanded=False):
        sel_lang = st.radio("🌐 ენა / Language", ["ქართული", "English"], index=0 if st.session_state.ui_lang == "ქართული" else 1, horizontal=True)
        if sel_lang != st.session_state.ui_lang:
            st.session_state.ui_lang = sel_lang
            st.rerun()
        st.markdown("---")
        st.markdown(f"**{'👤 Personal Info' if is_en else '👤 პერსონალური ინფორმაცია'}**")
        c_a, c_b = st.columns(2)
        with c_a:
            age = st.number_input("Age" if is_en else "ასაკი", min_value=14, max_value=90, value=23)
            weight = st.number_input("Weight (kg)" if is_en else "წონა (კგ)", min_value=35, max_value=200, value=76, key="user_weight")
        with c_b:
            height = st.number_input("Height (cm)" if is_en else "სიმაღლე (სმ)", min_value=120, max_value=220, value=172)
        limitations = st.text_area("🩺 Health / Limitations" if is_en else "🩺 შეზღუდვები / ჯანმრთელობა", value="None" if is_en else "არანაირი", height=68)
        st.markdown("---")
        st.markdown(f"**{'ℹ️ About FitChef AI' if is_en else 'ℹ️ ჩვენს შესახებ'}**")
        about_txt = "FitChef AI is an intelligent fitness & nutrition assistant powered by LangGraph and Gemini Vision." if is_en else "FitChef AI არის პერსონალური ფიტნეს და კვების ასისტენტი, რომელიც აერთიანებს ამინდის ანალიზს, სავარჯიშო გეგმებს, კალორიების კონტროლსა და მაცივრის სკანერს."
        st.caption(about_txt)

lang_rule = "Respond strictly in English." if is_en else "უპასუხე მხოლოდ გამართული, ბუნებრივი ქართული ენით."
user_profile = f"City: {city}. Age: {age}, Height: {height} cm, Weight: {weight} kg, Target: {target_weight} kg. Goal: {goal} within {timeframe}. Time: {time_avail} mins/day. Limitations: {limitations}. {lang_rule}"

selected_quick_prompt = None
if not st.session_state.chat_history:
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🌤️ Weather Workout" if is_en else "🌤️ ამინდის მიხედვით ვარჯიში", use_container_width=True):
            selected_quick_prompt = f"Check the weather in {city} and suggest a workout." if is_en else f"შეამოწმე {city}-ის ამინდი და ჩემი პროფილის მიხედვით შემირჩიე ვარჯიშები."
    with c2:
        if st.button("🥗 Healthy Recipe" if is_en else "🥗 ჯანსაღი რეცეპტი", use_container_width=True):
            selected_quick_prompt = "Suggest a healthy recipe aligned with my goal." if is_en else "მომიძებნე ჯანსაღი რეცეპტი ჩემი პროფილისა და მიზნის მიხედვით."
    with c3:
        if st.button("📋 Show Daily Plan" if is_en else "📋 მაჩვენე ჩემი დღის გეგმა", use_container_width=True):
            selected_quick_prompt = "Show my daily plan." if is_en else "მაჩვენე რა მაქვს ამჟამად დღევანდელ გეგმაში."

for role, text in st.session_state.chat_history:
    with st.chat_message(role): st.markdown(text)

if st.session_state.pending_interrupt:
    st.warning(f"⚠️ **{'Confirmation required' if is_en else 'დადასტურება საჭიროა'}:** {st.session_state.pending_interrupt}")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Yes, delete" if is_en else "✅ დიახ, წაშალე", use_container_width=True):
            res = st.session_state.agent.invoke(Command(resume=True), config)
            st.session_state.chat_history.append(("assistant", res["messages"][-1].content))
            st.session_state.pending_interrupt = None
            st.rerun()
    with col2:
        if st.button("❌ No, keep" if is_en else "❌ არა, დატოვე", use_container_width=True):
            res = st.session_state.agent.invoke(Command(resume=False), config)
            st.session_state.chat_history.append(("assistant", res["messages"][-1].content))
            st.session_state.pending_interrupt = None
            st.rerun()

chat_input_val = st.chat_input("Ask about workouts, nutrition, or weather..." if is_en else "მკითხე ვარჯიშზე, კვებაზე ან ამინდზე...")
prompt = selected_quick_prompt or chat_input_val

if prompt:
    st.session_state.chat_history.append(("user", prompt))
    with st.chat_message("user"): st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..." if is_en else "FitChef AI ფიქრობს..."):
            if st.session_state.get("agent") is None: st.session_state.agent = build_agent()
            f_ctx = st.session_state.get("fridge_context")
            full_prompt = f"[Fridge items: {f_ctx}]\n\n{prompt}" if f_ctx else prompt
            result = st.session_state.agent.invoke({"messages": [("user", full_prompt)], "user_profile": user_profile}, config)
            state = st.session_state.agent.get_state(config)
            if state.tasks and state.tasks[0].interrupts:
                st.session_state.pending_interrupt = state.tasks[0].interrupts[0].value
                st.rerun()
            else:
                reply = result["messages"][-1].content
                st.markdown(reply)
                st.session_state.chat_history.append(("assistant", reply)); auto_sync_daily_plan(reply)
                st.rerun()
