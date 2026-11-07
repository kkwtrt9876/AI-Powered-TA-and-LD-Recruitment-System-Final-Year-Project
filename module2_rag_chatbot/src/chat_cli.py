from .rag import answer_question


def main():
    print("RAG Chatbot (ChromaDB + Groq + CSV/Excel) – type 'exit' to quit.\n")
    while True:
        user_input = input("Student: ").strip()
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        try:
            reply = answer_question(user_input)
        except Exception as e:
            reply = f"Error while answering: {e}"

        print(f"Bot   : {reply}\n")


if __name__ == "__main__":
    main()

