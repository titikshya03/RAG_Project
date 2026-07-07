import os
import uuid
import streamlit as st
from pypdf import PdfReader
from openai import AzureOpenAI
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField
)
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

# ==========================
# CONFIG
# ==========================

load_dotenv()

search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
search_key = os.getenv("AZURE_SEARCH_KEY")
index_name = os.getenv("AZURE_SEARCH_INDEX")

openai_client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION")
)

# ==========================
# PAGE CONFIG
# ==========================

st.set_page_config(
    page_title="TwoDocs Challenge",
    page_icon="📚",
    layout="wide"
)

# ==========================
# CUSTOM CSS
# ==========================

st.markdown("""
<style>
.main {
    padding-top: 1rem;
}

.title {
    text-align:center;
    font-size:42px;
    font-weight:bold;
    color:#4F46E5;
}

.subtitle {
    text-align:center;
    color:gray;
    margin-bottom:25px;
}

.stButton>button {
    width:100%;
    border-radius:10px;
    height:50px;
    font-size:18px;
}

.answer-box {
    background:#f5f7ff;
    padding:15px;
    border-radius:10px;
}
</style>
""", unsafe_allow_html=True)

# ==========================
# CREATE INDEX
# ==========================

def create_index():

    index_client = SearchIndexClient(
        endpoint=search_endpoint,
        credential=AzureKeyCredential(search_key)
    )

    fields = [
        SimpleField(
            name="id",
            type="Edm.String",
            key=True
        ),
        SearchableField(
            name="content",
            type="Edm.String"
        ),
        SearchableField(
            name="source",
            type="Edm.String"
        )
    ]

    index = SearchIndex(
        name=index_name,
        fields=fields
    )

    try:
        index_client.create_or_update_index(index)
    except:
        pass


if "index_created" not in st.session_state:
    create_index()
    st.session_state.index_created = True

# ==========================
# TITLE
# ==========================

st.markdown(
    "<div class='title'>📚 TwoDocs Challenge</div>",
    unsafe_allow_html=True
)

st.markdown(
    "<div class='subtitle'>Upload two PDFs and ask questions from both documents</div>",
    unsafe_allow_html=True
)

# ==========================
# FILE UPLOAD
# ==========================

uploaded_files = st.file_uploader(
    "Upload up to 2 PDF files",
    type="pdf",
    accept_multiple_files=True
)

if uploaded_files:

    if len(uploaded_files) > 2:
        st.error("Please upload only 2 PDFs.")
        st.stop()

    search_client = SearchClient(
        endpoint=search_endpoint,
        index_name=index_name,
        credential=AzureKeyCredential(search_key)
    )

    total_chunks = 0

    with st.spinner("Indexing documents..."):

        for pdf in uploaded_files:

            reader = PdfReader(pdf)

            text = ""

            for page in reader.pages:
                text += page.extract_text() or ""

            chunks = [
                text[i:i+1000]
                for i in range(0, len(text), 1000)
            ]

            docs = []

            for chunk in chunks:

                docs.append({
                    "id": str(uuid.uuid4()),
                    "content": chunk,
                    "source": pdf.name
                })

            search_client.upload_documents(docs)

            total_chunks += len(chunks)

    st.success(
        f"✅ Indexed {len(uploaded_files)} PDFs ({total_chunks} chunks)"
    )

    st.divider()

    # ==========================
    # QUESTION SECTION
    # ==========================

    st.subheader("💬 Ask a Question")

    question = st.text_input(
        "Enter your question"
    )

    if st.button("Get Answer"):

        with st.spinner("Searching documents..."):

            results = search_client.search(
                search_text=question,
                top=5
            )

            contexts = []
            sources = set()

            for r in results:
                contexts.append(r["content"])
                sources.add(r["source"])

            context = "\n".join(contexts)

            response = openai_client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
                messages=[
                    {
                        "role": "system",
                        "content":
                        f"""
                        Use ONLY the information below.

                        {context}

                        If the answer is not found,
                        say 'Information not found in uploaded documents.'
                        """
                    },
                    {
                        "role": "user",
                        "content": question
                    }
                ],
                max_tokens=300
            )

            answer = response.choices[0].message.content

            st.markdown("### ✅ Answer")

            st.success(answer)

            st.markdown("### 📄 Source Document(s)")

            for source in sources:
                st.info(source)