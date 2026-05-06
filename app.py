import os
import streamlit as st
from dotenv import load_dotenv
from google.genai.errors import ClientError
from llm_agent import run_agent

load_dotenv()

st.set_page_config(
    page_title="AI Recipe Assistant",
    page_icon="🍳",
    layout="centered",
)

st.markdown("""
<style>
    .title { font-size: 2.2rem; font-weight: 700; color: #e65c00; }
    .subtitle { color: #777; margin-bottom: 1rem; font-size: 0.95rem; }
    .history-entry {
        background: #f5f5f5;
        border-radius: 6px;
        padding: 0.4rem 0.8rem;
        margin: 0.2rem 0;
        font-size: 0.8rem;
        color: #555;
    }
    .section-label {
        font-size: 0.75rem;
        color: #999;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin: 0.8rem 0 0.3rem 0;
    }
</style>
""", unsafe_allow_html=True)

EXAMPLE_QUERIES = {
    "🔍 Пошук": [
        "яйця, цибуля, картопля",
        "курка, рис, морква",
        "томати, часник, паста",
    ],
    "🥗 Фільтри": [
        "веганські рецепти з томатами",
        "швидкий сніданок без глютену",
        "вегетаріанське за 10 хвилин",
    ],
    "🔄 Заміни": [
        "чим замінити молоко?",
        "немає яєць, що використати?",
        "чим замінити масло?",
    ],
    "✏️ Модифікація": [
        "зроби рецепт 3 без молока",
        "зроби борщ веганським",
    ],
    "🔥 Калорії": [
        "скільки калорій у картоплі з яйцями?",
        "калорійність курки з рисом",
    ],
}


def init_session():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "gemini_history" not in st.session_state:
        st.session_state.gemini_history = []
    if "context" not in st.session_state:
        st.session_state.context = {}
    if "query_log" not in st.session_state:
        st.session_state.query_log = []
    if "pending_prompt" not in st.session_state:
        st.session_state.pending_prompt = None


def _classify_error(e: Exception) -> str:
    if isinstance(e, ClientError):
        if e.status_code == 429:
            return "⏳ Перевищено ліміт запитів. Зачекайте хвилину і спробуйте знову."
        if e.status_code == 503:
            return "⏳ Сервери Gemini тимчасово перевантажені. Зачекайте 30 секунд і спробуйте ще раз."
        if e.status_code in (401, 403):
            return "🔑 Невірний API ключ. Перевірте файл .env"
        return f"❌ Помилка API {e.status_code}"
    err = str(e)
    if "503" in err or "UNAVAILABLE" in err:
        return "⏳ Сервери Gemini тимчасово перевантажені. Зачекайте 30 секунд і спробуйте ще раз."
    if "429" in err or "RESOURCE_EXHAUSTED" in err:
        return "⏳ Перевищено ліміт запитів. Зачекайте хвилину і спробуйте знову."
    if "401" in err or "403" in err or "API_KEY" in err:
        return "🔑 Невірний API ключ. Перевірте файл .env"
    return f"❌ Помилка: {err}"


def send_message(prompt: str):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.query_log.append(prompt)

    answer, updated_history = run_agent(
        prompt,
        st.session_state.gemini_history,
        st.session_state.context,
    )
    st.session_state.gemini_history = updated_history
    st.session_state.messages.append({"role": "assistant", "content": answer})


def main():
    init_session()

    st.markdown('<div class="title">🍳 AI Recipe Assistant</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">Введіть інгредієнти або запит — система знайде або згенерує рецепт</div>',
        unsafe_allow_html=True,
    )

    if not os.environ.get("GEMINI_API_KEY"):
        st.error("GEMINI_API_KEY не знайдено. Додайте його у файл .env або змінні середовища.")
        st.stop()

    col_chat, col_sidebar = st.columns([3, 1])

    with col_sidebar:
        st.markdown("**💡 Приклади запитів**")
        for category, examples in EXAMPLE_QUERIES.items():
            st.markdown(f'<div class="section-label">{category}</div>', unsafe_allow_html=True)
            for example in examples:
                if st.button(example, key=f"ex_{example}", use_container_width=True):
                    st.session_state.pending_prompt = example

        st.markdown("---")

        if st.session_state.query_log:
            st.markdown("**📋 Історія**")
            for entry in reversed(st.session_state.query_log[-6:]):
                st.markdown(f'<div class="history-entry">{entry[:38]}</div>', unsafe_allow_html=True)

        st.markdown("")
        if st.button("🗑 Очистити чат", use_container_width=True):
            st.session_state.messages = []
            st.session_state.gemini_history = []
            st.session_state.context = {}
            st.rerun()

    with col_chat:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # обробка кліку на приклад
        if st.session_state.pending_prompt:
            prompt = st.session_state.pending_prompt
            st.session_state.pending_prompt = None
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Обробляю запит..."):
                    send_message(prompt)
                st.markdown(st.session_state.messages[-1]["content"])
            st.rerun()

        if prompt := st.chat_input("Введіть інгредієнти або запит..."):
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Обробляю запит..."):
                    send_message(prompt)
                st.markdown(st.session_state.messages[-1]["content"])
            st.rerun()


if __name__ == "__main__":
    main()