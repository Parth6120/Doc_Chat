import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import api_client as api

st.set_page_config(
    page_title="Doc Chat",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ─── State ─────────────────────────────────────────────────
def _init_state():
    defaults = {
        "user_id": "",
        "sessions": [],
        "sessions_loaded": False,
        "active_session_id": None,
        "messages": [],
        "renaming_sid": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ─── Sidebar ────────────────────────────────────────────────
with st.sidebar:
    st.title("📚 Doc Chat")

    uid = st.text_input("User ID", value=st.session_state.user_id, placeholder="e.g. user_123")
    if uid != st.session_state.user_id:
        st.session_state.user_id = uid
        st.session_state.sessions = []
        st.session_state.sessions_loaded = False
        st.session_state.active_session_id = None
        st.session_state.messages = []
        st.session_state.renaming_sid = None
        st.rerun()

    if not st.session_state.user_id:
        st.info("Enter a User ID to get started.")
        st.stop()

    st.divider()

    # ── Document upload ──
    st.subheader("Upload Documents")
    uploaded = st.file_uploader("PDF or TXT", type=["pdf", "txt"], label_visibility="collapsed")
    if uploaded and st.button("Ingest Document", use_container_width=True, type="primary"):
        with st.spinner(f"Ingesting {uploaded.name}…"):
            try:
                result = api.ingest_document(uploaded.read(), uploaded.name, st.session_state.user_id)
                st.success(f"✅ {result['chunks_vectorized']} chunks stored")
            except Exception as exc:
                st.error(str(exc))

    st.divider()

    # ── New session form ──
    st.subheader("Sessions")
    with st.form("new_session", clear_on_submit=True):
        new_name = st.text_input("Session name", placeholder="e.g. Q1 Report Analysis")
        if st.form_submit_button("➕  Create Session", use_container_width=True):
            title = new_name.strip() or "New Chat"
            with st.spinner("Creating…"):
                try:
                    sid = api.create_session(st.session_state.user_id, title=title)
                    st.session_state.active_session_id = sid
                    st.session_state.messages = []
                    st.session_state.sessions = api.list_sessions(st.session_state.user_id)
                    st.session_state.sessions_loaded = True
                except Exception as exc:
                    st.error(str(exc))
            st.rerun()

    # Load sessions once per user
    if not st.session_state.sessions_loaded:
        try:
            st.session_state.sessions = api.list_sessions(st.session_state.user_id)
            st.session_state.sessions_loaded = True
        except Exception as exc:
            st.error(f"Could not load sessions: {exc}")

    # ── Session list ──
    for session in st.session_state.sessions:
        sid = session["session_id"]
        title = session.get("title", sid[:20])
        is_active = sid == st.session_state.active_session_id

        if st.session_state.renaming_sid == sid:
            with st.form(f"rename_{sid}", clear_on_submit=True):
                new_title = st.text_input("New name", value=title, key=f"rt_{sid}")
                c1, c2 = st.columns(2)
                with c1:
                    save = st.form_submit_button("Save", use_container_width=True)
                with c2:
                    cancel = st.form_submit_button("Cancel", use_container_width=True)

            if save:
                final = new_title.strip() or title
                try:
                    api.rename_session(sid, final)
                    for s in st.session_state.sessions:
                        if s["session_id"] == sid:
                            s["title"] = final
                            break
                except Exception as exc:
                    st.error(str(exc))
                st.session_state.renaming_sid = None
                st.rerun()

            if cancel:
                st.session_state.renaming_sid = None
                st.rerun()

        else:
            col_btn, col_edit, col_del = st.columns([5, 1, 1])
            with col_btn:
                if st.button(
                    title,
                    key=f"sel_{sid}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary",
                ):
                    if not is_active:
                        st.session_state.active_session_id = sid
                        try:
                            st.session_state.messages = api.get_session_messages(sid)
                        except Exception:
                            st.session_state.messages = []
                        st.rerun()
            with col_edit:
                if st.button("✏️", key=f"edit_{sid}", help="Rename session"):
                    st.session_state.renaming_sid = sid
                    st.rerun()
            with col_del:
                if st.button("🗑", key=f"del_{sid}", help="Delete session"):
                    try:
                        api.delete_session(sid)
                        st.session_state.sessions = [
                            s for s in st.session_state.sessions if s["session_id"] != sid
                        ]
                        if st.session_state.active_session_id == sid:
                            st.session_state.active_session_id = None
                            st.session_state.messages = []
                    except Exception as exc:
                        st.error(str(exc))
                    st.rerun()


# ─── Main area ──────────────────────────────────────────────
if not st.session_state.active_session_id:
    st.info("👈 Select or create a session from the sidebar to start chatting.")
    st.stop()

active_title = next(
    (s.get("title", st.session_state.active_session_id)
     for s in st.session_state.sessions
     if s["session_id"] == st.session_state.active_session_id),
    st.session_state.active_session_id,
)
st.subheader(active_title)
st.caption(f"Session ID: `{st.session_state.active_session_id}`")

# Render history
for msg in st.session_state.messages:
    with st.chat_message("human" if msg["role"] == "human" else "assistant"):
        st.markdown(msg["content"])

# Chat input
if prompt := st.chat_input("Ask a question about your documents…"):
    st.session_state.messages.append({"role": "human", "content": prompt})
    with st.chat_message("human"):
        st.markdown(prompt)

    sources: list = []
    with st.chat_message("assistant"):
        response_text = st.write_stream(
            api.stream_chat(
                st.session_state.user_id,
                st.session_state.active_session_id,
                prompt,
                sources,
            )
        )

    st.session_state.messages.append({"role": "ai", "content": response_text})

    if sources:
        st.caption("Sources: " + "  ·  ".join(f"`{s}`" for s in sources))

    st.rerun()
