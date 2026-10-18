import streamlit as st
import pdfplumber
import pandas as pd
import io
import zipfile
import os
import stripe
import traceback

from supabase import create_client
from datetime import datetime, timezone


# ============================================================
# PAGE SETUP
# ============================================================

st.set_page_config(
    page_title="TabXtract",
    page_icon="🔭",
    layout="wide",
)


# ============================================================
# STRIPE CONFIGURATION
# ============================================================

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")


# ============================================================
# SUPABASE CONFIGURATION
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY"
)

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error(
        "Account services are not configured. "
        "Please try again later."
    )
    st.stop()

if not SUPABASE_SERVICE_ROLE_KEY:
    st.error(
        "Subscription services are not configured. "
        "Please try again later."
    )
    st.stop()

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
)

supabase_admin = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_field(obj, name, default=None):
    """Safely read a field from a Stripe response."""
    if obj is None:
        return default

    try:
        value = obj.get(name, default)
    except (AttributeError, TypeError):
        value = getattr(obj, name, default)

    return default if value is None else value


def stripe_date(timestamp):
    """Convert a Stripe timestamp to a UTC date string."""
    if not timestamp:
        return None

    return datetime.fromtimestamp(
        timestamp,
        timezone.utc,
    ).isoformat()


def log_error(context):
    """Write diagnostic information to Render logs."""
    print(f"TabXtract {context} traceback:")
    traceback.print_exc()


# ============================================================
# USER SIGN-UP AND LOGIN
# ============================================================

if "supabase_access_token" not in st.session_state:
    st.session_state["supabase_access_token"] = None
    st.session_state["supabase_refresh_token"] = None
    st.session_state["supabase_user"] = None


# Restore the user's Supabase session.
if (
    st.session_state["supabase_access_token"]
    and st.session_state["supabase_refresh_token"]
):
    try:
        auth_response = supabase.auth.set_session(
            st.session_state["supabase_access_token"],
            st.session_state["supabase_refresh_token"],
        )

        if auth_response.session:
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
        st.session_state["supabase_access_token"] = None
        st.session_state["supabase_refresh_token"] = None
        st.session_state["supabase_user"] = None


# Show login and sign-up forms when logged out.
if not st.session_state["supabase_user"]:

    st.title("Welcome to TabXtract")
    st.write("Create an account or log in to continue.")

    signup_tab, login_tab = st.tabs(
        ["Create Account", "Log In"]
    )

    with signup_tab:

        with st.form("signup_form"):

            signup_email = st.text_input("Email address")

            signup_password = st.text_input(
                "Password",
                type="password",
            )

            signup_submit = st.form_submit_button(
                "Create Account",
                use_container_width=True,
            )

        if signup_submit:

            if not signup_email or not signup_password:
                st.error("Enter your email and password.")

            elif len(signup_password) < 8:
                st.error(
                    "Your password must be at least 8 characters."
                )

            else:
                try:
                    response = supabase.auth.sign_up({
                        "email": signup_email,
                        "password": signup_password,
                    })

                    if response.session and response.user:

                        st.session_state["supabase_access_token"] = (
                            response.session.access_token
                        )

                        st.session_state["supabase_refresh_token"] = (
                            response.session.refresh_token
                        )

                        st.session_state["supabase_user"] = {
                            "id": response.user.id,
                            "email": response.user.email,
                        }

                        st.rerun()

                    else:
                        st.success(
                            "Account request received. Check your email "
                            "to verify your account, then log in."
                        )

                except Exception:
                    st.error(
                        "We couldn't create your account. "
                        "Check your details or try logging in."
                    )

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

            try:
                response = supabase.auth.sign_in_with_password({
                    "email": login_email,
                    "password": login_password,
                })

                if response.session and response.user:

                    st.session_state["supabase_access_token"] = (
                        response.session.access_token
                    )

                    st.session_state["supabase_refresh_token"] = (
                        response.session.refresh_token
                    )

                    st.session_state["supabase_user"] = {
                        "id": response.user.id,
                        "email": response.user.email,
                    }

                    st.rerun()

                else:
                    st.error("Login failed. Please try again.")

            except Exception:
                st.error(
                    "Login failed. Check your email and password, "
                    "and verify your email if required."
                )

    st.stop()


