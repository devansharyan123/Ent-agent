import streamlit as st
import requests

BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Enterprise AI Assistant", layout="wide")

# --- styling (combined custom CSS)
st.markdown(
    """
    <style>
    .reportview-container .main .block-container{max-width:980px;padding-top:1rem;}
    .stChatMessage p{font-size:15px}
    #MainMenu {visibility: hidden;} footer {visibility: hidden}
    /* Make the expander content scrollable so input remains fixed below it */
    .stExpander .stExpanderContent { max-height: 62vh; overflow-y: auto; }

    .stMarkdown table {
        width: 100%;
        border-collapse: collapse;
        margin: 1.5rem 0;
    }
    .stMarkdown th, .stMarkdown td {
        border: 1px solid rgba(150, 150, 150, 0.4) !important;
        padding: 12px !important;
    }
    .stMarkdown th {
        background-color: rgba(150, 150, 150, 0.15) !important;
        font-weight: 700 !important;
    }
    .stMarkdown tr:nth-child(even) {
        background-color: rgba(150, 150, 150, 0.05) !important;
    }
    .stMarkdown tr:hover {
        background-color: rgba(150, 150, 150, 0.1) !important;
        transition: background-color 0.2s ease-in-out;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------- SESSION ----------------
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "role" not in st.session_state:
    st.session_state.role = None
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "tool_select" not in st.session_state:
    st.session_state.tool_select = "Auto (RAG first)"

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
    st.title("📝 Create Account")
    username = st.text_input("Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    role = st.selectbox("Role", ["HR", "Employee"])
    if st.button("Register"):
        if not username or not email or not password:
            st.warning("Please fill all fields")
        else:
            try:
                res = requests.post(
                    f"{BASE_URL}/register",
                    json={"username": username, "email": email, "password": password, "role": role},
                )
                if res.status_code == 200:
                    st.success("Account created! Please login.")
                else:
                    st.error("Registration failed")
            except Exception as e:
                st.error(f"Error: {e}")

# ---------------- LOGIN ----------------
elif not st.session_state.user_id and menu == "Login":
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if not username or not password:
            st.warning("Please fill all fields")
        else:
            try:
                res = requests.post(f"{BASE_URL}/login", json={"username": username, "password": password})
                if res.status_code == 200:
                    data = res.json()
                    if "error" in data:
                        st.error(data["error"])
                    else:
                        st.session_state.user_id = data["user_id"]
                        st.session_state.role = data["role"]
                        st.success("Login successful")
                        st.rerun()
                else:
                    st.error("Login failed")
            except Exception as e:
                st.error(f"Error: {e}")

# ---------------- MAIN APP ----------------
elif st.session_state.user_id:
    st.title("🤖 Enterprise Knowledge Assistant")

    # role badge
    if st.session_state.role == "Admin":
        st.info("👑 Admin Access")
    elif st.session_state.role == "HR":
        st.info("🧑‍💼 HR Access")
    else:
        st.info("👤 Employee Access")

    # Conversations in sidebar: NEW at top
    st.sidebar.subheader("💬 Conversations")
    if st.sidebar.button("➕ New Conversation"):
        try:
            res = requests.post(f"{BASE_URL}/chat/start", params={"user_id": st.session_state.user_id})
            if res.status_code == 200:
                data = res.json()
                st.session_state.conversation_id = data["conversation_id"]
                st.rerun()
            else:
                st.sidebar.error("Failed to create conversation")
        except Exception as e:
            st.sidebar.error(f"Error: {e}")

    conversations = []
    try:
        res = requests.get(f"{BASE_URL}/chat/user/{st.session_state.user_id}")
        if res.status_code == 200:
            conversations = res.json()
    except:
        st.sidebar.error("Backend not reachable")

    for conv in conversations:
        col1, col2 = st.sidebar.columns([4, 1])
        with col1:
            if st.button(conv["title"], key=f"open_{conv['conversation_id']}"):
                st.session_state.conversation_id = conv["conversation_id"]
                st.rerun()
        with col2:
            if st.button("❌", key=f"del_{conv['conversation_id']}"):
                try:
                    requests.delete(f"{BASE_URL}/chat/{conv['conversation_id']}")
                    if st.session_state.conversation_id == conv["conversation_id"]:
                        st.session_state.conversation_id = None
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Delete failed: {e}")

    st.sidebar.markdown("---")

    # Chat area
    st.subheader("💬 Chat")
    if not st.session_state.conversation_id:
        st.warning("Select or create a conversation")
    else:
        # ---------------- LOAD HISTORY ----------------
        messages = []
        try:
            res = requests.get(f"{BASE_URL}/chat/history/{st.session_state.conversation_id}")
            if res.status_code == 200:
                messages = res.json()
            else:
                st.error("Failed to load messages")
        except:
            st.error("Backend not reachable")

        # Render messages inside an expander with fixed height so input stays anchored below
        with st.expander("", expanded=True):
            for msg in messages:
                with st.chat_message("user"):
                    st.write(msg.get("question"))
                with st.chat_message("assistant"):
                    tool_used = msg.get("tool")
                    answer = msg.get("answer", "No response")
                    if tool_used:
                        st.write(f"Tool: {tool_used}\n\n{answer}")
                    else:
                        st.write(answer)

        # Bottom row: single tool dropdown + chat input (anchored because expander is scrollable)
        tool_options = [
            "Auto (RAG first)",
            "Policies (RAG)",
            "LLM (External)",
            "Document Summary",
            "Policy Comparison",
            "Agent Brain",
        ]
        try:
            default_index = tool_options.index(st.session_state.tool_select)
        except ValueError:
            default_index = 0

        col_tool, col_input = st.columns([2.5, 9.5])
        with col_tool:
            choice = st.selectbox("Tool", tool_options, index=default_index, key="inline_tool_select")
            st.session_state.tool_select = choice
        with col_input:
            user_input = st.chat_input(f"Ask something... (Tool: {st.session_state.tool_select})")

        # Send
        if user_input:
            with st.chat_message("user"):
                st.write(user_input)
            try:
                # map UI labels to a simple tool param
                tool_map = {
                    "Auto (RAG first)": "auto",
                    "Policies (RAG)": "rag",
                    "LLM (External)": "llm",
                    "Document Summary": "summary",
                    "Policy Comparison": "compare",
                    "Agent Brain": "agent",
                }
                selected_tool = tool_map.get(st.session_state.tool_select, "auto")
                res = requests.post(
                    f"{BASE_URL}/chat/message",
                    params={
                        "conversation_id": st.session_state.conversation_id,
                        "question": user_input,
                        "role": st.session_state.role,
                        "tool": selected_tool,
                    },
                )
                if res.status_code == 200:
                    data = res.json()
                    answer = data.get("answer", "No response")
                    # Prefix assistant response with tool used
                    display = f"Tool: {st.session_state.tool_select}\n\n{answer}"
                    with st.chat_message("assistant"):
                        st.write(display)
                    st.rerun()
                else:
                    st.error("Failed to get response")
            except Exception as e:
                st.error(f"Error: {e}")