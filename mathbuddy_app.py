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

# --- FINAL, CORRECTED INITIAL PROMPT ---
initial_prompt = (
    "You are a helpful, supportive chatbot named MathBuddy... (previous instructions)... "
    # THIS IS THE FINAL, CORRECTED INSTRUCTION FOR GRAPHING:
    "If the user asks for a graph of a specific function (e.g., 'graph y=x^2'), your response MUST start immediately with the Python code block and contain NOTHING ELSE. "
    "The code must be enclosed in a single Python code block (```python...). "
    "Your code will be executed in an environment where `fig, ax = plt.subplots()` has ALREADY been run. "
    "Therefore, you MUST NOT include `import matplotlib.pyplot as plt` or `fig, ax = plt.subplots()` in your code. "
    "You MUST use the pre-existing `ax` variable to plot (e.g., `ax.plot(...)`, `ax.set_title(...)`, `ax.grid(True)`). "
    "Do NOT provide code for a different function than the one requested. Do not include `plt.show()`."
)

# (The rest of your script remains exactly the same as the last version.)

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
    st.session_state.recent_message = {"user": prompt, "assistant": answer}
    return answer

def handle_direct_chat():
    prompt = st.session_state.direct_chat_box
    if prompt and prompt.strip():
        get_chatgpt_response(prompt)
        st.session_state.direct_chat_box = ""

def page_1():
    st.title("📚 Welcome to MathBuddy")
    st.image("MathBuddy.png", caption="Your Study Companion for Math Success 📱", width=550)
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

def render_message_content(content):
    """Renders message content, executing and plotting code if found."""
    # Use regex to find a code block, making it more robust
    match = re.search(r"```(python)?\n?(.*)```", content, re.DOTALL)
    
    # Check for a code block AND a plotting command.
    if match and ('ax.plot' in content or 'ax.scatter' in content):
        code = match.group(2).strip()
        try:
            fig, ax = plt.subplots()
            # Execute the code, passing the figure and axes
            exec(code, {'plt': plt, 'np': np, 'ax': ax, 'fig': fig})
            # Display the plot in Streamlit
            st.pyplot(fig)
            plt.close(fig) # Close the figure to free up memory
        except Exception as e:
            st.error(f"⚠️ An error occurred while generating the graph:\n{e}")
            st.code(code, language='python')
    else:
        st.markdown(content) # Display regular text messages

def page_3():
    """Page 3: Main Chat Interface with consistent message rendering."""
    st.title("💬 Start Chatting with MathBuddy")
    st.write("Describe your math question or upload a document to begin!")

    tab1, tab2 = st.tabs(["✍️ Direct Chat", "📄 Chat with a Document"])

    with tab1:
        st.header("Type your question here")
        st.text_input(
            "Your question:",
            key="direct_chat_box",
            on_change=handle_direct_chat,
            placeholder="Ask MathBuddy a question and press Enter...",
            label_visibility="collapsed"
        )

    with tab2:
        st.header("Upload a file to discuss")
        uploaded_file = st.file_uploader("📁 Choose a PDF or image file", type=["pdf", "png", "jpg", "jpeg"])
        if uploaded_file and st.session_state.get("processed_file_name") != uploaded_file.name:
            with st.spinner("Processing file..."):
                st.session_state.file_text = extract_text_from_file(uploaded_file)
                st.session_state.processed_file_name = uploaded_file.name
        
        if st.session_state.get("file_text"):
            st.success(f"✅ Successfully processed **{st.session_state.processed_file_name}**.")
            if prompt := st.chat_input("Ask a question about your document..."):
                get_chatgpt_response(prompt, context=st.session_state.file_text)
                st.rerun()

    st.divider()
    st.subheader("📌 Most Recent Exchange")
    recent = st.session_state.get("recent_message", {"user": "", "assistant": ""})
    if recent["user"] or recent["assistant"]:
        with st.chat_message("user"):
            st.markdown(recent["user"])
        with st.chat_message("assistant"):
            # Use the new rendering function here
            render_message_content(recent["assistant"])
    else:
        st.info("Your first exchange will appear here.")
    
    st.divider()
    st.subheader("📜 Full Chat History")

    if st.session_state.messages:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                # Also use the new rendering function here for consistency
                render_message_content(msg["content"])

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("◀️ Previous"):
            st.session_state.step = 2
            st.rerun()
    with col2:
        if st.button("▶️ Next", key="page3_next"):
            st.session_state.step = 4
            st.session_state.feedback_saved = False
            st.rerun()

def page_4():
    st.title("🎉 Wrap-Up: Final Reflection")
    if not st.session_state.get("feedback_saved"):
        with st.spinner("Generating your feedback summary..."):
            chat_history = "\n".join(f"{msg['role']}: {msg['content']}" for msg in st.session_state.messages)
            prompt = f"This is a conversation between a student and MathBuddy:\n{chat_history}\n\nPlease summarize the key concepts discussed, note the student's areas of strength, and suggest improvements or study tips for them to continue their learning."
            response = client.chat.completions.create(model=MODEL, messages=[{"role": "system", "content": prompt}])
            st.session_state.experiment_plan = response.choices[0].message.content
    st.subheader("📋 Feedback Summary")
    st.write(st.session_state.get("experiment_plan", ""))
    if not st.session_state.get("feedback_saved"):
        all_data_to_store = st.session_state.messages + [{"role": "feedback_summary", "content": st.session_state.experiment_plan}]
        if save_to_db(all_data_to_store):
            st.session_state.feedback_saved = True
    if st.button("◀️ Previous", key="page4_back"):
        st.session_state.step = 3
        st.rerun()

# --- MAIN ROUTING LOGIC ---
if "step" not in st.session_state:
    st.session_state.step = 1
if "messages" not in st.session_state:
    st.session_state.messages = []
if "recent_message" not in st.session_state:
    st.session_state.recent_message = {"user": "", "assistant": ""}

if st.session_state.step == 1:
    page_1()
elif st.session_state.step == 2:
    page_2()
elif st.session_state.step == 3:
    page_3()
elif st.session_state.step == 4:
    page_4()
