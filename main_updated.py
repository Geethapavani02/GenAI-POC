import os
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as gen_ai
import pandas as pd
from io import BytesIO

# Load environment variables
load_dotenv()

VALID_USERNAME = os.getenv("VALID_USERNAME")
VALID_PASSWORD = os.getenv("VALID_PASSWORD")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Configure Streamlit page settings
st.set_page_config(
    page_title="Test Case Generator - AI Model",
    page_icon=":clipboard:",
    layout="centered",
)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("Login to Access Test Case Generator")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_button = st.form_submit_button("Login")
    
    if login_button:
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            st.session_state.logged_in = True
            st.success("Welcome to the Test Case Generator!")
            st.rerun()
        else:
            st.error("Invalid username or password. Please try again.")


if st.session_state.logged_in:
    st.title("Test Case Generator - AI Model")
    
    model_option = ["Google Gemini AI"]
    selected_model = st.selectbox("Select the AI Model", model_option)
    
    if "current_model" not in st.session_state:
        st.session_state.current_model = selected_model

    if st.session_state.current_model != selected_model:
        st.session_state.test_case_history = []
        st.session_state.current_model = selected_model
        st.info(f"You have switched to {selected_model}. Test case generation history has been cleared.")
        
    def configure_google_model():
        gen_ai.configure(api_key=GOOGLE_API_KEY)
        return gen_ai.GenerativeModel("gemini-2.0-flash-exp")

    model = configure_google_model()

    st.sidebar.header("Input Details")

    #User file upload for use cases or Manual input
    uploaded_file = st.sidebar.file_uploader("Upload a .txt file with use case details", type=["txt"])
    use_case_text = ""
    if uploaded_file is not None:
        use_case_text = uploaded_file.getvalue().decode("utf-8")
    else:
        use_case_text = st.sidebar.text_area("Enter use case Manually")
    
    if st.sidebar.button("Genearate Use Cases"):
        if use_case_text.strip():
            prompt_test_cases = f"""
            Generate a structured use case document based on the following details.
            Ensure the output includes:
            - Use Case: Create New Commercial Insurance Policy
            - Description:
                - This use case describes the steps involved in creating a new Guidewire Insurance policy for a business, including capturing a policyholder and vehicle information, selecting coverage options, and issuing policy."and
            - Status:
            - Pre-Conditions:
                - The agent is logged into insurance system.
            - Trigger:
                - The agent selects the "Guidewire Product"
            - Successfule End Conditions:
                - A new Guidewire insurance policy is created and issued as per the Business need
            - Actor: 
                - Agent
            - Related Use Cases:
                - None
            - Test Cases: (Generated Based on the Use Case)
                - Identify all possible scenario, including all cases 
                    - Guidewire Business specific rules (State-specific coverage validation, all possible steps required in Guidewrire Policy Center as well as screens available for the Guidewire Policy center)

            Use Case Details:
            {use_case_text}
            """

            response = model.generate_content([prompt_test_cases])
            generated_text = response.candidates[0].content.parts[0].text if response and response.candidates else "No Test case generated"

            sections = generated_text.split("\n\n")
            data = {"Section": [], "Details":[]}

            for section in sections:
                lines = section.split("\n", 1)
                if len(lines) == 2:
                    section_title, section_details = lines
                else:
                    section_title = lines[0]
                    section_details = ""

                data["Section"].append(section_title.strip())
                data["Details"].append(section_details.strip())

            df = pd.DataFrame(data)

            st.write("Generated Use Case & Test Cases")
            st.dataframe(df)

            output = BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df.to_excel(writer, sheet_name="Use Case & Test Cases", index=False)
                worksheet = writer.sheets["Use Case & Test Cases"]
                worksheet.set_column(0, 0, 40)
                worksheet.set_column(1, 1, 80)

            output.seek(0)

            st.download_button(
                label= "Download Use Case & Test Case",
                data=output,
                file_name="Use_cases.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        else:
            st.warning("Please uplaoda a file or enter use case details manually.")