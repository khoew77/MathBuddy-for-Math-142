import pymysql
import streamlit as st
from openai import OpenAI
import os
import json
from datetime import datetime
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import matplotlib.pyplot as plt
import numpy as np
import re

# --- GLOBAL CONFIGURATION AND SETUP ---

st.set_page_config(page_title="MathBuddy", page_icon="🧮", layout="centered")

OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
MODEL = 'gpt-4o'
client = OpenAI(api_key=OPENAI_API_KEY)

# --- UPDATED INITIAL PROMPT ---
initial_prompt = (
    "You are a helpful, supportive chatbot named MathBuddy... (previous instructions)... " # Abridged for clarity
    "Explain all mathematical expressions clearly using plain text only... (previous instructions)... "
    # THIS IS THE UPDATED INSTRUCTION FOR GRAPHING:
    "If the user asks for a graph of a specific function (e.g., 'graph y=x^2'), you MUST return Python code that plots that EXACT function using matplotlib and numpy. "
    "The code should be complete, correct, and enclosed in a single Python code block (```python...). "
    "Generate code that defines a figure and axes (e.g., fig, ax = plt.subplots()) and uses `ax.plot()`, `ax.set_title()`, `ax.set_xlabel()`, `ax.set_ylabel()`, and `ax.grid(True)`. "
    "Do NOT provide code for a different function than the one requested. Do not include `plt.show()`."
)

# --- HELPER FUNCTIONS ---
# (All helper functions like extract_text_from_file, save_to_db, get_chatgpt_response remain the same)
def extract_text_from_file(file):
    try:
        if file.type == "application/pdf":
            doc = fitz.open(stream=file.read(), filetype="pdf")
            text = "".join(page.get_text() for page in doc)
            return text
        elif file.type.startswith("image/"):
            image = Image.open(file)
            return pytesseract.image_to_string(image)
    except Exception as e:
        st.error(f"❌ Error processing file: {e}")
        return None

def save_to_db(all_data):
    number = st.session_state.get('user_number', '').strip()
    name = st.session_state.get('user_name', '').strip()
    if not number or not name:
        st.error("⚠️ Please enter your student ID and name.")
        return False
    try:
        db = pymysql.connect(host=st.secrets["DB_HOST"], user=st.secrets["DB_USER"], password=st.secrets["DB_PASSWORD"], database=st.secrets["DB_DATABASE"], charset="utf8mb4", autocommit=True)
        cursor = db.cursor()
        now = datetime.now()
        chat = json.dumps(all_data, ensure_ascii=False)
        sql = "INSERT INTO qna (number, name, chat, time) VALUES (%s, %s, %s, %s)"
        val = (number, name, chat, now)
        cursor.execute(sql, val)
        cursor.close()
        db.close()
        return True
    except Exception as e:
        st.error(f"❌ An error occurred: {e}")
        return False

def get_chatgpt_response(prompt, context=""):
    system_messages = [{"role": "system", "content": initial_prompt}]
    if context:
        context_prompt = f"Use the following content from an uploaded document...\n\nDOCUMENT CONTENT:\n{context[:4000]}"
        system_messages.append({"role": "system", "content": context_prompt})
    messages_to_send = system_messages + st.session_state["messages"] + [{"role": "user", "content": prompt}]
    response = client.chat.completions.create(model=MODEL, messages=messages_to_send)
    answer = response.choices[0].message.content
    st.session_state["messages"].append({"role": "user", "content": prompt})
    st.session_state["messages"].append({"role": "assistant", "content": answer})
    return answer

# --- PAGE DEFINITIONS ---

def page_1():
    st.title("📚 Welcome to MathBuddy")
    st.image("mathbuddy_promo.png", caption="Your Study Companion for Math Success 📱", width=300)
    st.write("Please enter your student ID and name to get started.")
    st.session_state.user_number = st.text_input("🆔 Student ID", value=st.session_state.get("user_number", ""))
    st.session_state.user_name = st.text_input("👤 Name", value=st.session_state.get("user_name", ""))
    if st.button("▶️ Next", key="page1_next"):
        if not st.session_state.user_number.strip() or not st.session_state.user_name.strip():
            st.error("⚠️ Oops! Please enter both your student ID and name.")
        else:
            st.session_state.step = 2
            st.rerun()

def page_2():
    st.title("📖 How to Use MathBuddy")
    st.write("Follow these simple steps to make the most of your session.")
    st.info("""
       **1. Start a Conversation:** Explain your math question, problem, or goal.
       **2. Get Guided Feedback:** MathBuddy will ask questions and suggest improvements.
       **3. Ask Anything:** Don't hesitate to ask for clarification.
       **4. Move On When Ready:** When you're done, just click the **Next** button.
    """)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("◀️ Previous"):
            st.session_state.step = 1
            st.rerun()
    with col2:
        if st.button("▶️ Next", key="page2_next"):
            st.session_state.step = 3
            st.rerun()

def page_3():
    st.title("💬 Start Chatting with MathBuddy")
    st.write("Describe your math question or upload a document to begin!")
    tab1, tab2 = st.tabs(["✍️ Direct Chat", "📄 Chat with a Document"])

    with tab1:
        st.header("Type your question here")
        user_input = st.text_area("You: ", key="text_chat_input", label_visibility="collapsed")
        if st.button("📤 Send", key="send_text"):
            if user_input.strip():
                get_chatgpt_response(user_input)
                st.rerun()

    with tab2:
        st.header("Upload a file to discuss")
        uploaded_file = st.file_uploader("📁 Choose a PDF or image file", type=["pdf", "png", "jpg", "jpeg"])
        if uploaded_file and st.session_state.get("processed_file_name") != uploaded_file.name:
            with st.spinner("Processing file..."):
                st.session_state.file_text = extract_text_from_file(uploaded_file)
                st.session_state.processed_file_name = uploaded_file.name
        if st.session_state.get("file_text"):
            st.success(f"✅ Successfully processed **{st.session_state.processed_file_name}**. Ask questions below.")
            if prompt := st.chat_input("Ask a question about your document..."):
                get_chatgpt_response(prompt, context=st.session_state.file_text)
                st.rerun()

    st.divider()
    st.subheader("📜 Full Chat History")

    # --- UPDATED CHAT DISPLAY LOGIC ---
    if st.session_state.messages:
        for msg in reversed(st.session_state.messages):
            with st.chat_message(msg["role"]):
                content = msg["content"]
                # Check if the content contains a python code block for matplotlib
                if "
