import os
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as gen_ai
import pandas as pd
from io import BytesIO
import io
import re

# Load environment variables
load_dotenv()

VALID_USERNAME = os.getenv("VALID_USERNAME")
VALID_PASSWORD = os.getenv("VALID_PASSWORD")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

st.set_page_config(page_title="GenAI Test Case Generator", layout="centered")

# --- Login Page ---
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

    
    
# --- Dashboard ---
if st.session_state.logged_in:
    st.title("🧪 GenAI Test Case Generator")
    def configure_google_model():
        gen_ai.configure(api_key=GOOGLE_API_KEY)
        return gen_ai.GenerativeModel("gemini-2.0-flash-exp")

    model = configure_google_model()
    selected_model = st.selectbox("Select a Model", ["Google Gemini AI"])
    uploaded_file = st.file_uploader("Upload Use Case File (.txt, .docx, .pdf)")
    manual_input = st.text_area("Or paste the user story directly")
    template_file = st.file_uploader("Upload Sample Template (.csv or .xlsx)")
    use_case_text = ""
    df_generated = pd.DataFrame()  # Initialize to empty DataFrame

    # Get use_case_text from file or manual input
    if uploaded_file is not None:
        use_case_text = uploaded_file.getvalue().decode("utf-8")
    else:
        use_case_text = manual_input

    # --- Template Handling ---
    template_columns_str = ""
    if template_file:
        if template_file.name.endswith('.csv'):
            df_template = pd.read_csv(template_file)
        else:
            df_template = pd.read_excel(template_file)
        template_columns = list(df_template.columns)
        template_columns_str = ", ".join(template_columns)
    else:
        df_template = None
        template_columns = []

    if st.button("🚀 Generate Test Cases"):
        if use_case_text.strip():
            st.success("Test cases generated successfully!")

            prompt_test_cases = f"""
            You are a QA test case generator. Based on the following use case details, generate at least 5 test cases.

            Output ONLY the test cases as a table in CSV format (comma-delimited), with the first row as column headers.
            The CSV must start with this header row exactly: {template_columns_str}
            Enclose every field in double quotes (""), even if it contains commas or is empty.
            Do not add any extra columns or commas before or after the header or data rows.
            Each row must have EXACTLY the same number of columns as the header, in the same order, and no extra commas or columns.
            Do not include any explanation, markdown, or extra text—only the table.
            In the steps field, number each step (e.g., 1. Do this, 2. Do that, 3. ...). Do not use "\n" or any escape characters. Each new step should be on a new line inside the cell using a real line break (press Enter/Return), not the characters "\n" or ";". Do not put a semicolon at the end of each step.

            Use Case Details:
            {use_case_text}

            Cover both positive and negative scenarios, edge cases, and business-specific rules (e.g., state-specific coverage validation, all required steps/screens in Guidewire Policy Center).
            If you are unsure about a column, leave it blank.
            """

            response = model.generate_content([prompt_test_cases])
            generated_text = response.candidates[0].content.parts[0].text if response and response.candidates else "No Test case generated"

            # Try to extract the CSV table from the LLM output
            # Find the CSV part (if LLM wraps it in markdown, remove backticks)
            csv_match = re.search(r"((?:.|\n)*?,(?:.|\n)*?)$", generated_text.strip())
            csv_text = csv_match.group(1) if csv_match else generated_text

            # Remove markdown code fences and extra text
            cleaned_text = re.sub(r"^```.*?```$", "", generated_text, flags=re.MULTILINE | re.DOTALL).strip()

            lines = cleaned_text.splitlines()
            header_ok = len(lines) > 0 and all(col.strip() in lines[0] for col in template_columns)
            has_data = len(lines) > 1

            if not cleaned_text or not header_ok or not has_data:
                st.warning("No table detected in the generated output. Showing raw output.")
                df_generated = pd.DataFrame({"Output": [generated_text]})
            else:
                try:
                    df_generated = pd.read_csv(io.StringIO(cleaned_text), delimiter=",", on_bad_lines='skip')
                    df_generated = df_generated.loc[:, ~df_generated.columns.str.contains('^Unnamed')]
                    # Always select only the template columns, in order
                    if template_columns:
                        for col in template_columns:
                            if col not in df_generated.columns:
                                df_generated[col] = ""
                        df_generated = df_generated[template_columns]
                    print(df_generated)
                except Exception as e:
                    st.warning(f"Could not parse generated test cases as a table. Showing raw output. Error: {e}")
                    df_generated = pd.DataFrame({"Output": [generated_text]})
            print("RAW GENERATED TEXT:\n", generated_text)

    # --- Build the final DataFrame for download/display ---
    if not df_generated.empty and template_columns and all(col in df_generated.columns for col in template_columns):
        df_final = df_generated[template_columns]
    else:
        df_final = df_generated

    st.dataframe(df_final)

    if df_final.shape[0] == 0 or (len(df_final.columns) == 1 and 'Output' in df_final.columns):
        st.warning("No test cases were generated. Please check your prompt, template, and use case details.")

    # --- Download Excel ---
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_final.to_excel(writer, index=False, sheet_name='TestCases')
    output.seek(0)

    st.download_button(
        label="⬇️ Download Excel",
        data=output,
        file_name="test_cases.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # --- Download CSV ---
    csv_output = df_final.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="⬇️ Download CSV",
        data=csv_output,
        file_name="test_cases.csv",
        mime="text/csv"
    )
