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

# --- GLOBAL CONFIGURATION AND SETUP ---

st.set_page_config(page_title="MathBuddy", page_icon="🧮", layout="centered")

OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
MODEL = 'gpt-4o'
client = OpenAI(api_key=OPENAI_API_KEY)

# --- CORRECTED INITIAL PROMPT ---
initial_prompt = (
    "You are a helpful, supportive chatbot named MathBuddy designed to assist college-level math students in exploring and refining their understanding of mathematical concepts. "
    "Your job is to guide students as they work through problems on their own."
    "Act as a coach, not a solver. Break the problem into manageable parts and guide the student with leading questions."
    "When a student asks a math question, **do not immediately solve it**."
    "DO NOT give full solutions or final answers."
    "Instead, first try to understand how much the student already knows."
    "Ask a few gentle, open-ended questions to assess their thinking."
    "Encourage them to explain their approach or where they got stuck. Examples:\n"
    "- What have you tried so far?\n"
    "- Where are you stuck?\n"
    "- What do you remember about similar problems?\n\n"    
    "Ask helpful questions, break the problem into steps, and suggest strategies."
    "Only offer the next helpful nudge. Let the student do the reasoning."
    "You encourage students to develop their own ideas, attempt problem solving independently, and reflect on their thinking. "
    "Your tone is friendly, clear, and educational. "
    "Use a friendly, encouraging tone. After assessing their understanding, offer a hint or suggestion—"
    "but still do not give the full solution."
    "If students are working on a project or math investigation, start by asking them to describe their math question, goal, and any process or methods they’ve already tried. "
    "Provide specific feedback on strengths and suggestions for improvement based on standard mathematical practices (e.g., clarity of reasoning, appropriate use of definitions, logical structure, completeness). "
    "Guide the student toward discovering the solution on their own. Use questions, hints, and scaffolding to support their thinking, rather than giving full solutions."
    "Work with the student to explore different strategies or perspectives, but leave the solving to them."
    "Encourage productive struggle. Help the student see mistakes as opportunities to learn, not something to avoid with full answers."
    "Always prioritize guiding students to reflect and revise."
    "Explain all mathematical expressions clearly using plain text only. Use parentheses for grouping, fractions like '3/4', powers like 'x^2', and avoid LaTeX or special symbols. Format expressions for readability."
    "Explain math in plain English. Do not use LaTeX, symbols like \\(\\), or math notation—use only plain text."
    "When the student has completed the necessary work and seems ready to provide an answer (indicated by a confident statement or after sufficient problem-solving effort), ask them for their final answer. Let them know that they can move on to the next phase of reflection or summary by clicking the 'Next' button."
    "If the user asks for a graph of a specific function (e.g., 'graph y=x^2'), you MUST return Python code that plots that EXACT function using matplotlib and numpy. "
    "The code should be complete, correct, and enclosed in a single Python code block (```python...). "
    "Generate code that defines a figure and axes (e.g., fig, ax = plt.subplots()) and uses `ax.plot()`, `ax.set_title()`, `ax.set_xlabel()`, `ax.set_ylabel()`, and `ax.grid(True)`. "
    "Do NOT provide code for a different function than the one requested. Do not include `plt.show()`."
)

# --- HELPER FUNCTIONS ---
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

def handle_direct_chat():
    """Callback to process and clear the direct chat input."""
    prompt = st.session_state.direct_chat_box
    if prompt and prompt.strip():
        get_chatgpt_response(prompt)
        # Clear the input box after processing
        st.session_state.direct_chat_box = ""

def page_3():
    """Page 3: Main Chat Interface with repositioned input."""
    st.title("💬 Start Chatting with MathBuddy")
    st.write("Describe your math question or upload a document to begin!")

    tab1, tab2 = st.tabs(["✍️ Direct Chat", "📄 Chat with a Document"])

    with tab1:
        st.header("Type your question here")
        # Use st.text_input for in-line placement and Enter-to-submit
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
            # This chat input remains at the bottom, dedicated to the document
            if prompt := st.chat_input("Ask a question about your document..."):
                get_chatgpt_response(prompt, context=st.session_state.file_text)
                st.rerun()

    st.divider()
    st.subheader("📜 Full Chat History")
    if st.session_state.messages:
        for msg in reversed(st.session_state.messages):
            with st.chat_message(msg["role"]):
                content = msg["content"]
                if "```python" in content and "matplotlib" in content:
                    code = content.split("```python\n")[1].split("```")[0]
                    try:
                        fig, ax = plt.subplots()
                        exec(code, {'plt': plt, 'np': np, 'ax': ax, 'fig': fig})
                        st.pyplot(fig)
                    except Exception as e:
                        st.error(f"⚠️ An error occurred while generating the graph:\n{e}")
                        st.code(code, language='python')
                else:
                    st.markdown(content)

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

if st.session_state.step == 1:
    page_1()
elif st.session_state.step == 2:
    page_2()
elif st.session_state.step == 3:
    page_3()
elif st.session_state.step == 4:
    page_4()
