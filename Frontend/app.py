import InvokeLambda as agenthelper
import streamlit as st
import json
import time
from log_setup import logger
from lxml import etree
from html import unescape
import re
import base64
import streamlit_pdf_viewer as spv
from utils import fetch_pdf
from streamlit_float import *
from streamlit_js_eval import streamlit_js_eval




# Streamlit page configuration
st.set_page_config(page_title="Chatbot", page_icon="💬", layout="wide")
float_init(theme=True, include_unstable_primary=False)

if "history" not in st.session_state:
    st.session_state.history = []
    st.session_state.case = ""
    st.session_state.prev_case = ""
    logger.info('New History Created !!')

st.sidebar.title("**Sample Queries:**")
sample_queries = [
    "Is there a victim?",
    "Give me summary",
    "What is the type of crime the defendant was arrested for?",
    "Is the defendant on any form of Criminal Release/Probation?",
    "Does the defendant have prior arrests?",
    "How many arrestee?",
    "How many convictions?",
    " Is there a Domestic Violence act involved?",
    "Was a firearm used?",
    "Was anyone threatened?",
    "Were drugs used?",
    "Is there a field test?",
    "What is the defendant’s domesticity?",
    "Did the defendant attempt to avoid arrest?",
    "Open case Form-IV-1",
    "Open case tempePD"
]
for query in sample_queries:
    st.sidebar.markdown(query)

col1, col2 = st.columns([1, 1])
width = streamlit_js_eval(js_expressions='window.innerWidth')
height = streamlit_js_eval(js_expressions='screen.height')

curr_case_name = ""
if height is not None:
    container_height = height - 350
else:
    print("Failed to get height")
    container_height = 700

with col1: 
    toggle_var = st.toggle("XML Response")
    
    with st.container(height=container_height):
        prompt = ""
        # Display a text box for input at the bottom
        with st.container():
            prompt = st.chat_input("Ex.- Enter the Query")
            button_b_pos = "1rem"
            button_css = float_css_helper(width="2.2rem", bottom=button_b_pos, transition=0)
            float_parent(css=button_css)

        # Displaying all the previous messages
        for message in st.session_state.history:
            with st.chat_message("user"):
                st.markdown(message["question"])
            with st.chat_message("assistant"):
                st.markdown(message["answer"])

        # random ID generator
        st.session_state.session_id = "ChatBot-Session"

        if prompt:
            with st.chat_message("user"):
                st.markdown(prompt)
            full_response = ""
            
            match = re.search(r'\bcase\s+([^:]+)', prompt, re.IGNORECASE)
            if match:
                case_name = match.group(1).strip()  # Remove leading/trailing whitespace
                st.session_state.case = case_name
                response_text = "Case Opened !!"
                print("print session in if:", st.session_state.case)
                the_response = response_text
                curr_case_name = case_name
            elif st.session_state.case:
                case_name = st.session_state.case
                curr_case_name = st.session_state.case
                print("print session in elif:", st.session_state.case)
                temp_prompt = f"{prompt} in {case_name}"
                print("prompt ",temp_prompt)
                # Prepare and invoke the lambda function since this is not a new case
                event = {"question": temp_prompt, 
                        "simplify_response": toggle_var}

                #Invoking Agent
                response = agenthelper.lambda_handler(event, None)
                responseJson = json.loads(response['body'])
                the_response = responseJson['response']
                logger.debug(f'response: {the_response}')
            else:
                the_response = 'No case name found in the query.'
                print("print session in else:", st.session_state.case)

            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                # Adding a small delay while displaying to make it like streaming
                for chunk in the_response.split("\\n"):  # Splitting on literal \n to handle new lines correctly
                    full_response += unescape(chunk) + " "  # Handle XML entities and append space for proper formatting
                    time.sleep(0.1)
                    # Add a blinking cursor to simulate typing
                    message_placeholder.markdown(full_response.strip() + "▌")

            # Save the history with unescaped newlines for future correct display
            st.session_state.history.append({"question": prompt, "answer": full_response.strip()})

with col2:
    if curr_case_name:
        st.markdown("### Case "+ curr_case_name + " Pdf")
        print("Case ",curr_case_name)
        pdf_bytes = fetch_pdf(curr_case_name) 
        if height is not None and width is not None: 
            pdf_height = height - 370
            pdf_width = (width // 2)
        else:
            print("Failed to get pdf height or width")
            pdf_height = 800
            pdf_width = 400
        
        spv.pdf_viewer(pdf_bytes, width= pdf_width, height=pdf_height)
        
        # st.experimental_memo(render_pdf)
        # st.markdown("### Case Report Preview")
        # pdf_bytes = fetch_pdf(caseName)
        
        # pdf_preview = base64.b64encode(pdf_bytes).decode("utf-8")
        # st.markdown(
        #     f'<iframe src="data:application/pdf;base64,{pdf_preview}" width="100%" height="450vh" type="application/pdf"></iframe>',
        #     unsafe_allow_html=True,
        # )