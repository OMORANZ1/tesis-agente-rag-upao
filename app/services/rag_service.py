import os

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_mistralai import MistralAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

try:
    from ..config import CHROMA_PATH, SILABO_PATH
except ImportError:
    from config import CHROMA_PATH, SILABO_PATH


def crear_embeddings():
    return MistralAIEmbeddings(
        api_key=os.getenv("MISTRAL_API_KEY"),
        model="mistral-embed",
    )


def cargar_silabo():
    print("Cargando silabo...")
    loader = PyPDFLoader(str(SILABO_PATH))
    documentos = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(documentos)
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=crear_embeddings(),
        persist_directory=str(CHROMA_PATH),
    )
    print(f"Silabo cargado: {len(chunks)} fragmentos indexados.")
    return vectorstore


def cargar_vectorstore_existente():
    return Chroma(
        persist_directory=str(CHROMA_PATH),
        embedding_function=crear_embeddings(),
    )


def crear_retriever():
    if CHROMA_PATH.exists():
        vectorstore = cargar_vectorstore_existente()
    else:
        vectorstore = cargar_silabo()

    return vectorstore.as_retriever(search_kwargs={"k": 3})
