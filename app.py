import streamlit as st
import pdfplumber
import pandas as pd
import io
import zipfile


# ============================================================
# PAGE SETUP
# ============================================================

st.set_page_config(
    page_title="TableFlow",
    page_icon="📄",
    layout="wide"
)


# ============================================================
# SIMPLE STYLING
# ============================================================

st.markdown(
    """
    <style>

    .main {
        background-color: #f8f9fa;
    }

    .title {
        font-size: 38px;
        font-weight: 700;
        color: #1f2937;
        margin-bottom: 5px;
    }

    .subtitle {
        font-size: 17px;
        color: #6b7280;
        margin-bottom: 30px;
    }

    .step-number {
        font-size: 28px;
        font-weight: 700;
        color: #2563eb;
    }

    .step-title {
        font-size: 18px;
        font-weight: 600;
        color: #1f2937;
    }

    .step-text {
        font-size: 14px;
        color: #6b7280;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="title">📄 TableFlow</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Extract tables from PDF files and convert them to CSV.'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# HOW IT WORKS
# ============================================================

st.subheader("How it works")

step1, step2, step3 = st.columns(3)

with step1:

    st.markdown(
        '<div class="step-number">1</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="step-title">Upload</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="step-text">'
        'Upload a PDF containing tables.'
        '</div>',
        unsafe_allow_html=True
    )


with step2:

    st.markdown(
        '<div class="step-number">2</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="step-title">Extract</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="step-text">'
        'Automatically find and extract the tables.'
        '</div>',
        unsafe_allow_html=True
    )


with step3:

    st.markdown(
        '<div class="step-number">3</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="step-title">Download</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="step-text">'
        'Download your tables as CSV files.'
        '</div>',
        unsafe_allow_html=True
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
            start=1
        ):

            page_tables = page.extract_tables()

            for table_number, table in enumerate(
                page_tables,
                start=1
            ):

                if not table:
                    continue

                # Convert table to DataFrame
                df = pd.DataFrame(table)

                # Remove completely empty rows
                df = df.dropna(how="all")

                # Remove completely empty columns
                df = df.dropna(
                    axis=1,
                    how="all"
                )

                if df.empty:
                    continue

                tables.append(
                    {
                        "page": page_number,
                        "table": table_number,
                        "data": df
                    }
                )

    return tables


# ============================================================
# FILE UPLOAD
# ============================================================

st.subheader("Upload a PDF")

uploaded_file = st.file_uploader(
    "Choose a PDF file",
    type=["pdf"]
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
        type="primary"
    ):

        with st.spinner(
            "Extracting tables..."
        ):

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

            except Exception as e:

                st.error(
                    f"An error occurred while processing the PDF: {e}"
                )


# ============================================================
# DISPLAY RESULTS
# ============================================================

if "tables" in st.session_state:

    tables = st.session_state["tables"]

    st.subheader("Extracted Tables")

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Tables",
            len(tables)
        )

    with col2:

        total_rows = sum(
            len(table["data"])
            for table in tables
        )

        st.metric(
            "Total Rows",
            total_rows
        )

    with col3:

        total_pages = len(
            set(
                table["page"]
                for table in tables
            )
        )

        st.metric(
            "Pages With Tables",
            total_pages
        )


    st.divider()


    # --------------------------------------------------------
    # INDIVIDUAL TABLES
    # --------------------------------------------------------

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
            use_container_width=True
        )


        # Convert DataFrame to CSV
        csv_data = df.to_csv(
            index=False,
            header=False
        ).encode("utf-8")


        st.download_button(
            label=f"⬇️ Download Table {i + 1} CSV",
            data=csv_data,
            file_name=(
                f"table_page_{page}_{table_number}.csv"
            ),
            mime="text/csv",
            key=f"download_{i}"
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
        zipfile.ZIP_DEFLATED
    ) as zip_file:

        for i, table_info in enumerate(tables):

            df = table_info["data"]

            page = table_info["page"]

            table_number = table_info["table"]


            csv_data = df.to_csv(
                index=False,
                header=False
            )


            filename = (
                f"table_page_{page}_{table_number}.csv"
            )


            zip_file.writestr(
                filename,
                csv_data
            )


    zip_buffer.seek(0)


    st.download_button(
        label="📦 Download All Tables as ZIP",
        data=zip_buffer,
        file_name="extracted_tables.zip",
        mime="application/zip"
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "PDF Table Extractor • Convert PDF tables to CSV"
)
