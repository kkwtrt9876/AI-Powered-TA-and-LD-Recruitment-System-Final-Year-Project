from typing import List
import os

import chromadb
import pandas as pd

from .config import DATA_PATH, CHROMA_DIR, CHROMA_COLLECTION


def row_to_text(row: pd.Series) -> str:
    """
    Convert a dataset row into a single text string.
    Works even if we don't know column names in advance.
    """
    parts: List[str] = []
    for col, val in row.items():
        if pd.isna(val):
            continue
        parts.append(f"{col}: {val}")
    return " | ".join(parts)


def load_dataframe(path: os.PathLike) -> pd.DataFrame:
    """
    Load .xlsx / .xls / .csv into a DataFrame.
    """
    suffix = str(path).split(".")[-1].lower()
    if suffix in ("xlsx", "xls"):
        return pd.read_excel(path, engine="openpyxl")
    elif suffix == "csv":
        return pd.read_csv(path)
    else:
        raise ValueError(f"Unsupported file type for {path}. Use .xlsx/.xls or .csv")


def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found at {DATA_PATH}")

    df = load_dataframe(DATA_PATH)

    if df.empty:
        raise ValueError("Dataset is empty – add some rows first.")

    df = df.fillna("")

    texts: List[str] = []
    metadatas: List[dict] = []
    ids: List[str] = []

    for idx, row in df.iterrows():
        text = row_to_text(row)
        if not text.strip():
            continue
        texts.append(text)
        metadatas.append({"row_index": int(idx)})
        ids.append(str(idx))

    # Ensure Chroma dir exists
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    # Use Chroma's DEFAULT embedding (ONNX MiniLM via onnxruntime)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(name=CHROMA_COLLECTION)

    # Clear old data if re-ingesting
    try:
        collection.delete(where={})
    except Exception:
        pass

    collection.add(
        ids=ids,
        documents=texts,
        metadatas=metadatas,
    )

    print(
        f"Ingested {len(texts)} rows into Chroma collection "
        f"'{CHROMA_COLLECTION}' from '{DATA_PATH.name}'."
    )


if __name__ == "__main__":
    main()

