# RAG Chatbot (ChromaDB + Groq + CSV/Excel)

This is a small Retrieval-Augmented Generation (RAG) chatbot for a TA/LD
recruitment-style system. It uses:

- Groq LLM (`llama-3.3-70b-versatile`)
- ChromaDB as a local vector database
- Sentence-Transformers embeddings
- A CSV or Excel dataset as knowledge source

---

## Setup (Ubuntu 24.04)

### 1. Clone / create project

```bash
cd ~/Desktop
mkdir rag_chatbot && cd rag_chatbot

