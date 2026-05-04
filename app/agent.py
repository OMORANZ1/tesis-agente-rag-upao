import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_mistralai import MistralAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.messages import HumanMessage, AIMessage

from pathlib import Path
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

SILABO_PATH = "../docs/silabo.pdf"
CHROMA_PATH = "../chroma_db"

def cargar_silabo():
    print("Cargando sílabo...")
    loader = PyPDFLoader(SILABO_PATH)
    documentos = loader.load()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )
    chunks = splitter.split_documents(documentos)
    embeddings = MistralAIEmbeddings(
        api_key=os.getenv("MISTRAL_API_KEY"),
        model="mistral-embed"
    )
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_PATH
    )
    print(f"Sílabo cargado: {len(chunks)} fragmentos indexados.")
    return vectorstore

def cargar_vectorstore_existente():
    embeddings = MistralAIEmbeddings(
        api_key=os.getenv("MISTRAL_API_KEY"),
        model="mistral-embed"
    )
    return Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=embeddings
    )

# Historial de conversación en memoria
historial = []

def crear_agente():
    if os.path.exists(CHROMA_PATH):
        vectorstore = cargar_vectorstore_existente()
    else:
        vectorstore = cargar_silabo()

    with open("../prompts/system_prompt.txt", "r", encoding="utf-8") as f:
        system_prompt = f.read()

    llm = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="llama-3.1-8b-instant",
        temperature=0.3
    )

    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    def obtener_respuesta(pregunta):
        global historial
        docs = retriever.invoke(pregunta)
        contexto = "\n\n".join([d.page_content for d in docs])
        historial_texto = "\n".join([
            f"Estudiante: {m.content}" if isinstance(m, HumanMessage)
            else f"Tutor: {m.content}"
            for m in historial
        ])
        prompt_final = f"""{system_prompt}

Contexto del sílabo:
{contexto}

Historial de conversación:
{historial_texto}

Pregunta del estudiante: {pregunta}

Respuesta:"""
        respuesta = llm.invoke(prompt_final)
        historial.append(HumanMessage(content=pregunta))
        historial.append(AIMessage(content=respuesta.content))
        if len(historial) > 20:
            historial = historial[-20:]
        return respuesta.content

    return obtener_respuesta

def reiniciar_historial():
    global historial
    historial = []