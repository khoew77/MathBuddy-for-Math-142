import pymysql
import streamlit as st
from openai import OpenAI
import os
import json
from datetime import datetime
import fitz  # PyMuPDF
from PIL import Image
import pytesseract

# --- GLOBAL CONFIGURATION AND SETUP ---

# Configure page settings
st.set_page_config(page_title="MathBuddy", page_icon="🧮", layout="centered")

# Load secrets and initialize OpenAI client
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
MODEL = 'gpt-4o'  # Using a more recent model
client = OpenAI(api_key=OPENAI_API_KEY)

# Initial system prompt for the MathBuddy persona
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
    "Explain math in plain English. Do not use LaTeX, symbols like \(\), or math notation—use only plain text."
    "When the student has completed the necessary work and seems ready to provide an answer (indicated by a confident statement or after sufficient problem-solving effort), ask them for their final answer. Let them know that they can move on to the next phase of reflection or summary by clicking the 'Next' button."
    "If the user asks for a graph, return Python code using matplotlib and numpy, and do not say you can't generate a graph."
)

# --- HELPER FUNCTIONS ---

def extract_text_from_file(file):
    """Extracts text from an uploaded PDF or image file."""
    try:
        if file.type == "application/pdf":
            doc = fitz.open(stream=file.read(), filetype="pdf")
            text = "".join(page.get_text() for page in doc)
            return text
        elif file.type.startswith("image/"):
            image = Image.open(file)
            return pytesseract.image_to_string(image)
        else:
            raise ValueError("Unsupported file type.")
    except Exception as e:
        st.error(f"Error processing file: {e}")
        return None

def save_to_db(all_data):
    """Saves the entire chat and feedback summary to the database."""
    number = st.session_state.get('user_number', '').strip()
    name = st.session_state.get('user_name', '').strip()

    if not number or not name:
        st.error("Please enter your student ID and name.")
        return False

    try:
        db = pymysql.connect(
            host=st.secrets["DB_HOST"],
            user=st.secrets["DB_USER"],
            password=st.secrets["DB_PASSWORD"],
            database=st.secrets["DB_DATABASE"],
            charset="utf8mb4",
            autocommit=True
        )
        cursor = db.cursor()
        now = datetime.now()
        chat = json.dumps(all_data, ensure_ascii=False)
        sql = "INSERT INTO qna (number, name, chat, time) VALUES (%s, %s, %s, %s)"
        val = (number, name, chat, now)
        cursor.execute(sql, val)
        cursor.close()
        db.close()
        return True
    except pymysql.MySQLError as db_err:
        st.error(f"A database error occurred: {db_err}")
        return False
    except Exception as e:
        st.error(f"An unexpected error has occurred: {e}")
        return False

def get_chatgpt_response(prompt, context=""):
    """Generates a response from OpenAI, including context if provided."""
    system_messages = [{"role": "system", "content": initial_prompt}]
    if context:
        context_prompt = f"Use the following content from an uploaded document to answer the user's questions.\n\nDOCUMENT CONTENT:\n{context[:4000]}"
        system_messages.append({"role": "system", "content": context_prompt})

    messages_to_send = system_messages + st.session_state["messages"] + [{"role": "user", "content": prompt}]
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages_to_send,
    )
    answer = response.choices[0].message.content

    # Append to the single, unified message history
    st.session_state["messages"].append({"role": "user", "content": prompt})
    st.session_state["messages"].append({"role": "assistant", "content": answer})
    return answer

# --- PAGE DEFINITIONS ---

def page_1():
    """Page 1: Welcome and User Info Input."""
    st.title("📚 Welcome to MathBuddy")
    st.image("mathbuddy_promo.png", caption="Your Study Companion for Math Success 📱", width=300)
    st.write("Please enter your student ID and name, then click the 'Next' button.")

    st.session_state.user_number = st.text_input("Student ID", value=st.session_state.get("user_number", ""))
    st.session_state.user_name = st.text_input("Name", value=st.session_state.get("user_name", ""))

    if st.button("Next", key="page1_next"):
        if not st.session_state.user_number.strip() or not st.session_state.user_name.strip():
            st.error("Oops! Please enter both your student ID and name.")
        else:
            st.session_state.step = 2
            st.rerun()

