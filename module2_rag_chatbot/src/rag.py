from typing import List

import chromadb

from .config import CHROMA_DIR, CHROMA_COLLECTION, groq_client, GROQ_MODEL


def get_collection():
    """
    Connect to the persistent Chroma collection.
    We rely on the default embedding function used at ingest time.
    """
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_collection(name=CHROMA_COLLECTION)
    return collection


def retrieve_context(query: str, k: int = 5) -> List[str]:
    """
    Query Chroma with the user question and return top-k document texts.
    """
    collection = get_collection()
    result = collection.query(
        query_texts=[query],
        n_results=k,
    )
    docs = result.get("documents", [[]])[0]
    return docs


def build_prompt(context_chunks: List[str], question: str) -> str:
    """
    Build a prompt that makes the LLM answer professionally and only
    use the provided context.
    """
    context_text = "\n\n---\n\n".join(context_chunks) if context_chunks else "No relevant data."

    return (
        "You are an academic assistant for a Teaching Assistant / Lab Demonstrator (TA/LD) "
        "recruitment system. Your job is to answer students' questions in a clear, polite, "
        "and professional way.\n\n"
        "You are given a set of context passages retrieved from the official system/database. "
        "Use them as the ONLY source of truth.\n\n"
        "Instructions:\n"
        "1. First, understand the student's question.\n"
        "2. Carefully read the context and extract any information that is relevant.\n"
        "3. If the context contains relevant information, answer in a professional, student-friendly tone.\n"
        "   - Be concise but complete.\n"
        "   - Use bullet points or numbered steps if the answer has multiple conditions or steps.\n"
        "   - Use simple, formal English.\n"
        "4. If the context clearly does NOT contain the answer, say that you do not know based on the available data.\n"
        "   - You may say: \"Based on the available information, this is not specified.\" "
        "and, if helpful, suggest the student contact the department/administrator.\n"
        "5. Do NOT invent or guess policies, dates, or eligibility rules that are not explicitly supported by the context.\n\n"
        f"Context:\n{context_text}\n\n"
        f"Student's question: {question}\n\n"
        "Now provide a professional answer for the student."
    )


def ask_llm(prompt: str) -> str:
    """
    Call the Groq LLM with a system message enforcing professional style
    and no hallucinations beyond the given context.
    """
    chat_completion = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a professional academic assistant helping students with "
                    "questions about TA/LD recruitment. "
                    "Always answer politely, clearly, and concisely. "
                    "Use only the information provided in the context. "
                    "Do not invent information that is not supported by the given context."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
    )
    return chat_completion.choices[0].message.content.strip()


def answer_question(question: str, k: int = 5) -> str:
    """
    Main RAG entry point: retrieve context, build prompt, and ask the LLM.
    """
    context_chunks = retrieve_context(question, k=k)
    prompt = build_prompt(context_chunks, question)
    return ask_llm(prompt)

