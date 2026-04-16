import streamlit as st
import requests
import html

BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Enterprise AI Assistant", layout="wide")

# ---------------- STYLING ----------------
st.markdown("""
<style>

/* Chat container */
.chat-container {
    height: 70vh;
    overflow-y: auto;
    padding-bottom: 80px;
}

/* Bottom input bar */
.bottom-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: #0e1117;
    padding: 10px;
    border-top: 1px solid #333;
    z-index: 100;
}

/* Tool button */
.tool-btn {
    padding: 6px 12px;
    border-radius: 8px;
    background: #1f2937;
    color: white;
    cursor: pointer;
    border: 1px solid #444;
}

/* Source tags */
.source-tags {
    margin-top: 0.5rem;
    display: flex;
    gap: 0.5rem;
}
.source-tag {
    padding: 4px 10px;
    border-radius: 999px;
    background: rgba(255,185,0,0.2);
    border: 1px solid rgba(255,185,0,0.6);
    color: #f8cc6a;
    font-size: 0.8rem;
}

</style>
""", unsafe_allow_html=True)

# ---------------- HELPERS ----------------
def _source_key(message):
    return f"{message.get('question')}|||{message.get('answer')}"

def _render_sources(sources):
    if not sources:
        return

    chips = ""
    for s in sources[:2]:
        chips += f"<span class='source-tag'>{html.escape(s.get('file_name',''))}</span>"

    st.markdown(f"<div class='source-tags'>{chips}</div>", unsafe_allow_html=True)

# ---------------- SESSION ----------------
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "role" not in st.session_state:
    st.session_state.role = None
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "tool" not in st.session_state:
    st.session_state.tool = "auto"
if "message_sources" not in st.session_state:
    st.session_state.message_sources = {}

# ---------------- SIDEBAR ----------------
st.sidebar.title("🏢 Enterprise AI Assistant")

if st.session_state.user_id:
    st.sidebar.success(f"Logged in as {st.session_state.role}")

    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()
else:
    menu = st.sidebar.radio("Navigation", ["Login", "Register"])

# ---------------- REGISTER ----------------
if not st.session_state.user_id and menu == "Register":
    st.title("Register")

    username = st.text_input("Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    role = st.selectbox("Role", ["HR", "Employee"])

    if st.button("Register"):
        requests.post(f"{BASE_URL}/register", json={
            "username": username,
            "email": email,
            "password": password,
            "role": role
        })
        st.success("Registered!")

# ---------------- LOGIN ----------------
elif not st.session_state.user_id and menu == "Login":
    st.title("Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        res = requests.post(f"{BASE_URL}/login", json={
            "username": username,
            "password": password
        })
        data = res.json()

        if "error" not in data:
            st.session_state.user_id = data["user_id"]
            st.session_state.role = data["role"]
            st.rerun()
        else:
            st.error(data["error"])

# ---------------- MAIN APP ----------------
elif st.session_state.user_id:

    st.title("🤖 Enterprise Assistant")

    # Conversations
    if st.sidebar.button("➕ New Chat"):
        res = requests.post(f"{BASE_URL}/chat/start",
            params={"user_id": st.session_state.user_id})
        st.session_state.conversation_id = res.json()["conversation_id"]
        st.rerun()

    res = requests.get(f"{BASE_URL}/chat/user/{st.session_state.user_id}")
    convs = res.json() if res.status_code == 200 else []

    for c in convs:
        if st.sidebar.button(c["title"], key=c["conversation_id"]):
            st.session_state.conversation_id = c["conversation_id"]
            st.rerun()

    # Chat area
    st.markdown("<div class='chat-container'>", unsafe_allow_html=True)

    if st.session_state.conversation_id:
        res = requests.get(f"{BASE_URL}/chat/history/{st.session_state.conversation_id}")
        messages = res.json()

        for msg in messages:
            with st.chat_message("user"):
                st.write(msg["question"])

            with st.chat_message("assistant"):
                st.write(msg["answer"])
                _render_sources(st.session_state.message_sources.get(_source_key(msg), []))

    st.markdown("</div>", unsafe_allow_html=True)

    # ---------------- TOOL + INPUT ----------------
    col1, col2 = st.columns([1, 6])

    with col1:
        tool = st.selectbox(
            "",
            ["auto", "rag", "llm", "summary", "compare", "agent"],
            key="tool"
        )

    with col2:
        user_input = st.chat_input(f"Ask something... ({tool})")

    if user_input:

        tool = st.session_state.tool

        if tool in ["auto", "rag"]:
            res = requests.post(f"{BASE_URL}/ask", json={
                "user_id": st.session_state.user_id,
                "question": user_input,
                "conversation_id": st.session_state.conversation_id
            })
        else:
            res = requests.post(f"{BASE_URL}/chat/message", params={
                "conversation_id": st.session_state.conversation_id,
                "question": user_input,
                "role": st.session_state.role,
                "tool": tool
            })

        data = res.json()

        sources = data.get("sources", [])
        key = _source_key({"question": user_input, "answer": data.get("answer")})
        st.session_state.message_sources[key] = sources

        st.rerun()

