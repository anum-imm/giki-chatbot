# create_index.py
import os
from dotenv import load_dotenv
from pinecone import Pinecone

# 1️⃣ Load env vars
load_dotenv()
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

# 2️⃣ Initialize Pinecone client
pc = Pinecone(api_key=PINECONE_API_KEY)

# 3️⃣ Index configuration
index_name = "giki-content"

# 4️⃣ Create index if it doesn't exist
if not pc.has_index(index_name):
    pc.create_index_for_model(
        name=index_name,
        cloud="aws",            # choose "aws" or "gcp"
        region="us-east-1",     # region for the index
        embed={
            "model": "llama-text-embed-v2",      # integrated embedding model
            "field_map": {"text": "chunk_text"}  # maps your text field to embedding
        }
    )
    print(f"✅ Created index '{index_name}' successfully!")
else:
    print(f"Index '{index_name}' already exists!")
