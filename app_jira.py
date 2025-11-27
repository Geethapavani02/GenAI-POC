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
from variables import JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN

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
    model = genai.GenerativeModel("gemini-2.5-flash-lite")
   #model = genai.GenerativeModel("gpt-4o")

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

    def attach_csv_to_jira(jira_url: str, jira_email: str, jira_api_token: str, jira_issue_key: str, csv_data: str, filename: str = "test_cases.csv") -> bool:
        """Attach a CSV file to a Jira issue."""
        try:
            # Upload attachment
            attach_url = f"{jira_url.rstrip('/')}/rest/api/2/issue/{jira_issue_key}/attachments"
            headers = {
                "Accept": "application/json",
                "X-Atlassian-Token": "no-check"
            }
            files = {"file": (filename, csv_data, "text/csv")}
            resp = requests.post(
                attach_url,
                auth=(jira_email, jira_api_token),
                headers=headers,
                files=files,
                timeout=15
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            st.error(f"Failed to attach CSV to Jira: {e}")
            return False

    def attach_excel_to_jira(jira_url: str, jira_email: str, jira_api_token: str, jira_issue_key: str, excel_data: BytesIO, filename: str = "test_cases.xlsx") -> bool:
        """Attach an Excel file to a Jira issue."""
        try:
            # Upload attachment
            attach_url = f"{jira_url.rstrip('/')}/rest/api/2/issue/{jira_issue_key}/attachments"
            headers = {
                "Accept": "application/json",
                "X-Atlassian-Token": "no-check"
            }
            files = {"file": (filename, excel_data.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            resp = requests.post(
                attach_url,
                auth=(jira_email, jira_api_token),
                headers=headers,
                files=files,
                timeout=15
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            st.error(f"Failed to attach Excel to Jira: {e}")
            return False

    # --- Session State Init ---
    if "brd_text" not in st.session_state:
        st.session_state.brd_text = ""
    if "usecase_text" not in st.session_state:
        st.session_state.usecase_text = ""
    if "fetched_from_jira" not in st.session_state:
        st.session_state.fetched_from_jira = False
    if "use_usecase_as_brd" not in st.session_state:
        st.session_state.use_usecase_as_brd = False
    if "testcases_generated" not in st.session_state:
        st.session_state.testcases_generated = False
    if "testcases_df" not in st.session_state:
        st.session_state.testcases_df = None
    if "fetched_jira_issue_key" not in st.session_state:
        st.session_state.fetched_jira_issue_key = ""
    if "testcases_csv_data" not in st.session_state:
        st.session_state.testcases_csv_data = ""
    if "testcases_excel_data" not in st.session_state:
        st.session_state.testcases_excel_data = None
    if "sync_history" not in st.session_state:
        st.session_state.sync_history = []

    # --- Use Case Upload / Jira Fetch ---
    st.subheader("📥 Upload, Paste, or Fetch Use Case from Jira")

    # --- Jira Fetcher ---
    with st.expander("🔁 Fetch Use Case from Jira"):
        st.write("Provide your Jira site, credentials (email + API token) and the issue key to fetch the issue description.")
        jira_url = st.text_input("Jira Base URL (e.g., https://yourorg.atlassian.net)", value=JIRA_BASE_URL, key="jira_url")
        jira_email = st.text_input("Jira Email (or username)", value=JIRA_EMAIL, key="jira_email")
        jira_api_token = st.text_input("Jira API Token (create at id.atlassian.com/manage-profile/security/api-tokens)", type="password",value=JIRA_API_TOKEN, key="jira_api_token")
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
                    
                    # Check if description is empty or not available
                    if not fetched_text or fetched_text.strip() == "":
                        summary = data.get("fields", {}).get("summary", "")
                        if summary and summary.strip():
                            fetched_text = summary
                            st.warning(f"⚠️ No description found for issue {jira_issue_key}. Using summary instead.")
                        else:
                            st.error(f"❌ No description or summary available for issue {jira_issue_key}. Please add a description to this issue.")
                            st.session_state.sync_history.append({
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "action": "Jira Fetch",
                                "issue_key": jira_issue_key,
                                "status": "❌ No description/summary available"
                            })
                    else:
                        st.session_state.usecase_text = fetched_text
                        st.session_state.fetched_from_jira = True
                        st.session_state.fetched_jira_issue_key = jira_issue_key
                        # Log to history
                        st.session_state.sync_history.append({
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "action": "Jira Fetch",
                            "issue_key": jira_issue_key,
                            "status": "✅ Success"
                        })
                        st.success("Fetched use case and populated the text area.")
                except Exception as e:
                    # Log failure to history
                    st.session_state.sync_history.append({
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "action": "Jira Fetch",
                        "issue_key": jira_issue_key,
                        "status": f"❌ Failed: {str(e)[:50]}"
                    })
                    st.error(f"Failed to fetch from Jira: {e}")

    # If a Jira fetch was performed, hide paste/upload options and use fetched text as BRD.
    if not st.session_state.get("fetched_from_jira"):
        usecase_file = st.file_uploader("Upload Use Case (.txt)", type=["txt"])
        usecase_text = st.text_area("Or paste use case directly", value=st.session_state.get("usecase_text", ""), key="usecase_text", height=200)
        # Option: use the pasted/fetched use case directly as the BRD for test-case generation
        # This checkbox will be auto-checked when a Jira fetch succeeds.
        use_usecase_as_brd = st.checkbox("Use this use case as the BRD for generating test cases (skip manual BRD)", value=st.session_state.get("use_usecase_as_brd", False), key="use_usecase_as_brd")
        today = datetime.now().strftime("%B %d,%Y")

        final_usecase = ""
        if usecase_file:
            final_usecase = usecase_file.getvalue().decode("utf-8")
        elif usecase_text.strip():
            final_usecase = usecase_text.strip()
    else:
        fetched_text = st.session_state.get("usecase_text", "")
        if not fetched_text or fetched_text.strip() == "":
            st.info("Jira use case fetched — no description. Upload a template to generate test cases.")
        else:
            st.info("Jira use case fetched — upload a template to generate test cases.")
        # Use the fetched usecase as the final_usecase
        final_usecase = fetched_text
        usecase_text = final_usecase

    # --- Manual BRD Generation ---
    # Only show manual BRD generation when the user did not fetch from Jira
    if (not st.session_state.get("fetched_from_jira")) and final_usecase and st.button("📝 Generate BRD Manually"):
        with st.spinner("Generating BRD from use case..."):
            today = datetime.now().strftime("%B %d,%Y")
            brd_prompt = f"Create a detailed Business Requirements Document (BRD) with today's date ({today}) based on the following Guidewire PolicyCenter use case:\n\n{final_usecase}"
            response = model.generate_content(brd_prompt)
            st.session_state.brd_text = (
                response.candidates[0].content.parts[0].text.strip()
                if response and response.candidates and response.candidates[0].content.parts
                else ""
            )
            # If user generated a BRD manually, clear the Jira-fetch flag
            st.session_state.fetched_from_jira = False
    # --- Download BRD (Optional) ---
    # Hide BRD download when the session is using the fetched Jira use case as BRD
    if st.session_state.brd_text and not st.session_state.get("fetched_from_jira"):
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

    def generate_test_cases(brd_text_value: str, template_cols: list):
        if not brd_text_value:
            st.warning("No BRD content available for test-case generation.")
            return
        if not template_cols:
            st.warning("Please upload a valid test case template.")
            return

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
    {brd_text_value}
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

        st.subheader("✅ Generated Test Cases")
        st.dataframe(df_result, use_container_width=True, hide_index=True)

        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            df_result.to_excel(writer, index=False, sheet_name="TestCases")
        excel_buffer.seek(0)

        csv_data = df_result.to_csv(index=False).encode("utf-8")
        
        st.download_button("⬇️ Download Excel", data=excel_buffer,
                        file_name="test_cases.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.download_button("⬇️ Download CSV", data=csv_data,
                        file_name="test_cases.csv", mime="text/csv")

        # Store the dataframe and CSV data for Jira attachment
        st.session_state.testcases_generated = True
        st.session_state.testcases_df = df_result
        st.session_state.testcases_csv_data = csv_data.decode("utf-8")
        st.session_state.testcases_excel_data = excel_buffer
        # Log to history
        st.session_state.sync_history.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": "Test Cases Generated",
            "issue_key": st.session_state.get("fetched_jira_issue_key", "N/A"),
            "status": f"✅ Generated {len(df_result)} test cases"
        })

    # --- Generate Test Cases ---
    # If Jira fetch was used, treat the use case as BRD automatically
    if st.session_state.get("fetched_from_jira"):
        use_usecase_as_brd = True
    else:
        use_usecase_as_brd = st.session_state.get("use_usecase_as_brd", False)

    # If fetched and checkbox/flag enabled and a template is present, auto-generate test cases once.
    if use_usecase_as_brd and st.session_state.get("usecase_text") and template_columns and not st.session_state.get("testcases_generated"):
        generate_test_cases(st.session_state.usecase_text, template_columns)

    # When not auto-generating, show the manual Generate Test Cases button (also hidden when fetched-from-jira flow is active)
    if not st.session_state.get("fetched_from_jira"):
        if st.button("🚀 Generate Test Cases"):
            # Determine BRD source: prefer generated BRD, else use manual checkbox/usecase
            if st.session_state.brd_text:
                brd_to_use = st.session_state.brd_text
            elif st.session_state.get("use_usecase_as_brd") and st.session_state.get("usecase_text"):
                brd_to_use = st.session_state.usecase_text
            else:
                st.warning("Please generate the BRD manually first.")
                brd_to_use = None

            if brd_to_use:
                generate_test_cases(brd_to_use, template_columns)

    # --- Attach Test Cases to Jira ---
    if st.session_state.get("testcases_generated") and st.session_state.get("testcases_csv_data"):
        st.divider()
        st.subheader("📎 Attach Test Cases to Jira")
        
        with st.expander("🔗 Attach CSV to Jira Issue"):
            st.write("Attach the generated test cases CSV to the Jira issue.")
            
            # If we fetched from Jira, pre-fill the issue key
            jira_url_attach = st.text_input("Jira Base URL", value=JIRA_BASE_URL, key="jira_url_attach")
            jira_email_attach = st.text_input("Jira Email",value=JIRA_EMAIL, key="jira_email_attach")
            jira_api_token_attach = st.text_input("Jira API Token", type="password",value=JIRA_API_TOKEN, key="jira_api_token_attach")
            jira_issue_key_attach = st.text_input(
                "Jira Issue Key", 
                value=st.session_state.get("fetched_jira_issue_key", ""),
                key="jira_issue_key_attach"
            )
            
            if st.button("📤 Attach CSV to Jira"):
                if not (jira_url_attach and jira_email_attach and jira_api_token_attach and jira_issue_key_attach):
                    st.warning("Please provide all Jira details.")
                else:
                    success = attach_csv_to_jira(
                        jira_url_attach,
                        jira_email_attach,
                        jira_api_token_attach,
                        jira_issue_key_attach,
                        st.session_state.testcases_csv_data
                    )
                    if success:
                        st.session_state.sync_history.append({
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "action": "CSV Attached to Jira",
                            "issue_key": jira_issue_key_attach,
                            "status": "✅ Success"
                        })
                        st.success(f"✅ Test cases CSV successfully attached to {jira_issue_key_attach}!")
                    else:
                        st.session_state.sync_history.append({
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "action": "CSV Attached to Jira",
                            "issue_key": jira_issue_key_attach,
                            "status": "❌ Failed"
                        })
        
        with st.expander("🔗 Attach Excel to Jira Issue"):
            st.write("Attach the generated test cases Excel to the Jira issue.")
            
            jira_url_attach_excel = st.text_input("Jira Base URL", value=JIRA_BASE_URL, key="jira_url_attach_excel")
            jira_email_attach_excel = st.text_input("Jira Email", key="jira_email_attach_excel")
            jira_api_token_attach_excel = st.text_input("Jira API Token", type="password", key="jira_api_token_attach_excel")
            jira_issue_key_attach_excel = st.text_input(
                "Jira Issue Key", 
                value=st.session_state.get("fetched_jira_issue_key", ""),
                key="jira_issue_key_attach_excel"
            )
            
            if st.button("📤 Attach Excel to Jira"):
                if not (jira_url_attach_excel and jira_email_attach_excel and jira_api_token_attach_excel and jira_issue_key_attach_excel):
                    st.warning("Please provide all Jira details.")
                else:
                    success = attach_excel_to_jira(
                        jira_url_attach_excel,
                        jira_email_attach_excel,
                        jira_api_token_attach_excel,
                        jira_issue_key_attach_excel,
                        st.session_state.testcases_excel_data
                    )
                    if success:
                        st.session_state.sync_history.append({
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "action": "Excel Attached to Jira",
                            "issue_key": jira_issue_key_attach_excel,
                            "status": "✅ Success"
                        })
                        st.success(f"✅ Test cases Excel successfully attached to {jira_issue_key_attach_excel}!")
                    else:
                        st.session_state.sync_history.append({
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "action": "Excel Attached to Jira",
                            "issue_key": jira_issue_key_attach_excel,
                            "status": "❌ Failed"
                        })

    # --- Session History Display ---
    if st.session_state.sync_history:
        st.divider()
        st.subheader("📜 Session Activity History")
        
        with st.expander("View Sync History"):
            history_df = pd.DataFrame(st.session_state.sync_history)
            st.dataframe(history_df, use_container_width=True, hide_index=True)
            
            # Add option to clear history
            if st.button("🗑️ Clear History"):
                st.session_state.sync_history = []
                st.rerun()
