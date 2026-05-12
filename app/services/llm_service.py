import os

from langchain_groq import ChatGroq


def crear_llm(temperature: float = 0.2):
    return ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="llama-3.1-8b-instant",
        temperature=temperature,
    )
