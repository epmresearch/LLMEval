import pandas as pd
import re
import streamlit as st
from io import StringIO

@st.cache_data
def extract_tables(markdown_text):
    """
    Extracts tables from Markdown text and returns them as a list of DataFrames.
    """
    tables = []
    pattern = re.compile(r'(\|.+?\|(?:\n\|[-:]+)+\n(?:\|.*?\|(?:\n|$))+)', re.DOTALL)
    matches = pattern.findall(markdown_text)
    for match in matches:
        table = pd.read_csv(StringIO(match), sep='|').dropna(axis=1, how='all').dropna(axis=0, how='all')
        tables.append(table)
    return tables

def display_response(response_text):
    """
    Displays the response text, rendering Markdown and tables appropriately.
    """
    tables = extract_tables(response_text)
    for table in tables:
        st.table(table)
        response_text = response_text.replace(table.to_markdown(), '')

    st.markdown(response_text)
