# app.py - Complete Streamlit Frontend with Working Recommendations for All Tools
import streamlit as st
import requests
import html
import uuid
import os
import re

# Disable LangSmith warnings
os.environ["LANGCHAIN_TRACING_V2"] = "false"

BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Enterprise AI Assistant", layout="wide")

# ---------------- CUSTOM CSS ----------------
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
    .recommendations-container {
        margin-top: 1rem;
        padding-top: 0.75rem;
        border-top: 1px solid rgba(150, 150, 150, 0.2);
    }
    .recommendation-header {
        font-size: 0.9rem;
        font-weight: 600;
        color: #f8cc6a;
        margin-bottom: 0.5rem;
    }
    .stButton button {
        background: linear-gradient(135deg, #1e3a5f 0%, #0f2b45 100%);
        color: white;
        border: 1px solid #2e6b8f;
        border-radius: 20px;
        padding: 0.4rem 1rem;
        margin: 0.25rem;
        font-size: 0.85rem;
        transition: all 0.2s ease;
    }
    .stButton button:hover {
        background: linear-gradient(135deg, #2e5a8f 0%, #1f3b5f 100%);
        border-color: #4e8faf;
        transform: translateY(-1px);
    }
    .tool-badge {
        display: inline-block;
        background: rgba(255, 185, 0, 0.2);
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.7rem;
        color: #f8cc6a;
        margin-left: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)


def extract_recommendations_from_text(text: str) -> tuple:
    """Extract recommendations from answer text and return clean answer + recommendations"""
    if not text:
        return text, ""
    
    # Look for "Other questions you would like to know about" section
    patterns = [
        r'(###\s*Other questions you would like to know about.*?)(?:\n\n|$)',  # Section header with ###
        r'(Other questions you would like to know about.*?)(?:\n\n|$)',  # New section
        r'(Would you like to know more about.*?)(?:\n\n|$)',  # Direct questions
        r'(💡.*?)(?:\n\n|$)',  # Emoji header
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            recommendations_text = match.group(1).strip()
            # Remove the recommendations from main answer
            answer = text[:match.start()].strip()
            return answer, recommendations_text
    
    # Check for bullet points at the end
    lines = text.split('\n')
    recommendations_lines = []
    answer_lines = []
    found_recommendations = False
    
    for i, line in enumerate(reversed(lines)):
        if line.strip().startswith('-') and ('Would you like' in line or 'know more about' in line):
            recommendations_lines.insert(0, line.strip())
            found_recommendations = True
        elif found_recommendations and line.strip():
            # We've found all recommendations
            break
        elif not found_recommendations:
            answer_lines.insert(0, line)
    
    if found_recommendations:
        answer = '\n'.join(answer_lines).strip()
        recommendations = '\n'.join(recommendations_lines)
        return answer, recommendations
    
    return text, ""


def _source_key(message: dict) -> str:
    """Generate unique key for message sources"""
    question = (message or {}).get("question", "")
    answer = (message or {}).get("answer", "")
    return f"{question}|||{answer}"


def _load_chunk_tooltip(source: dict) -> str:
    """Load chunk preview for tooltip"""
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
    """Render source tags with tooltips"""
    if not sources:
        return

    unique_sources = []
    seen = set()
    for src in sources:
        key = (str(src.get("file_name") or ""), src.get("chunk_index"), src.get("page_number"))
        if key in seen:
            continue
        seen.add(key)
        unique_sources.append(src)
        if len(unique_sources) == 3:
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


def _render_recommendations(recommendations: str) -> None:
    """Render clickable recommendation buttons"""
    if not recommendations or recommendations.strip() == "":
        return
    
    st.markdown('<div class="recommendations-container">', unsafe_allow_html=True)
    st.markdown('<div class="recommendation-header">💡 You might also want to know:</div>', unsafe_allow_html=True)
    
    # Parse bullet points
    lines = recommendations.split('\n')
    buttons_created = 0
    
    for line in lines:
        line = line.strip()
        # Match bullet points with or without dash
        if line.startswith('-'):
            rec_text = line[1:].strip()
        elif line.startswith('•'):
            rec_text = line[1:].strip()
        elif line.startswith('*'):
            rec_text = line[1:].strip()
        elif line.startswith('Would you like'):
            rec_text = line.strip()
        else:
            continue
        
        # Remove any markdown formatting
        rec_text = rec_text.replace('**', '').replace('*', '')
        
        # Create button
        if st.button(rec_text, key=f"rec_{hash(rec_text)}_{buttons_created}", use_container_width=True):
            st.session_state.auto_question = rec_text
            st.rerun()
        
        buttons_created += 1
        if buttons_created >= 5:  # Limit to 5 recommendations
            break
    
    st.markdown('</div>', unsafe_allow_html=True)


# ---------------- SESSION ----------------
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "role" not in st.session_state:
    st.session_state.role = None
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "tool_select" not in st.session_state:
    st.session_state.tool_select = "Policies (RAG)"
if "tool_locked" not in st.session_state:
    st.session_state.tool_locked = False
if "message_sources" not in st.session_state:
    st.session_state.message_sources = {}
if "chunk_preview_cache" not in st.session_state:
    st.session_state.chunk_preview_cache = {}
if "auto_question" not in st.session_state:
    st.session_state.auto_question = None

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
        # Tool selection UI
        col_tool, col_input = st.columns([2, 8])
        
        with col_tool:
            # Define tool options
            tool_options = [
                "Auto (RAG first)",
                "Policies (RAG)",
                "LLM (External)",
                "Document Summary",
                "Policy Comparison"
            ]
            
            # Get current tool index
            try:
                current_index = tool_options.index(st.session_state.tool_select)
            except:
                current_index = 1  # Default to "Policies (RAG)"
            
            tool_choice = st.selectbox(
                "🔧 Select Tool",
                tool_options,
                index=current_index,
                key="tool_select_box",
                disabled=st.session_state.tool_locked,
                help="Choose which tool to use for answering"
            )
            
            # Lock/Unlock tool
            col_lock, col_unlock = st.columns(2)
            with col_lock:
                if not st.session_state.tool_locked:
                    if st.button("🔒 Lock Tool", key="lock_tool", use_container_width=True):
                        st.session_state.tool_select = tool_choice
                        st.session_state.tool_locked = True
                        st.rerun()
            
            with col_unlock:
                if st.session_state.tool_locked:
                    if st.button("🔓 Unlock", key="unlock_tool", use_container_width=True):
                        st.session_state.tool_locked = False
                        st.rerun()
            
            # Show current locked tool
            if st.session_state.tool_locked:
                st.info(f"🔒 Using: **{st.session_state.tool_select}**")
            
            # Update session state
            if not st.session_state.tool_locked:
                st.session_state.tool_select = tool_choice
        
        with col_input:
            # Auto-fill from recommendation click
            if st.session_state.auto_question:
                user_input = st.session_state.auto_question
                st.session_state.auto_question = None
            else:
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
                answer_text = msg.get("answer", "")
                recommendations = msg.get("recommendations", "")
                
                # Always extract recommendations from answer to clean it
                answer_text, extracted_recs = extract_recommendations_from_text(answer_text)
                
                # Convert recommendations list to string if needed
                if isinstance(recommendations, list):
                    recommendations = "\n".join([f"- {item}" for item in recommendations])
                elif not recommendations and extracted_recs:
                    recommendations = extracted_recs
                
                st.write(answer_text)
                
                # Display recommendations if available (as buttons only)
                if recommendations:
                    _render_recommendations(recommendations)
                
                cached_sources = st.session_state.message_sources.get(_source_key(msg), [])
                _render_source_tags(cached_sources)

        # ---------------- SEND MESSAGE ----------------
        if user_input:
            with st.chat_message("user"):
                st.write(user_input)

            try:
                # Map UI tool selection to backend tool parameter
                tool_map = {
                    "Auto (RAG first)": "auto",
                    "Policies (RAG)": "rag",
                    "LLM (External)": "llm",
                    "Document Summary": "summary",
                    "Policy Comparison": "compare"
                }
                
                selected_tool = tool_map.get(st.session_state.tool_select, "auto")
                recommendations = ""
                sources = []
                
                # For all tools, use /chat/message endpoint which handles everything
                res = requests.post(
                    f"{BASE_URL}/chat/message",
                    params={
                        "conversation_id": st.session_state.conversation_id,
                        "question": user_input,
                        "role": st.session_state.role,
                        "tool": selected_tool
                    },
                    timeout=30
                )
                
                if res.status_code == 200:
                    data = res.json()
                    answer_text = data.get("answer", "No response")
                    sources = data.get("sources", [])
                    
                    # Try to extract recommendations from answer
                    clean_answer, recommendations = extract_recommendations_from_text(answer_text)
                    
                    # Save to session state
                    message_key = _source_key({
                        "question": user_input,
                        "answer": clean_answer,
                    })
                    st.session_state.message_sources[message_key] = sources

                    # Display response
                    with st.chat_message("assistant"):
                        st.write(clean_answer)
                        
                        # Display recommendations if available
                        if recommendations:
                            _render_recommendations(recommendations)
                        
                        _render_source_tags(sources)

                    st.rerun()
                else:
                    st.error(f"Failed to get response: {res.status_code}")

            except requests.exceptions.Timeout:
                st.error("Request timeout. Please try again.")
            except Exception as e:
                st.error(f"Error: {e}")