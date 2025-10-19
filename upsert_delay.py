# upsert.py (fixed with delay between batches)
import os
import json
import time
from dotenv import load_dotenv
from pinecone import Pinecone

# Load .env
load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = "giki-content"
DELAY_BETWEEN_BATCHES = float(os.getenv("UPSERT_DELAY", "2.5"))  # seconds (adjust as needed)

# Initialize Pinecone
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)
print(f"✅ Connected to Pinecone index: {INDEX_NAME}")

# Load JSON chunks
FILE_PATH = r"C:\Users\pc\Desktop\labs\ailab\mid\data\processed\giki_chunks.json"
with open(FILE_PATH, "r", encoding="utf-8") as f:
    chunks = json.load(f)
print(f"✅ Loaded {len(chunks)} chunks from {FILE_PATH}")

# Prepare records for upsert
upsert_data = []
for chunk in chunks:
    rec = {
        "_id": chunk["id"],
        "chunk_text": chunk["text"],
        "title": str(chunk.get("title", "") or ""),
        "source": str(chunk.get("source", "") or "")
    }
    upsert_data.append(rec)
print(f"✅ Prepared {len(upsert_data)} items for upsert")

# Upsert in batches with delay
batch_size = 50
for i in range(0, len(upsert_data), batch_size):
    batch = upsert_data[i:i + batch_size]
    index.upsert_records(namespace="default", records=batch)
    batch_number = i // batch_size + 1
    print(f"✅ Upserted batch {batch_number} ({len(batch)} items)")
    time.sleep(DELAY_BETWEEN_BATCHES)  # pause to respect token limits

print(f"✅ Successfully upserted all {len(upsert_data)} chunks into Pinecone index '{INDEX_NAME}'")
