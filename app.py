import streamlit as st
import pdfplumber
import pandas as pd
import io
import zipfile


st.set_page_config(
    page_title="PDF Table Extractor",
    page_icon="📄",
    layout="wide"
)

st.title("📄 PDF Table Extractor")
st.write("Upload a PDF, extract its tables, and download them as CSV files.")

def extract_tables_from_pdf(pdf_file):
    """
    Extract all tables from a PDF.

    Returns:
        List of dictionaries containing:
        - page number
        - table number
        - dataframe
    """

    tables = []

    with pdfplumber.open(pdf_file) as pdf:

        for page_number, page in enumerate(pdf.pages, start=1):

            page_tables = page.extract_tables()

            for table_number, table in enumerate(page_tables, start=1):

                if not table:
                    continue

                # Convert table to DataFrame
                df = pd.DataFrame(table)

                # Remove completely empty rows/columns
                df = df.dropna(how="all")
                df = df.dropna(axis=1, how="all")

                if df.empty:
                    continue

                tables.append({
                    "page": page_number,
                    "table": table_number,
                    "data": df
                })

    return tables


# --------------------------------------------------
# FILE UPLOAD
# --------------------------------------------------

uploaded_file = st.file_uploader(
    "Upload a PDF",
    type=["pdf"]
)


if uploaded_file:

    st.success(f"Uploaded: {uploaded_file.name}")

    if st.button("🔍 Extract Tables"):

        with st.spinner("Extracting tables..."):

            try:

                tables = extract_tables_from_pdf(uploaded_file)

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


# --------------------------------------------------
# DISPLAY RESULTS
# --------------------------------------------------

if "tables" in st.session_state:

    tables = st.session_state["tables"]

    st.subheader("Extracted Tables")

    for i, table_info in enumerate(tables):

        page = table_info["page"]
        table_number = table_info["table"]
        df = table_info["data"]

        st.markdown(
            f"### Table {i + 1} — Page {page}"
        )

        st.dataframe(
            df,
            use_container_width=True
        )

        # Convert dataframe to CSV
        csv_data = df.to_csv(
            index=False,
            header=False
        ).encode("utf-8")

        st.download_button(
            label=f"⬇️ Download Table {i + 1} CSV",
            data=csv_data,
            file_name=f"table_page_{page}_{table_number}.csv",
            mime="text/csv",
            key=f"download_{i}"
        )

        st.divider()


# --------------------------------------------------
# DOWNLOAD ALL TABLES AS ZIP
# --------------------------------------------------

if "tables" in st.session_state and st.session_state["tables"]:

    st.subheader("Download All Tables")

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(
        zip_buffer,
        "w",
        zipfile.ZIP_DEFLATED
    ) as zip_file:

        for i, table_info in enumerate(
            st.session_state["tables"]
        ):

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