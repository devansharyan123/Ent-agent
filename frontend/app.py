import os
import streamlit as st
import requests
import html

BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Enterprise AI Assistant", layout="wide")

# ---------------------------------------------------------------------------
# Custom styling
# ---------------------------------------------------------------------------

# -------- CUSTOM CSS --------
st.markdown("""
<style>
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
    .source-tags {
        margin-top: 0.75rem;
        display: flex;
        flex-wrap: wrap;
        gap: 0.55rem;
    }
    .source-tag-wrap {
        position: relative;
        display: inline-flex;
        align-items: center;
    }
    .source-tag {
        display: inline-block;
        font-size: 0.86rem;
        line-height: 1.2rem;
        padding: 0.3rem 0.75rem;
        border-radius: 999px;
        border: 1px solid rgba(255, 185, 0, 0.65);
        background: rgba(255, 185, 0, 0.18);
        color: #f8cc6a;
        font-weight: 600;
        max-width: 28rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        cursor: help;
    }
    .source-tooltip {
        visibility: hidden;
        opacity: 0;
        position: absolute;
        bottom: 130%;
        left: 0;
        z-index: 1000;
        width: min(34rem, 78vw);
        max-height: 16rem;
        overflow-y: auto;
        padding: 0.6rem 0.75rem;
        border-radius: 0.55rem;
        background: #111827;
        color: #f9fafb;
        border: 1px solid rgba(255, 185, 0, 0.4);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
        font-size: 0.8rem;
        line-height: 1.25rem;
        white-space: pre-wrap;
        transition: opacity 0.16s ease;
        pointer-events: none;
    }
    .source-tag-wrap:hover .source-tooltip {
        visibility: visible;
        opacity: 1;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _source_key(message: dict) -> str:
    question = (message or {}).get("question", "")
    answer = (message or {}).get("answer", "")
    return f"{question}|||{answer}"




# def _render_recommendations(recommendations: list[str]) -> None:
#     """Display policy recommendations in a clean format."""
#     if not recommendations:
#         return
    
#     st.markdown("---")
#     st.markdown("**📚 Related Topics:**")
#     for rec in recommendations:
#         st.markdown(f"• {rec}")


def _load_chunk_tooltip(source: dict) -> str:
    chunk_text = str(source.get("chunk_text") or "").strip()
    if chunk_text:
        return chunk_text

    file_name = str(source.get("file_name") or "").strip()
    chunk_index = source.get("chunk_index")
    if not file_name or chunk_index is None:
        return "Source preview unavailable"

    cache_key = f"{file_name}|{chunk_index}"
    cached = st.session_state.chunk_preview_cache.get(cache_key)
    if cached:
        return cached

    try:
        preview_res = requests.get(
            f"{BASE_URL}/chat/chunk-preview",
            params={"file_name": file_name, "chunk_index": int(chunk_index)},
            timeout=5,
        )
        if preview_res.status_code == 200:
            preview_text = (preview_res.json().get("chunk_text") or "").strip()
            if preview_text:
                st.session_state.chunk_preview_cache[cache_key] = preview_text
                return preview_text
    except Exception:
        pass

    return "Source preview unavailable"


def _render_source_tags(sources: list[dict]) -> None:
    if not sources:
        return

    # Show only first two unique tags for cleaner UI.
    unique_sources = []
    seen = set()
    for src in sources:
        key = (str(src.get("file_name") or ""), src.get("chunk_index"), src.get("page_number"))
        if key in seen:
            continue
        seen.add(key)
        unique_sources.append(src)
        if len(unique_sources) == 2:
            break

    chips = []
    for src in unique_sources:
        file_name = str(src.get("file_name") or "Unknown source")
        chunk_text = _load_chunk_tooltip(src)
        page_no = src.get("page_number")
        chunk_index = src.get("chunk_index")

        preview = file_name
        if page_no is not None:
            preview = f"{file_name} | p.{page_no}"
        elif chunk_index is not None:
            preview = f"{file_name} | chunk {chunk_index}"
        if len(preview) > 65:
            preview = preview[:62].rstrip() + "..."

        header = file_name
        if page_no is not None:
            header = f"{file_name} | page {page_no}"
        elif chunk_index is not None:
            header = f"{file_name} | chunk {chunk_index}"

        safe_chunk = chunk_text.strip()[:1400]
        if not safe_chunk:
            safe_chunk = "Source preview unavailable"

        chips.append(
            "<span class=\"source-tag-wrap\">"
            f"<span class=\"source-tag\">{html.escape(preview)}</span>"
            f"<span class=\"source-tooltip\"><strong>{html.escape(header)}</strong>\n\n{html.escape(safe_chunk)}</span>"
            "</span>"
        )

    st.markdown(
        "<div class=\"source-tags\">" + "".join(chips) + "</div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Session initialization
# ---------------------------------------------------------------------------

# -------- SESSION --------
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
if "message_sources" not in st.session_state:
    st.session_state.message_sources = {}
if "chunk_preview_cache" not in st.session_state:
    st.session_state.chunk_preview_cache = {}

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

# -------- SIDEBAR --------
st.sidebar.title("🏢 Enterprise AI Assistant")

if st.session_state.user_id:
    st.sidebar.success(f"Logged in as {st.session_state.role}")

    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

else:
    menu = st.sidebar.radio("Navigation", ["Login", "Register"])


# ---------------------------------------------------------------------------
# Register interface
# ---------------------------------------------------------------------------

# -------- REGISTER --------
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


# ---------------------------------------------------------------------------
# Login interface
# ---------------------------------------------------------------------------

# -------- LOGIN --------
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


# ---------------------------------------------------------------------------
# Main application interface
# ---------------------------------------------------------------------------

# -------- MAIN APP --------
elif st.session_state.user_id:

    st.title("🤖 Enterprise Knowledge Assistant")

    # Role display
    if st.session_state.role == "Admin":
        st.info("👑 Admin Access")
    elif st.session_state.role == "HR":
        st.info("🧑‍💼 HR Access")
    else:
        st.info("👤 Employee Access")

    # ---------------------------------------------------------------------------
    # Conversation management
    # ---------------------------------------------------------------------------

    # -------- SIDEBAR CONVERSATIONS --------
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

    # ---------------------------------------------------------------------------
    # New conversation
    # ---------------------------------------------------------------------------

    # -------- NEW CONVERSATION --------
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

    # ---------------------------------------------------------------------------
    # Chat interface
    # ---------------------------------------------------------------------------

    # -------- CHAT --------
    st.subheader("💬 Chat")

    if not st.session_state.conversation_id:
        st.warning("Select or create a conversation")

    else:
        # Tool selection + lock UI located at message input area
        col_tool, col_input = st.columns([1, 9])

        with col_tool:
            options = ["Auto (RAG first)", "Policies (RAG)", "LLM (External)", "Document Summary", "Policy Comparison", "Policy Recommendation"]
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

        # ---------------------------------------------------------------------------
        # Load conversation history
        # ---------------------------------------------------------------------------

        # -------- LOAD HISTORY --------
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

        # ---------------------------------------------------------------------------
        # Display messages
        # ---------------------------------------------------------------------------

        # -------- DISPLAY CHAT --------
        for msg in messages:
            with st.chat_message("user"):
                st.write(msg.get("question"))

            with st.chat_message("assistant"):
                st.write(msg.get("answer"))
                cached_sources = st.session_state.message_sources.get(_source_key(msg), [])
                _render_source_tags(cached_sources)
                
                # Display recommendations
                # recommendations = msg.get("recommendations", [])
                # _render_recommendations(recommendations)

        # ---------------------------------------------------------------------------
        # Send message
        # ---------------------------------------------------------------------------

        # -------- SEND --------
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
                    "Policy Recommendation": "recommend",
                    "Agent Brain": "agent"
                }
                selected_tool = tool_map.get(st.session_state.tool_select, "auto")

                # Policy retrieval path returns grounded sources via /ask.
                if selected_tool in {"auto", "rag"}:
                    res = requests.post(
                        f"{BASE_URL}/ask",
                        json={
                            "user_id": st.session_state.user_id,
                            "question": user_input,
                            "conversation_id": st.session_state.conversation_id,
                        },
                    )
                else:
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
                    answer_text = data.get("answer", "No response")
                    sources = data.get("sources", [])
                    recommendations = data.get("recommendations", [])

                    message_key = _source_key({
                        "question": user_input,
                        "answer": answer_text,
                    })
                    st.session_state.message_sources[message_key] = sources

                    # with st.chat_message("assistant"):
                    #     st.write(answer_text)
                    #     _render_source_tags(sources)
                    #     _render_recommendations(recommendations)

                    st.rerun()

                else:
                    st.error("Failed to get response")

            except Exception as e:
                st.error(f"Error: {e}")