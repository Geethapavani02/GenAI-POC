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
import requests
from variables import JIRA_BASE_URL

# Load environment variables
load_dotenv()

VALID_USERNAME = os.getenv("VALID_USERNAME")
VALID_PASSWORD = os.getenv("VALID_PASSWORD")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# --- Streamlit Config ---
st.set_page_config(page_title="GenAI Test Case Generator", layout="centered")
st.title("🚀 Guidewire PolicyCenter – GenAI Test Case Generator")


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

    # --- SideBar Logout --- #
    # with st.sidebar:
    #     st.success(f"Logged in as: {VALID_USERNAME}")
    #     if st.button("Logout"):
    #         st.session_state.clear()
    #         st.rerun()

    # --- Gemini Model Config ---
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash-exp")

    def sanitize_text_for_pdf(text):
    # Replace characters not supported by latin-1
        return text.encode("latin-1", errors="replace").decode("latin-1")

    # --- PDF Generator ---
    def generate_pdf_from_text(text: str) -> BytesIO:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        lines = sanitize_text_for_pdf(text).strip().splitlines()

        if any("|" in line for line in lines):
            for line in lines:
                if "|" not in line:
                    pdf.multi_cell(0,10,line)
                else:
                    coloumn = [col.strip() for col in line.split("|") if col.strip()]
                    for col in coloumn:
                        pdf.cell(40, 10, txt=col, border= 1)
                    pdf.ln()
        else:
            for line in lines:
                pdf.multi_cell(0,10,line)



        # for line in text.splitlines():
        #     safe_line = line.encode("latin-1", errors="replace").decode("latin-1")
        #     pdf.multi_cell(0, 10, safe_line)
        buffer = BytesIO()
        pdf_output = pdf.output(dest="S").encode("latin-1", errors="replace")
        buffer.write(pdf_output)
        buffer.seek(0)
        return buffer

    def extract_adf_text(adf: dict) -> str:
        """Rudimentary extraction of plain text from Jira ADF (Atlassian Document Format)."""
        parts = []

        def walk(node):
            if not isinstance(node, dict):
                return
            node_type = node.get("type")
            if node_type in ("paragraph", "heading", "blockquote"):
                for c in node.get("content", []):
                    walk(c)
                parts.append("\n")
            elif node_type == "text":
                parts.append(node.get("text", ""))
            else:
                for c in node.get("content", []):
                    walk(c)

        walk(adf)
        text = "".join(parts)
        # Collapse multiple newlines and strip
        lines = [line.rstrip() for line in text.splitlines()]
        return "\n".join([line for line in lines if line.strip() != ""])

    # --- Session State Init ---
    if "brd_text" not in st.session_state:
        st.session_state.brd_text = ""
    if "usecase_text" not in st.session_state:
        st.session_state.usecase_text = ""

    # --- Use Case Upload / Jira Fetch ---
    st.subheader("📥 Upload, Paste, or Fetch Use Case from Jira")

    # --- Jira Fetcher ---
    with st.expander("🔁 Fetch Use Case from Jira"):
        st.write("Provide your Jira site, credentials (email + API token) and the issue key to fetch the issue description.")
        jira_url = st.text_input("Jira Base URL (e.g., https://yourorg.atlassian.net)", value=JIRA_BASE_URL, key="jira_url")
        jira_email = st.text_input("Jira Email (or username)", key="jira_email")
        jira_api_token = st.text_input("Jira API Token (create at id.atlassian.com/manage-profile/security/api-tokens)", type="password", key="jira_api_token")
        jira_issue_key = st.text_input("Jira Issue Key (e.g., PROJ-123)", key="jira_issue_key")
        if st.button("Fetch from Jira"):
            if not (jira_url and jira_email and jira_api_token and jira_issue_key):
                st.warning("Please provide Jira URL, email, API token, and issue key.")
            else:
                try:
                    api = f"{jira_url.rstrip('/')}/rest/api/2/issue/{jira_issue_key}?fields=summary,description"
                    resp = requests.get(api, auth=(jira_email, jira_api_token), headers={"Accept": "application/json"}, timeout=15)
                    resp.raise_for_status()
                    data = resp.json()
                    desc = data.get("fields", {}).get("description")
                    if isinstance(desc, dict):
                        fetched_text = extract_adf_text(desc)
                    else:
                        fetched_text = desc or ""
                    if not fetched_text:
                        fetched_text = data.get("fields", {}).get("summary", "")
                    st.session_state.usecase_text = fetched_text
                    st.success("Fetched use case and populated the text area.")
                except Exception as e:
                    st.error(f"Failed to fetch from Jira: {e}")

    usecase_file = st.file_uploader("Upload Use Case (.txt)", type=["txt"])
    usecase_text = st.text_area("Or paste use case directly", value=st.session_state.get("usecase_text", ""), key="usecase_text", height=200)
    today = datetime.now().strftime("%B %d,%Y")

    final_usecase = ""
    if usecase_file:
        final_usecase = usecase_file.getvalue().decode("utf-8")
    elif usecase_text.strip():
        final_usecase = usecase_text.strip()

    # --- Manual BRD Generation ---
    if final_usecase and st.button("📝 Generate BRD Manually"):
        with st.spinner("Generating BRD from use case..."):
            brd_prompt = f"Create a detailed Business Requirements Document (BRD) with today's date ({today}) based on the following Guidewire PolicyCenter use case:\n\n{final_usecase}"
            response = model.generate_content(brd_prompt)
            st.session_state.brd_text = (
                response.candidates[0].content.parts[0].text.strip()
                if response and response.candidates and response.candidates[0].content.parts
                else ""
            )
    # --- Download BRD (Optional) ---
    if st.session_state.brd_text:
        st.download_button("⬇️ Download BRD (TXT)", data=st.session_state.brd_text,
                        file_name="generated_brd.txt", mime="text/plain")
        st.download_button("⬇️ Download BRD (PDF)", data=generate_pdf_from_text(st.session_state.brd_text),
                        file_name="generated_brd.pdf", mime="application/pdf")
    # --- Template Upload ---
    st.subheader("📋 Upload Sample Test Case Template")
    template_file = st.file_uploader("Upload Template (.csv or .xlsx)", type=["csv", "xlsx"])
    template_columns = []
    if template_file:
        df_template = pd.read_csv(template_file) if template_file.name.endswith(".csv") else pd.read_excel(template_file)
        template_columns = list(df_template.columns)

    # --- Generate Test Cases ---
    if st.button("🚀 Generate Test Cases"):
        if not st.session_state.brd_text:
            st.warning("Please generate the BRD manually first.")
        elif not template_columns:
            st.warning("Please upload a valid test case template.")
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
    5. Include aatleast one of each Transaction types other than Use Case (e.g., Submission, Policy Change, Cancellation, Rewrite, Reinstatement, ....)

    Output strict CSV format (comma-separated). Wrap all fields in double quotes, even multiline ones.
    Do NOT include markdown or ``` formatting.

    Use the exact headers below:
    "Test Case Number","Title","Preconditions","Steps","Expected Results","Transaction Type","Status","Test Data"

    In the steps field, number each step (e.g., 1. Do this, 2. Do that, 3. ...). Do not use "\n" or any escape characters. Each new step should be on a new line inside the cell using a real line break (press Enter/Return), not the characters "\n"

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

            # --- Clean and Parse Output ---
            cleaned = output_text.strip().strip("`").replace("```csv", "").replace("```", "")
            try:
                df_result = pd.read_csv(io.StringIO(cleaned), quoting=csv.QUOTE_ALL)
                expected_cols = [
                    "Test Case Number", "Title", "Preconditions", "Steps",
                    "Expected Results", "Transaction Type", "Status", "Test Data"
                ]
                for col in expected_cols:
                    if col not in df_result.columns:
                        df_result[col] = ""
                df_result = df_result[expected_cols]
            except Exception as e:
                st.warning(f"Error parsing CSV: {e}")
                df_result = pd.DataFrame({"Output": [output_text]})

            # --- Show and Download ---
            st.subheader("✅ Generated Test Cases")
            st.dataframe(df_result, use_container_width=True, hide_index=True)

            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                df_result.to_excel(writer, index=False, sheet_name="TestCases")
            excel_buffer.seek(0)

            st.download_button("⬇️ Download Excel", data=excel_buffer,
                            file_name="test_cases.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            st.download_button("⬇️ Download CSV", data=df_result.to_csv(index=False).encode("utf-8"),
                            file_name="test_cases.csv", mime="text/csv")
