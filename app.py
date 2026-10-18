import streamlit as st
import pdfplumber
import pandas as pd
import io
import zipfile
import os
import traceback
import stripe


from supabase import create_client


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="TabXtract",
    page_icon="🔭",
    layout="wide",
)


# ============================================================
# SUPABASE CONFIGURATION
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error(
        "Account services are not configured. "
        "Please try again later."
    )
    st.stop()

try:
    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_KEY,
    )
except Exception:
    st.error(
        "We couldn't connect to the account service. "
        "Please try again later."
    )
    print("TabXtract Supabase initialization error:")
    traceback.print_exc()
    st.stop()


# ============================================================
# SESSION STATE
# ============================================================

if "supabase_access_token" not in st.session_state:
    st.session_state["supabase_access_token"] = None

if "supabase_refresh_token" not in st.session_state:
    st.session_state["supabase_refresh_token"] = None

if "supabase_user" not in st.session_state:
    st.session_state["supabase_user"] = None

if "tables" not in st.session_state:
    st.session_state["tables"] = []


# ============================================================
# RESTORE LOGIN SESSION
# ============================================================

if (
    st.session_state["supabase_access_token"]
    and st.session_state["supabase_refresh_token"]
):
    try:
        auth_response = supabase.auth.set_session(
            st.session_state["supabase_access_token"],
            st.session_state["supabase_refresh_token"],
        )

        if auth_response and auth_response.session:

            st.session_state["supabase_access_token"] = (
                auth_response.session.access_token
            )

            st.session_state["supabase_refresh_token"] = (
                auth_response.session.refresh_token
            )

            if auth_response.user:
                st.session_state["supabase_user"] = {
                    "id": auth_response.user.id,
                    "email": auth_response.user.email,
                }

    except Exception:
        print("TabXtract session restoration error:")
        traceback.print_exc()

        st.session_state["supabase_access_token"] = None
        st.session_state["supabase_refresh_token"] = None
        st.session_state["supabase_user"] = None


# ============================================================
# SIGN-UP AND LOGIN
# ============================================================

if not st.session_state["supabase_user"]:

    st.title("Welcome to TabXtract")

    st.write(
        "Create an account or log in to extract tables "
        "from your PDF documents."
    )

    signup_tab, login_tab = st.tabs(
        ["Create Account", "Log In"]
    )

    # --------------------------------------------------------
    # SIGN-UP
    # --------------------------------------------------------

    with signup_tab:

        with st.form("signup_form"):

            signup_email = st.text_input(
                "Email address",
                key="signup_email",
            )

            signup_password = st.text_input(
                "Password",
                type="password",
                key="signup_password",
            )

            signup_submit = st.form_submit_button(
                "Create Account",
                use_container_width=True,
            )

        if signup_submit:

            if not signup_email or not signup_password:

                st.error(
                    "Please enter your email and password."
                )

            elif len(signup_password) < 8:

                st.error(
                    "Your password must be at least 8 characters."
                )

            else:
                try:
                    response = supabase.auth.sign_up({
                        "email": signup_email.strip(),
                        "password": signup_password,
                    })

                    if (
                        response
                        and response.session
                        and response.user
                    ):

                        st.session_state[
                            "supabase_access_token"
                        ] = response.session.access_token

                        st.session_state[
                            "supabase_refresh_token"
                        ] = response.session.refresh_token

                        st.session_state["supabase_user"] = {
                            "id": response.user.id,
                            "email": response.user.email,
                        }

                        st.rerun()

                    else:
                        st.success(
                            "Your account request was received. "
                            "Check your email for a confirmation "
                            "link, then log in."
                        )

                except Exception:
                    st.error(
                        "We couldn't create your account. "
                        "Check your details or try logging in."
                    )

                    print("TabXtract sign-up error:")
                    traceback.print_exc()

    # --------------------------------------------------------
    # LOGIN
    # --------------------------------------------------------

    with login_tab:

        with st.form("login_form"):

            login_email = st.text_input(
                "Email address",
                key="login_email",
            )

            login_password = st.text_input(
                "Password",
                type="password",
                key="login_password",
            )

            login_submit = st.form_submit_button(
                "Log In",
                use_container_width=True,
            )

        if login_submit:

            if not login_email or not login_password:

                st.error(
                    "Please enter your email and password."
                )

            else:
                try:
                    response = (
                        supabase.auth.sign_in_with_password({
                            "email": login_email.strip(),
                            "password": login_password,
                        })
                    )

                    if (
                        response
                        and response.session
                        and response.user
                    ):

                        st.session_state[
                            "supabase_access_token"
                        ] = response.session.access_token

                        st.session_state[
                            "supabase_refresh_token"
                        ] = response.session.refresh_token

                        st.session_state["supabase_user"] = {
                            "id": response.user.id,
                            "email": response.user.email,
                        }

                        st.rerun()

                    else:
                        st.error(
                            "Login failed. Please try again."
                        )

                except Exception:
                    st.error(
                        "Login failed. Check your email and "
                        "password, and confirm your email if required."
                    )

                    print("TabXtract login error:")
                    traceback.print_exc()

    st.stop()


# ============================================================
# LOGGED-IN USER
# ============================================================

current_user = st.session_state["supabase_user"]

st.sidebar.caption(
    f"Logged in as: {current_user['email']}"
)

if st.sidebar.button("Log Out"):

    try:
        supabase.auth.sign_out()
    except Exception:
        print("TabXtract logout notice:")
        traceback.print_exc()

    st.session_state["supabase_access_token"] = None
    st.session_state["supabase_refresh_token"] = None
    st.session_state["supabase_user"] = None
    st.session_state["tables"] = []

    st.rerun()


# ============================================================
# STYLING
# ============================================================

