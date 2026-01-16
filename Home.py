import streamlit as st

st.set_page_config(page_title="LLM Evaluation Platform", page_icon="🔍", layout="centered")

st.title("LLM Evaluation Platform")

st.markdown("""
## Welcome to the LLM Response Evaluation Platform

This platform allows you to evaluate LLM responses in two different ways:

1. **Human Evaluation**: Compare and evaluate LLM responses manually
2. **LLM-based Evaluation**: Use LLM agents to automatically evaluate responses

Please select one of the options below to continue:
""")

col1, col2 = st.columns(2)

with col1:
    st.page_link("pages/human_evaluator.py", label="Human Evaluator", icon="👤", help="Manually compare and evaluate LLM responses")

with col2:
    st.page_link("pages/llm_evaluator.py", label="LLM Evaluator", icon="🤖", help="Use LLM agents to automatically evaluate responses")

# Add some styling
st.markdown(
    """
    <style>
    div.stButton > button:first-child {
        background-color: #4CAF50;
        color: white;
        font-size: 16px;
        margin: 5px;
        padding: 10px 24px;
        border-radius: 8px;
        width: 100%;
    }
    div.stButton > button:hover {
        background-color: #45a049;
        color: white;
    }
    .stPageLink {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        margin: 10px 0;
        transition: transform 0.2s;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }
    .stPageLink:hover {
        transform: scale(1.05);
        background-color: #e6eaf1;
    }
    </style>
    """,
    unsafe_allow_html=True,
) 