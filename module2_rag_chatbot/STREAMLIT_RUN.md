Streamlit Frontend — Run Instructions

This file describes how to run the Streamlit frontend added at `src/streamlit_app.py`.

Prerequisites
- Python 3.10+ recommended
- A virtual environment (optional but recommended)
- A valid `GROQ_API_KEY` in the project `.env` (to enable real LLM responses). If
  you don't set an API key, the app will run in offline mock mode.

Steps (PowerShell):

```powershell
# 1) Activate virtual environment (adjust path if you use a different venv)
.\.venv\Scripts\Activate.ps1

# 2) Install dependencies
pip install -r requirements.txt

# 3) Run the Streamlit app
streamlit run src/streamlit_app.py
```

Optional: Rebuild the Chroma DB from your dataset:

```powershell
python src/ingest.py
```

Notes
- The Streamlit app contains an offline fallback so you can test the UI without
  contacting the Groq API. To enable full functionality, add `GROQ_API_KEY` to
  the `.env` file in the project root.
- If you want me to run a local smoke-test here (install & start the app), tell
  me and I'll attempt it (I will show the exact commands and any errors).
