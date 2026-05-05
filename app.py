import streamlit as st
import os
from llm_agent import run_agent

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
    .hint-box {
        background: #fff8f0;
        border-left: 4px solid #e65c00;
        padding: 0.8rem 1rem;
        border-radius: 0 8px 8px 0;
        margin-bottom: 1rem;
        font-size: 0.9rem;
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
    if "history" not in st.session_state:
        st.session_state.history = []
    if "context" not in st.session_state:
        st.session_state.context = {}
    if "query_log" not in st.session_state:
        st.session_state.query_log = []


def display_chat():
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])


def main():
    init_session()

    st.markdown('<div class="main-title">🍳 AI Recipe Assistant</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Введіть інгредієнти або запит — система знайде або згенерує рецепт</div>', unsafe_allow_html=True)

    # Перевірка API ключа
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        st.error("⚠️ Не знайдено ANTHROPIC_API_KEY. Додайте ключ у змінні середовища.")
        st.code("export ANTHROPIC_API_KEY=your_key_here", language="bash")
        st.stop()

    # Підказки
    with st.expander("💡 Приклади запитів"):
        st.markdown("""
        - `яйця, сир, хліб` — пошук по інгредієнтах
        - `курка, рис, морква` — що приготувати з цих продуктів
        - `веганські рецепти з томатами` — з фільтром
        - `зроби цей рецепт без молока` — модифікація
        - `швидкий сніданок без глютену` — фільтрація
        - `скільки калорій у курці з рисом` — підрахунок калорій
        """)

    # Ліва колонка для бокової панелі
    col1, col2 = st.columns([3, 1])

    with col2:
        if st.session_state.query_log:
            st.markdown("**📋 Історія запитів**")
            for i, q in enumerate(reversed(st.session_state.query_log[-8:])):
                st.markdown(f'<div class="history-item">🔹 {q[:35]}{"..." if len(q) > 35 else ""}</div>', unsafe_allow_html=True)

        if st.button("🗑 Очистити чат", use_container_width=True):
            st.session_state.messages = []
            st.session_state.history = []
            st.session_state.context = {}
            st.rerun()

    with col1:
        display_chat()

        if prompt := st.chat_input("Введіть інгредієнти або запит..."):
            # Показуємо повідомлення користувача
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.query_log.append(prompt)

            with st.chat_message("user"):
                st.markdown(prompt)

            # Відповідь асистента
            with st.chat_message("assistant"):
                with st.spinner("Обробляю запит..."):
                    answer, updated_history = run_agent(
                        prompt,
                        st.session_state.history,
                        st.session_state.context
                    )
                    st.session_state.history = updated_history[-20:]  # зберігаємо останні 20 повідомлень
                st.markdown(answer)

            st.session_state.messages.append({"role": "assistant", "content": answer})
            st.rerun()


if __name__ == "__main__":
    main()
