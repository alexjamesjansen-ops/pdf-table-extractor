
import os
import io
import zipfile
import traceback

import streamlit as st
import pdfplumber
import pandas as pd
import stripe
from supabase import create_client


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="TabXtract",
    page_icon="🔭",
    layout="wide",
)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Supabase configuration is missing. Check your Render environment variables.")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


# --------------------------------------------------
# STYLING
# --------------------------------------------------

st.markdown(
    """
    <style>
    .main {
        background-color: #f8f9fa;
    }

    .block-container {
        max-width: 1100px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    .tabx-title {
        font-size: 2.7rem;
        font-weight: 750;
        color: #16324f;
        margin-bottom: 0.15rem;
    }

    .tabx-subtitle {
        font-size: 1.1rem;
        color: #526477;
        margin-bottom: 1.5rem;
    }

    .step-number {
        color: #1976d2;
        font-weight: 750;
    }

    div[data-testid="stFileUploader"] {
        background-color: white;
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

if "user" not in st.session_state:
    st.session_state["user"] = None

if "auth_mode" not in st.session_state:
    st.session_state["auth_mode"] = "Log in"


def set_user_from_response(response):
    """Save the authenticated user in Streamlit session state."""
    user = getattr(response, "user", None)

    if user is not None:
        st.session_state["user"] = {
            "id": user.id,
            "email": user.email,
        }


def restore_session():
    """Restore an existing Supabase session when available."""
    if st.session_state["user"] is not None:
        return

    try:
        response = supabase.auth.get_session()
        session = getattr(response, "session", None)

        if session is not None and session.user is not None:
            st.session_state["user"] = {
                "id": session.user.id,
                "email": session.user.email,
            }
    except Exception:
        # A missing session simply means the user needs to log in.
        pass


# --------------------------------------------------
# STRIPE CHECKOUT
# --------------------------------------------------

def create_checkout_session(user_id, user_email):
    """Create a Stripe subscription checkout with a 7-day trial."""
    if not STRIPE_SECRET_KEY or not STRIPE_PRICE_ID:
        raise ValueError(
            "Stripe is not configured. Check STRIPE_SECRET_KEY "
            "and STRIPE_PRICE_ID in Render."
        )

    session = stripe.checkout.Session.create(
        mode="subscription",
        payment_method_collection="always",
        line_items=[
            {
                "price": STRIPE_PRICE_ID,
                "quantity": 1,
            }
        ],
        customer_email=user_email,
        client_reference_id=user_id,
        subscription_data={
            "trial_period_days": 7,
            "metadata": {
                "supabase_user_id": user_id,
            },
        },
        success_url="https://tabxtract.com/?checkout=success",
        cancel_url="https://tabxtract.com/?checkout=cancelled",
    )

    return session.url


# --------------------------------------------------
# PDF EXTRACTION
# --------------------------------------------------

def extract_tables_from_pdf(pdf_file):
    """Extract tables from each page of an uploaded PDF."""
    extracted_tables = []

    with pdfplumber.open(pdf_file) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()

            for table_number, table in enumerate(tables, start=1):
                if not table:
                    continue

                dataframe = pd.DataFrame(table)

                # Remove completely empty rows and columns.
                dataframe = dataframe.dropna(how="all")
                dataframe = dataframe.dropna(axis=1, how="all")

                # Remove rows and columns containing only blank strings.
                dataframe = dataframe.replace(r"^\s*$", pd.NA, regex=True)
                dataframe = dataframe.dropna(how="all")
                dataframe = dataframe.dropna(axis=1, how="all")

                if dataframe.empty:
                    continue

                extracted_tables.append(
                    {
                        "page": page_number,
                        "table": table_number,
                        "dataframe": dataframe,
                    }
                )

    return extracted_tables


def make_csv_bytes(dataframe):
    """Convert a dataframe to downloadable UTF-8 CSV bytes."""
    return dataframe.to_csv(index=False).encode("utf-8-sig")


# --------------------------------------------------
# LOGIN AND SIGNUP
# --------------------------------------------------

restore_session()

if st.session_state["user"] is None:
    st.markdown(
        '<div class="tabx-title">🔭 TabXtract</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="tabx-subtitle">'
        "Extract tables from PDFs and turn them into downloadable CSV files."
        "</div>",
        unsafe_allow_html=True,
    )

    st.divider()

    st.subheader("Welcome to TabXtract")

    auth_mode = st.radio(
        "Choose an option",
        ["Log in", "Create account"],
        horizontal=True,
    )

    with st.form("auth_form"):
        email = st.text_input("Email address")
        password = st.text_input("Password", type="password")

        submit = st.form_submit_button(
            "Log in" if auth_mode == "Log in" else "Create account",
            use_container_width=True,
        )

    if submit:
        if not email.strip() or not password:
            st.error("Enter your email address and password.")
        else:
            try:
                if auth_mode == "Log in":
                    response = supabase.auth.sign_in_with_password(
                        {
                            "email": email.strip(),
                            "password": password,
                        }
                    )

                    set_user_from_response(response)

                    if st.session_state["user"] is not None:
                        st.success("Logged in successfully.")
                        st.rerun()
                    else:
                        st.error("Login did not return a user. Please try again.")

                else:
                    response = supabase.auth.sign_up(
                        {
                            "email": email.strip(),
                            "password": password,
                        }
                    )

                    user = getattr(response, "user", None)
                    session = getattr(response, "session", None)

                    if user is not None and session is not None:
                        st.session_state["user"] = {
                            "id": user.id,
                            "email": user.email,
                        }
                        st.success("Account created successfully.")
                        st.rerun()
                    elif user is not None:
                        st.success(
                            "Account created. Check your email for a "
                            "confirmation link, then log in."
                        )
                    else:
                        st.error("Account creation did not complete. Try again.")

            except Exception:
                st.error(
                    "We couldn't complete that request. Check your details "
                    "and try again. If the problem continues, check your "
                    "Supabase authentication settings."
                )

    st.stop()


# --------------------------------------------------
# LOGGED-IN APPLICATION
# --------------------------------------------------

user = st.session_state["user"]

with st.sidebar:
    st.markdown("### 🔭 TabXtract")
    st.caption(f"Logged in as {user['email']}")

    st.divider()

    st.markdown("### Subscription")
    st.write("7-day free trial, then $10/month.")

    if st.button("Start free trial", use_container_width=True):
        try:
            checkout_url = create_checkout_session(
                user_id=user["id"],
                user_email=user["email"],
            )
            st.markdown(
                f"[Continue to secure Stripe checkout]({checkout_url})"
            )
        except Exception:
            st.error(
                "We couldn't start checkout. Please try again. "
                "If the problem continues, check the Stripe configuration "
                "in Render."
            )

    st.caption(
        "Checkout is being tested. Subscription access restrictions "
        "have not been enabled yet."
    )

    st.divider()

    if st.button("Log out", use_container_width=True):
        try:
            supabase.auth.sign_out()
        except Exception:
            pass

        st.session_state["user"] = None
        st.rerun()


# Show checkout return messages.
checkout_status = st.query_params.get("checkout")

if checkout_status == "success":
    st.success(
        "Stripe checkout completed. Subscription activation may take "
        "a short time while the webhook updates your account."
    )
elif checkout_status == "cancelled":
    st.info("Checkout was cancelled. You can try again whenever you're ready.")


st.markdown(
    '<div class="tabx-title">🔭 TabXtract</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="tabx-subtitle">'
    "Upload a PDF, extract its tables, and download them as CSV files."
    "</div>",
    unsafe_allow_html=True,
)

st.divider()

# Three-step instructions.
step1, step2, step3 = st.columns(3)

with step1:
    st.markdown(
        '<span class="step-number">STEP 1</span>',
        unsafe_allow_html=True,
    )
    st.markdown("**Upload your PDF**")
    st.caption("Choose a PDF that contains tables.")

with step2:
    st.markdown(
        '<span class="step-number">STEP 2</span>',
        unsafe_allow_html=True,
    )
    st.markdown("**Extract the tables**")
    st.caption("TabXtract identifies tables on each page.")

with step3:
    st.markdown(
        '<span class="step-number">STEP 3</span>',
        unsafe_allow_html=True,
    )
    st.markdown("**Download your CSV files**")
    st.caption("Download individual tables or a ZIP archive.")

st.divider()

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

if uploaded_file is not None:
    if st.button("Extract tables", type="primary", use_container_width=True):
        try:
            with st.spinner("Extracting tables from your PDF..."):
                tables = extract_tables_from_pdf(uploaded_file)

            st.session_state["extracted_tables"] = tables
            st.session_state["source_pdf_name"] = uploaded_file.name

        except Exception:
            st.error(
                "We couldn't read this PDF. Try another PDF file."
            )
            st.code(traceback.format_exc())

    if "extracted_tables" in st.session_state:
        tables = st.session_state["extracted_tables"]

        if not tables:
            st.warning(
                "No tables were detected. Try a PDF with clearer table borders "
                "or selectable text."
            )
        else:
            st.success(f"Found {len(tables)} table(s).")

            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(
                zip_buffer,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
            ) as zip_file:
                for index, item in enumerate(tables, start=1):
                    csv_data = make_csv_bytes(item["dataframe"])

                    filename = (
                        f"page_{item['page']}_table_{item['table']}.csv"
                    )

                    st.markdown(
                        f"**Table {index} — Page {item['page']}**"
                    )

                    st.dataframe(
                        item["dataframe"],
                        use_container_width=True,
                    )

                    st.download_button(
                        label=f"Download Table {index} as CSV",
                        data=csv_data,
                        file_name=filename,
                        mime="text/csv",
                        key=f"csv_download_{index}",
                    )

                    zip_file.writestr(filename, csv_data)

            st.divider()

            st.download_button(
                label="Download all tables as ZIP",
                data=zip_buffer.getvalue(),
                file_name="tabxtract_tables.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True,
            )