def page_2():
    """Page 2: Instructions."""
    st.title("MathBuddy: Your Personal AI Calculus Tutor")
    st.subheader("How to Use MathBuddy")
    st.write(
       """  
       Welcome to **MathBuddy!** 🧠 Here's how to interact with the chatbot:
        1. Start by explaining your math question, problem, or exploration goal.
        2. MathBuddy will give you constructive feedback, suggest improvements, and ask guiding questions.
        3. Ask as many questions as you like to understand the feedback better.
        4. When you feel ready, you can say "I'm ready to move on" and MathBuddy will continue the guidance.

        ✍️ Examples:
        - "Solve and explain this equation step by step: (2x + 3)(x - 1) = 0"
        - “What transformations are applied to f(x) = x² to get f(x) = -2(x - 1)² + 5?”
        - “Factor this expression: x² + 5x + 6”
        
        Please make sure you're ready before moving on. When you're ready, click **Next**.
        """)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Previous"):
            st.session_state.step = 1
            st.rerun()
    with col2:
        if st.button("Next", key="page2_next"):
            st.session_state.step = 3
            st.rerun()

def page_3():
    """Page 3: Main Chat Interface with two input options."""
    st.title("Start Chatting with MathBuddy")
    st.write("✍️ Describe your math question or upload a document. Let's work through it together!")

    # --- TABS FOR DIFFERENT INPUT METHODS ---
    tab1, tab2 = st.tabs(["✍️ Direct Chat", "📄 Chat with a Document"])

    with tab1:
        st.header("Chat with MathBuddy")
        user_input = st.text_area("You: ", key="text_chat_input")
        if st.button("Send", key="send_text"):
            if user_input.strip():
                get_chatgpt_response(user_input)
                st.rerun()
            else:
                st.warning("Please enter a message.")

    with tab2:
        st.header("Chat with a Document")
        uploaded_file = st.file_uploader("Upload a PDF or image file", type=["pdf", "png", "jpg", "jpeg"])

        if uploaded_file:
            if "file_text" not in st.session_state or st.session_state.get("processed_file_name") != uploaded_file.name:
                with st.spinner("Processing file..."):
                    st.session_state.file_text = extract_text_from_file(uploaded_file)
                    st.session_state.processed_file_name = uploaded_file.name
        
        # Display status message inside the tab
        if "file_text" in st.session_state and st.session_state.file_text:
            # THIS LINE IS IMPROVED
            st.success(f"Successfully processed **{st.session_state.processed_file_name}**. Use the chat box at the bottom of the page to ask questions about it.")

        # Place the chat input logic inside the tab where it's used
        if "file_text" in st.session_state and st.session_state.file_text:
            if prompt := st.chat_input("Ask a question about your document..."):
                get_chatgpt_response(prompt, context=st.session_state.file_text)
                st.rerun()

    # --- UNIFIED CHAT HISTORY DISPLAY ---
    st.divider()
    st.subheader("📜 Full Chat History")
    if st.session_state.messages:
        for msg in reversed(st.session_state.messages):
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    else:
        st.write("Your conversation will appear here.")
    
    # --- NAVIGATION BUTTONS ---
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Previous"):
            st.session_state.step = 2
            st.rerun()
    with col2:
        if st.button("Next", key="page3_next"):
            st.session_state.step = 4
            st.session_state.feedback_saved = False
            st.rerun()

def page_4():
    """Page 4: Final Reflection and Summary."""
    st.title("Wrap-Up: Final Reflection")

    if not st.session_state.get("feedback_saved", False):
        with st.spinner("Generating your feedback summary..."):
            chat_history = "\n".join(f"{msg['role']}: {msg['content']}" for msg in st.session_state.messages)
            prompt = (
                f"This is a conversation between a student and MathBuddy:\n{chat_history}\n\n"
                "Please summarize the key concepts discussed, note the student's areas of strength, and suggest improvements or study tips for them to continue their learning."
            )
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": prompt}]
            )
            st.session_state.experiment_plan = response.choices[0].message.content
    
    st.subheader("📋 Feedback Summary")
    st.write(st.session_state.get("experiment_plan", "No summary generated yet."))

    # Save the combined data (chat + feedback) to the database
    if not st.session_state.get("feedback_saved", False):
        all_data_to_store = st.session_state.messages + [{"role": "feedback_summary", "content": st.session_state.experiment_plan}]
        if save_to_db(all_data_to_store):
            st.session_state.feedback_saved = True
        else:
            st.error("Failed to save conversation. Please try again!")

    if st.button("Previous", key="page4_back"):
        st.session_state.step = 3
        if "experiment_plan" in st.session_state:
            del st.session_state.experiment_plan
        st.session_state.feedback_saved = False
        st.rerun()

# --- MAIN ROUTING LOGIC ---

# Initialize session state keys
if "step" not in st.session_state:
    st.session_state.step = 1
if "messages" not in st.session_state:
    st.session_state.messages = []

# Page router
if st.session_state.step == 1:
    page_1()
elif st.session_state.step == 2:
    page_2()
elif st.session_state.step == 3:
    page_3()
elif st.session_state.step == 4:
    page_4()
