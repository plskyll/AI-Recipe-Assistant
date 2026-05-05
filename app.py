import streamlit as st
import os
from dotenv import load_dotenv
from llm_agent import run_agent

load_dotenv()

st.set_page_config(
    page_title="AI Recipe Assistant",
    page_icon="🍳",
    layout="centered"
)

st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #e65c00;
    }
    .subtitle {
        color: #666;
        margin-bottom: 1.5rem;
    }
    .history-item {
        background: #f9f9f9;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        margin: 0.3rem 0;
        font-size: 0.85rem;
        color: #444;
        cursor: pointer;
    }
</style>
""", unsafe_allow_html=True)

def init_session():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "gemini_history" not in st.session_state:
        st.session_state.gemini_history = []
    if "context" not in st.session_state:
        st.session_state.context = {}
    if "query_log" not in st.session_state:
        st.session_state.query_log = []

def main():
    init_session()

    st.markdown('<div class="main-title">🍳 AI Recipe Assistant</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Введіть інгредієнти або запит — система знайде або згенерує рецепт</div>', unsafe_allow_html=True)

    if not os.environ.get("GEMINI_API_KEY"):
        st.error("⚠️ GEMINI_API_KEY not found in environment variables.")
        st.stop()

    col1, col2 = st.columns([3, 1])

    with col2:
        if st.session_state.query_log:
            st.markdown("**📋 Історія запитів**")
            for q in reversed(st.session_state.query_log[-8:]):
                st.markdown(f'<div class="history-item">🔹 {q[:35]}</div>', unsafe_allow_html=True)

        if st.button("🗑 Очистити чат", use_container_width=True):
            st.session_state.messages = []
            st.session_state.gemini_history = []
            st.session_state.context = {}
            st.rerun()

    with col1:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input("Введіть інгредієнти або запит..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.query_log.append(prompt)

            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Обробляю запит..."):
                    answer, updated_history = run_agent(
                        prompt,
                        st.session_state.gemini_history,
                        st.session_state.context
                    )
                    st.session_state.gemini_history = updated_history
                st.markdown(answer)

            st.session_state.messages.append({"role": "assistant", "content": answer})
            st.rerun()

if __name__ == "__main__":
    main()