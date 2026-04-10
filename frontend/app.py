import streamlit as st
import requests

BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Enterprise AI Assistant", layout="wide")

# ---------------- SESSION ----------------
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "role" not in st.session_state:
    st.session_state.role = None
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "tool_select" not in st.session_state:
    st.session_state.tool_select = "Auto (RAG first)"
if "tool_locked" not in st.session_state:
    st.session_state.tool_locked = False

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
    role = st.selectbox("Role", ["Admin", "HR", "Employee"])

    if st.button("Register"):
        if not username or not email or not password:
            st.warning("Please fill all fields")
        else:
            try:
                res = requests.post(
                    f"{BASE_URL}/register",
                    json={
                        "username": username,
                        "email": email,
                        "password": password,
                        "role": role
                    }
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
                res = requests.post(
                    f"{BASE_URL}/login",
                    json={
                        "username": username,
                        "password": password
                    }
                )

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

    # ---------------- ROLE DISPLAY ----------------
    if st.session_state.role == "Admin":
        st.info("👑 Admin Access")
    elif st.session_state.role == "HR":
        st.info("🧑‍💼 HR Access")
    else:
        st.info("👤 Employee Access")

    # ---------------- SIDEBAR CONVERSATIONS ----------------
    st.sidebar.subheader("💬 Conversations")

    conversations = []

    try:
        res = requests.get(f"{BASE_URL}/chat/user/{st.session_state.user_id}")
        if res.status_code == 200:
            conversations = res.json()
    except:
        st.sidebar.error("Backend not reachable")

    # Display conversations with delete button
    for conv in conversations:
        col1, col2 = st.sidebar.columns([4, 1])

        with col1:
            if st.button(conv["title"], key=f"open_{conv['conversation_id']}"):
                st.session_state.conversation_id = conv["conversation_id"]

        with col2:
            if st.button("❌", key=f"del_{conv['conversation_id']}"):
                try:
                    requests.delete(f"{BASE_URL}/chat/{conv['conversation_id']}")

                    if st.session_state.conversation_id == conv["conversation_id"]:
                        st.session_state.conversation_id = None

                    st.rerun()

                except Exception as e:
                    st.sidebar.error(f"Delete failed: {e}")

    # ---------------- NEW CONVERSATION ----------------
    st.sidebar.markdown("---")

    if st.sidebar.button("➕ New Conversation"):
        try:
            res = requests.post(
                f"{BASE_URL}/chat/start",
                params={"user_id": st.session_state.user_id}
            )

            if res.status_code == 200:
                data = res.json()
                st.session_state.conversation_id = data["conversation_id"]
                st.rerun()
            else:
                st.sidebar.error("Failed to create conversation")

        except Exception as e:
            st.sidebar.error(f"Error: {e}")

    # ---------------- CHAT ----------------
    st.subheader("💬 Chat")

    if not st.session_state.conversation_id:
        st.warning("Select or create a conversation")

    else:
        # Tool selection + lock UI located at message input area
        col_tool, col_input = st.columns([1, 9])

        with col_tool:
            options = ["Auto (RAG first)", "Policies (RAG)", "LLM (External)"]
            # disable selection when locked to prevent changes
            try:
                tool_choice = st.selectbox(
                    "Tool",
                    options,
                    index=options.index(st.session_state.tool_select),
                    key="tool_select_box",
                    disabled=st.session_state.tool_locked
                )
            except Exception:
                # fallback if disabled isn't supported in this streamlit version
                tool_choice = st.selectbox(
                    "Tool",
                    options,
                    index=options.index(st.session_state.tool_select),
                    key="tool_select_box"
                )

            # lock/unlock buttons
            if not st.session_state.tool_locked:
                if st.button("+", key="lock_tool"):
                    st.session_state.tool_select = tool_choice
                    st.session_state.tool_locked = True
                    st.experimental_rerun()
            else:
                st.write("Locked")
                if st.button("Change", key="unlock_tool"):
                    st.session_state.tool_locked = False
                    st.experimental_rerun()

            # persist selection even when not locked
            st.session_state.tool_select = tool_choice

        with col_input:
            user_input = st.chat_input("Ask something...")

        # ---------------- LOAD HISTORY ----------------
        messages = []

        try:
            res = requests.get(
                f"{BASE_URL}/chat/history/{st.session_state.conversation_id}"
            )

            if res.status_code == 200:
                messages = res.json()
            else:
                st.error("Failed to load messages")

        except:
            st.error("Backend not reachable")

        # ---------------- DISPLAY CHAT ----------------
        for msg in messages:
            with st.chat_message("user"):
                st.write(msg.get("question"))

            with st.chat_message("assistant"):
                st.write(msg.get("answer"))

        # ---------------- SEND ----------------
        if user_input:
            with st.chat_message("user"):
                st.write(user_input)

            try:
                # map UI labels to a simple tool param
                tool_map = {
                    "Auto (RAG first)": "auto",
                    "Policies (RAG)": "rag",
                    "LLM (External)": "llm"
                }
                selected_tool = tool_map.get(st.session_state.tool_select, "auto")

                res = requests.post(
                    f"{BASE_URL}/chat/message",
                    params={
                        "conversation_id": st.session_state.conversation_id,
                        "question": user_input,
                        "role": st.session_state.role,
                        "tool": selected_tool
                    }
                )

                if res.status_code == 200:
                    data = res.json()

                    with st.chat_message("assistant"):
                        st.write(data.get("answer", "No response"))

                    st.rerun()

                else:
                    st.error("Failed to get response")

            except Exception as e:
                st.error(f"Error: {e}")