st.markdown(
    """
    <style>
    .main {
        background-color: #f8f9fa;
    }

    .block-container {
        padding-top: 2.5rem;
        padding-bottom: 3rem;
        max-width: 1200px;
    }

    .title {
        font-size: 42px;
        font-weight: 750;
        letter-spacing: -1.5px;
        color: #0f172a;
        margin-bottom: 8px;
    }

    .subtitle {
        font-size: 17px;
        line-height: 1.6;
        color: #64748b;
        margin-bottom: 32px;
    }

    .step-number {
        font-size: 28px;
        font-weight: 700;
        color: #2563eb;
    }

    .step-title {
        font-size: 18px;
        font-weight: 650;
        color: #0f172a;
    }

    .step-text {
        font-size: 14px;
        line-height: 1.6;
        color: #64748b;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="title">TabXtract</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">'
    'Extract tables from PDF files and convert them to CSV.'
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# HOW IT WORKS
# ============================================================

st.subheader("How it works")

step1, step2, step3 = st.columns(3)

with step1:

    st.markdown(
        '<div class="step-number">1</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="step-title">Upload</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="step-text">'
        'Upload a PDF containing tables.'
        '</div>',
        unsafe_allow_html=True,
    )

with step2:

    st.markdown(
        '<div class="step-number">2</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="step-title">Extract</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="step-text">'
        'Automatically find and extract the tables.'
        '</div>',
        unsafe_allow_html=True,
    )

with step3:

    st.markdown(
        '<div class="step-number">3</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="step-title">Download</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="step-text">'
        'Download your tables as CSV files.'
        '</div>',
        unsafe_allow_html=True,
    )

st.divider()


# ============================================================
# PDF TABLE EXTRACTION FUNCTION
# ============================================================

def extract_tables_from_pdf(pdf_file):

    tables = []

    with pdfplumber.open(pdf_file) as pdf:

        for page_number, page in enumerate(
            pdf.pages,
            start=1,
        ):

            page_tables = page.extract_tables()

            for table_number, table in enumerate(
                page_tables,
                start=1,
            ):

                if not table:
                    continue

                df = pd.DataFrame(table)

                # Remove completely empty rows and columns.
                df = df.dropna(how="all")
                df = df.dropna(axis=1, how="all")

                if df.empty:
                    continue

                tables.append({
                    "page": page_number,
                    "table": table_number,
                    "data": df,
                })

    return tables


# ============================================================
# UPLOAD PDF
# ============================================================

st.subheader("Start with your PDF")

st.caption(
    "Choose a PDF document containing tables. "
    "TabXtract will extract the detected tables for you to review."
)

uploaded_file = st.file_uploader(
    "Upload your PDF document",
    type=["pdf"],
    help="Select a PDF file from your computer.",
)


# ============================================================
# EXTRACT TABLES
# ============================================================

if uploaded_file:

    st.success(
        f"Uploaded: {uploaded_file.name}"
    )

    if st.button(
        "🔍 Extract Tables",
        type="primary",
    ):

        # Clear previous results before processing a new request.
        st.session_state["tables"] = []

        with st.spinner("Extracting tables..."):

            try:
                tables = extract_tables_from_pdf(
                    uploaded_file
                )

                if not tables:

                    st.warning(
                        "No tables were detected in this PDF. "
                        "Try another document with clearer tables."
                    )

                else:
                    st.session_state["tables"] = tables

                    st.success(
                        f"Successfully extracted "
                        f"{len(tables)} table(s)."
                    )

            except Exception:
                st.error(
                    "An error occurred while processing this PDF. "
                    "Please try another file."
                )

                print("TabXtract PDF extraction error:")
                traceback.print_exc()


# ============================================================
# DISPLAY EXTRACTED TABLES
# ============================================================

if st.session_state["tables"]:

    tables = st.session_state["tables"]

    st.subheader("Extracted Tables")

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Tables",
            len(tables),
        )

    with col2:

        total_rows = sum(
            len(table["data"])
            for table in tables
        )

        st.metric(
            "Total Rows",
            total_rows,
        )

    with col3:

        total_pages = len({
            table["page"]
            for table in tables
        })

        st.metric(
            "Pages With Tables",
            total_pages,
        )

    st.divider()

    for i, table_info in enumerate(tables):

        page = table_info["page"]
        table_number = table_info["table"]
        df = table_info["data"]

        st.markdown(
            f"### Table {i + 1}"
        )

        st.caption(
            f"Page {page} • Table {table_number}"
        )

        st.dataframe(
            df,
            use_container_width=True,
        )

        # Download each table as a CSV.
        csv_data = df.to_csv(
            index=False,
            header=False,
        ).encode("utf-8")

        st.download_button(
            label=f"⬇️ Download Table {i + 1} CSV",
            data=csv_data,
            file_name=(
                f"table_page_{page}_{table_number}.csv"
            ),
            mime="text/csv",
            key=f"download_table_{i}",
        )

        st.divider()

    # ========================================================
    # DOWNLOAD ALL TABLES AS ZIP
    # ========================================================

    st.subheader("Download All Tables")

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(
        zip_buffer,
        "w",
        zipfile.ZIP_DEFLATED,
    ) as zip_file:

        for table_info in tables:

            df = table_info["data"]
            page = table_info["page"]
            table_number = table_info["table"]

            csv_data = df.to_csv(
                index=False,
                header=False,
            )

            filename = (
                f"table_page_{page}_{table_number}.csv"
            )

            zip_file.writestr(
                filename,
                csv_data,
            )

    zip_buffer.seek(0)

    st.download_button(
        label="📦 Download All Tables as ZIP",
        data=zip_buffer,
        file_name="extracted_tables.zip",
        mime="application/zip",
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "TabXtract • Simple, reliable PDF table extraction"
)
