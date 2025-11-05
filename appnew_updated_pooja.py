import base64
import os
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai
import pandas as pd
from io import BytesIO
import io
import csv
from fpdf import FPDF
from datetime import datetime

# Load environment variables
load_dotenv()

VALID_USERNAME = os.getenv("VALID_USERNAME")
VALID_PASSWORD = os.getenv("VALID_PASSWORD")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


# --- Streamlit Config ---
#st.set_page_config(page_title="GenAI Test Case Generator", layout="centered")
# st.title(" Prompt Pioneers | GenAI Test Center")
st.markdown(
    """
    <div style='text-align: center;'>
        <h1 style='color: #2C3E50; font-family: "Segoe UI", sans-serif;'>GenAI Test Centre</h1>
        <p style='font-size: 20px; '>by Prompt Pioneers | Powered by PolicyCenter</p>
    </div>
    """,
    unsafe_allow_html=True
)
# --- Session Login State ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# st.markdown("""
#     <div class="login-container">
#         <img src="https://companieslogo.com/img/orig/CAP.PA-9b4110b0.png?t=1720244491" width="120" style="margin-bottom: 20px;" />
# """, unsafe_allow_html=True)



with open("appnew_style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)





if not st.session_state.logged_in:
    # st.title("Access with Your Credentials")
    st.markdown(
        "<h2 style='text-align: center; font-family: Segoe UI'>Access with Your Credentials</h2>",
        unsafe_allow_html=True
        )

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

# --- Post Login ---
if st.session_state.logged_in:

    # Gemini Model Setup
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash-exp")

    def sanitize_text_for_pdf(text):
        return text.encode("latin-1", errors="replace").decode("latin-1")

    def generate_pdf_from_text(text: str) -> BytesIO:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        lines = sanitize_text_for_pdf(text).strip().splitlines()

        if any("|" in line for line in lines):
            for line in lines:
                if "|" not in line:
                    pdf.multi_cell(0, 10, line)
                else:
                    coloumn = [col.strip() for col in line.split("|") if col.strip()]
                    for col in coloumn:
                        pdf.cell(40, 10, txt=col, border=1)
                    pdf.ln()
        else:
            for line in lines:
                pdf.multi_cell(0, 10, line)

        buffer = BytesIO()
        pdf_output = pdf.output(dest="S").encode("latin-1", errors="replace")
        buffer.write(pdf_output)
        buffer.seek(0)
        return buffer

    # Session BRD Text
    if "brd_text" not in st.session_state:
        st.session_state.brd_text = ""

    # Step 1: Template Upload or Default
    st.subheader("Template Selection")
    upload_template_option = st.selectbox(
        "Do you want to upload a sample test case template?",
        options=["Yes", "No"],
        index=0
    )

    template_columns = []
    default_columns = [
        "Test Case Number", "Title", "Preconditions", "Steps",
        "Expected Results", "Transaction Type", "Status", "Test Data"
    ]

    if upload_template_option == "Yes":
        template_file = st.file_uploader("Upload Template (.csv or .xlsx)", type=["csv", "xlsx"])
        if template_file:
            df_template = pd.read_csv(template_file) if template_file.name.endswith(".csv") else pd.read_excel(template_file)
            template_columns = list(df_template.columns)
    elif upload_template_option == "No":
        st.info("Using default test case template structure.")
        template_columns = default_columns

    # Proceed if valid template is defined
    if template_columns:
        # Step 2: Use Case Upload
        st.subheader("Upload or Paste Use Case")
        usecase_file = st.file_uploader("Upload Use Case (.txt)", type=["txt"])
        # usecase_text = st.text_area("Or paste use case directly")
        usecase_text = ""
        final_usecase = ""
        if not usecase_file:
            usecase_text = st.text_area("Or paste use case directly")
        today = datetime.now().strftime("%B %d, %Y")
        if usecase_file:
            final_usecase = usecase_file.getvalue().decode("utf-8")
        elif usecase_text.strip():
            final_usecase = usecase_text.strip()



        # BRD Generation
        if final_usecase and st.button("📝 Generate BRD Manually"):
            with st.spinner("Generating BRD from use case..."):
                brd_prompt = f"Create a detailed Business Requirements Document (BRD) with today's date ({today}) based on the following Guidewire PolicyCenter use case:\n\n{final_usecase}"
                response = model.generate_content(brd_prompt)
                st.session_state.brd_text = (
                    response.candidates[0].content.parts[0].text.strip()
                    if response and response.candidates and response.candidates[0].content.parts
                    else ""
                )
        

            # Encode BRD text and PDF for download
            brd_txt_data = base64.b64encode(st.session_state.brd_text.encode("utf-8")).decode()
            brd_pdf_data = base64.b64encode(generate_pdf_from_text(st.session_state.brd_text).getvalue()).decode()

            # Render styled download buttons
            st.markdown(f"""
                <div class="custom-download" style="display: flex; justify-content: center; gap: 20px; margin-top: 20px; padding-bottom: 20px;">
                    <div class="custom-download" style="background-color: #4682B4; padding: 10px 20px; border-radius: 8px;">
                        <a href="data:text/plain;base64,{brd_txt_data}" 
                        download="generated_brd.txt" style="color: white; text-decoration: none; font-weight: bold;">
                        ⬇️ Download BRD (TXT)
                        </a>
                    </div>
                    <div class="custom-download" style="background-color: #4682B4; padding: 10px 20px; border-radius: 8px;">
                        <a href="data:application/pdf;base64,{brd_pdf_data}" 
                        download="generated_brd.pdf" style="color: white; text-decoration: none; font-weight: bold;">
                        ⬇️ Download BRD (PDF)
                        </a>
                    </div>
                </div>
            """, unsafe_allow_html=True)



        # # BRD Download
        # if st.session_state.brd_text:
        #     st.download_button("⬇️ Download BRD (TXT)", data=st.session_state.brd_text,
        #                     file_name="generated_brd.txt", mime="text/plain")
        #     st.download_button("⬇️ Download BRD (PDF)", data=generate_pdf_from_text(st.session_state.brd_text),
        #                     file_name="generated_brd.pdf", mime="application/pdf")

        # Step 3: Test Case Generation
        if st.button("🚀 Generate Test Cases"):
            if not st.session_state.brd_text:
                st.warning("Please generate the BRD manually first.")
            else:
                prompt_test_cases = f"""
You are a QA test case generator for Guidewire PolicyCenter. Based on the BRD below, do the following:

1. Automatically detect the transaction type (e.g., New Business, Policy Change, etc.).
2. Generate detailed test cases.
3. Each test case must include:
- Test Case Number (1, 2, 3...)
- A descriptive Title
- Preconditions
- Detailed, numbered Steps
- Expected Results
- Transaction Type (e.g., Submission, Policy Change)
- Status = Draft
- Test Data (e.g., customer info, product, vehicle)
4. Include additional scenarios based on the BRD (both Positive and Negative)
5. Include at least one of each Transaction type other than Use Case (e.g., Submission, Policy Change, Cancellation, Rewrite, Reinstatement)

Output strict CSV format (comma-separated). Wrap all fields in double quotes, even multiline ones.
Do NOT include markdown or ``` formatting.

Use the exact headers below:
"{'","'.join(default_columns)}"

In the steps field, number each step (e.g., 1. Do this, 2. Do that, 3. ...). Do not use "\\n" or any escape characters. Each new step should be on a new line inside the cell using a real line break (press Enter/Return), not the characters "\\n"

BRD:
{st.session_state.brd_text}
                """

                with st.spinner("Generating Test Cases..."):
                    response = model.generate_content(prompt_test_cases)
                    output_text = (
                        response.candidates[0].content.parts[0].text.strip()
                        if response and response.candidates and response.candidates[0].content.parts
                        else ""
                    )

                cleaned = output_text.strip().strip("`").replace("```csv", "").replace("```", "")
                try:
                    df_result = pd.read_csv(io.StringIO(cleaned), quoting=csv.QUOTE_ALL)
                    for col in default_columns:
                        if col not in df_result.columns:
                            df_result[col] = ""
                    df_result = df_result[default_columns]
                except Exception as e:
                    st.warning(f"Error parsing CSV: {e}")
                    df_result = pd.DataFrame({"Output": [output_text]})

                # Output
                st.subheader("✅ Generated Test Cases")
                st.dataframe(df_result, use_container_width=True, hide_index=True)

                excel_buffer = BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                    df_result.to_excel(writer, index=False, sheet_name="TestCases")
                excel_buffer.seek(0)

                # st.download_button("⬇️ Download Excel", data=excel_buffer,
                #                 file_name="test_cases.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                # st.download_button("⬇️ Download CSV", data=df_result.to_csv(index=False).encode("utf-8"),
                #                 file_name="test_cases.csv", mime="text/csv")
                st.markdown("""
    <div class="custom-download" style="display: flex; justify-content: center; gap: 20px; margin-top: 20px;">
        <div style="background-color: #4682B4; padding: 10px 20px; border-radius: 8px;">
            <a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{excel_data}" 
               download="test_cases.xlsx" style="color: white; text-decoration: none; font-weight: bold;">
               ⬇️ Download Excel
            </a>
        </div>
        <div style="background-color: #4682B4; padding: 10px 20px; border-radius: 8px;">
            <a href="data:text/csv;base64,{csv_data}" 
               download="test_cases.csv" style="color: white; text-decoration: none; font-weight: bold;">
               ⬇️ Download CSV
            </a>
        </div>
    </div>
""".format(
    excel_data=base64.b64encode(excel_buffer.getvalue()).decode(),
    csv_data=base64.b64encode(df_result.to_csv(index=False).encode("utf-8")).decode()
), unsafe_allow_html=True)

    else:
        st.info("Please select an option above to proceed.")