# Signed-in user's account controls.
current_user = st.session_state["supabase_user"]

st.sidebar.caption(
    f"Logged in as: {current_user['email']}"
)

if st.sidebar.button("Log Out"):

    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    st.session_state["supabase_access_token"] = None
    st.session_state["supabase_refresh_token"] = None
    st.session_state["supabase_user"] = None

    st.rerun()


# ============================================================
# VERIFY STRIPE CHECKOUT AND SAVE SUBSCRIPTION
# ============================================================

checkout_session_id = st.query_params.get("session_id")

if checkout_session_id:

    try:
        # Retrieve the checkout session from Stripe.
        checkout = stripe.checkout.Session.retrieve(
            checkout_session_id
        )

        # Confirm this is a completed subscription checkout
        # belonging to the signed-in user.
        if (
            get_field(checkout, "status") != "complete"
            or get_field(checkout, "mode") != "subscription"
            or get_field(checkout, "client_reference_id")
            != current_user["id"]
        ):
            st.error(
                "We couldn't verify this checkout for your account."
            )
            st.stop()

        subscription_value = get_field(
            checkout,
            "subscription",
        )

        if not subscription_value:
            st.error(
                "No subscription was found for this checkout."
            )
            st.stop()

        # Stripe may return a subscription ID or an expanded object.
        if isinstance(subscription_value, str):

            subscription = stripe.Subscription.retrieve(
                subscription_value
            )

        else:
            subscription = subscription_value

        subscription_id = get_field(
            subscription,
            "id",
        )

        # Check the metadata added when checkout was created.
        metadata = get_field(
            subscription,
            "metadata",
            {},
        ) or {}

        if (
            metadata.get("supabase_user_id")
            != current_user["id"]
        ):
            st.error(
                "The subscription could not be matched to your account."
            )
            st.stop()

        # Some fields are optional depending on the Stripe API version.
        # Missing optional date fields should not cause AttributeError.
        trial_end = get_field(
            subscription,
            "trial_end",
        )

        current_period_end = get_field(
            subscription,
            "current_period_end",
        )

        customer_id = get_field(
            checkout,
            "customer",
        )

        if not customer_id:
            customer_id = get_field(
                subscription,
                "customer",
            )

        subscription_record = {
            "user_id": current_user["id"],
            "stripe_customer_id": (
                str(customer_id) if customer_id else None
            ),
            "stripe_subscription_id": str(subscription_id),
            "status": get_field(
                subscription,
                "status",
                "inactive",
            ),
            "trial_end": stripe_date(trial_end),
            "current_period_end": stripe_date(
                current_period_end
            ),
            "updated_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

        # Save the verified subscription to Supabase.
        supabase_admin.table("subscriptions").upsert(
            subscription_record
        ).execute()

        # Only clear the URL after saving succeeds.
        st.query_params.clear()

        st.success(
            "Your subscription has been verified and saved."
        )

    except Exception:
        st.error(
            "Subscription verification failed. "
            "Please refresh the page or contact support."
        )

        log_error("checkout verification")


# ============================================================
# STYLING
# ============================================================

st.markdown(
    """
    <style>
    .main {
        background-color: #f8fafc;
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
# STRIPE CHECKOUT
# ============================================================

st.markdown("### Try TabXtract Pro")

st.write(
    "Start with a 7-day free trial, then $10/month "
    "for unlimited PDF table extraction."
)

if st.button(
    "Start Your 7-Day Free Trial",
    type="primary",
    use_container_width=True,
):

    if not stripe.api_key or not STRIPE_PRICE_ID:

        st.error(
            "Subscription checkout is not configured. "
            "Please try again later."
        )

    else:
        try:
            checkout_session = stripe.checkout.Session.create(
                mode="subscription",
                managed_payments={"enabled": False},
                client_reference_id=current_user["id"],
                customer_email=current_user["email"],
                line_items=[
                    {
                        "price": STRIPE_PRICE_ID,
                        "quantity": 1,
                    }
                ],
                subscription_data={
                    "trial_period_days": 7,
                    "metadata": {
                        "supabase_user_id": current_user["id"],
                    },
                },
                success_url=(
                    "https://tabxtract.com/"
                    "?checkout=success&session_id={CHECKOUT_SESSION_ID}"
                ),
                cancel_url=(
                    "https://tabxtract.com/?checkout=cancelled"
                ),
            )

            st.session_state["stripe_checkout_url"] = (
                checkout_session.url
            )

        except Exception:
            st.error(
                "We couldn't start checkout. Please try again later."
            )

            log_error("checkout creation")


if st.session_state.get("stripe_checkout_url"):

    st.link_button(
        "Continue to Secure Stripe Checkout",
        st.session_state["stripe_checkout_url"],
        use_container_width=True,
    )

st.divider()


# ============================================================
# CHECK SUBSCRIPTION ACCESS
# ============================================================

current_status = "inactive"

try:
    result = (
        supabase_admin.table("subscriptions")
        .select("stripe_subscription_id,status")
        .eq("user_id", current_user["id"])
        .maybe_single()
        .execute()
    )

    subscription_record = result.data

    if subscription_record:

        subscription_id = subscription_record.get(
            "stripe_subscription_id"
        )

        if subscription_id:

            # Ask Stripe for the current subscription status.
            live_subscription = stripe.Subscription.retrieve(
                subscription_id
            )

            current_status = get_field(
                live_subscription,
                "status",
                "inactive",
            )

            # Keep the saved status synchronized with Stripe.
            if current_status != subscription_record.get("status"):

                supabase_admin.table("subscriptions").update({
                    "status": current_status,
                    "updated_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                }).eq(
                    "user_id",
                    current_user["id"],
                ).execute()

except Exception:
    st.error(
        "We couldn't verify your subscription status. "
        "Please refresh the page or try again later."
    )

    log_error("subscription access check")
    st.stop()


if current_status not in ("trialing", "active"):

    st.warning(
        "A subscription is required to use PDF extraction. "
        "Start your 7-day free trial above to continue."
    )

    st.stop()


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
# PDF TABLE EXTRACTION
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
# FILE UPLOAD
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

    st.success(f"Uploaded: {uploaded_file.name}")

    if st.button("🔍 Extract Tables", type="primary"):

        with st.spinner("Extracting tables..."):

            try:
                tables = extract_tables_from_pdf(
                    uploaded_file
                )

                if not tables:

                    st.warning(
                        "No tables were detected in this PDF."
                    )

                else:
                    st.session_state["tables"] = tables

                    st.success(
                        f"Found {len(tables)} table(s)."
                    )

            except Exception:
                st.error(
                    "An error occurred while processing the PDF. "
                    "Please try another file."
                )

                log_error("PDF extraction")


# ============================================================
# DISPLAY RESULTS
# ============================================================

if "tables" in st.session_state:

    tables = st.session_state["tables"]

    st.subheader("Extracted Tables")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Tables", len(tables))

    with col2:
        total_rows = sum(
            len(table["data"])
            for table in tables
        )
        st.metric("Total Rows", total_rows)

    with col3:
        total_pages = len({
            table["page"]
            for table in tables
        })
        st.metric("Pages With Tables", total_pages)

    st.divider()

    for i, table_info in enumerate(tables):

        page = table_info["page"]
        table_number = table_info["table"]
        df = table_info["data"]

        st.markdown(f"### Table {i + 1}")

        st.caption(
            f"Page {page} • Table {table_number}"
        )

        st.dataframe(
            df,
            use_container_width=True,
        )

        csv_data = df.to_csv(
            index=False,
            header=False,
        ).encode("utf-8")

        st.download_button(
            label=f"⬇️ Download Table {i + 1} CSV",
            data=csv_data,
            file_name=f"table_page_{page}_{table_number}.csv",
            mime="text/csv",
            key=f"download_{i}",
        )

        st.divider()

    # ========================================================
    # DOWNLOAD ALL TABLES
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
