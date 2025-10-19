# # import os
# # from pinecone import Pinecone
# # from dotenv import load_dotenv

# # # 1️⃣ Load API key
# # load_dotenv()
# # api_key = os.getenv("PINECONE_API_KEY")

# # if not api_key:
# #     raise ValueError("❌ PINECONE_API_KEY not found in environment variables.")

# # # 2️⃣ Initialize Pinecone client
# # pc = Pinecone(api_key=api_key)

# # # 3️⃣ Connect to your index
# # index = pc.Index(host="https://giki-content-p9nr3sp.svc.aped-4627-b74a.pinecone.io")

# # # 4️⃣ Perform semantic search using the model attached to your index (e.g., llama-text-embed-v2)
# # query_text = "faculties"

# # results = index.search(
# #     namespace="default",
# #     query={
# #         "inputs": {"text": query_text},  # ✅ New structured format
# #         "top_k": 3                       # Number of results to return
# #     },
# #     fields=["chunk_text", "source"]      # Return these fields
# # )

# # # 5️⃣ Print results
# # for hit in results["result"]["hits"]:
# #     print(f"Score: {hit['_score']:.3f}")
# #     print(f"Chunk: {hit['fields']['chunk_text']}\n")

# # cli_pinecone.py
# import os
# from pinecone import Pinecone
# from dotenv import load_dotenv

# # -----------------------------
# # Load environment variables
# # -----------------------------
# load_dotenv()
# api_key = os.getenv("PINECONE_API_KEY")

# if not api_key:
#     raise ValueError("❌ PINECONE_API_KEY not found in environment variables.")

# # -----------------------------
# # Initialize Pinecone client
# # -----------------------------
# pc = Pinecone(api_key=api_key)
# index = pc.Index(host="https://giki-content-p9nr3sp.svc.aped-4627-b74a.pinecone.io")

# # -----------------------------
# # CLI loop
# # -----------------------------
# print("📌 Pinecone CLI - type 'exit' to quit.\n")

# while True:
#     query_text = input("Ask your question: ").strip()
#     if query_text.lower() in ["exit", "quit"]:
#         break

#     try:
#         results = index.search(
#             namespace="default",
#             query={"inputs": {"text": query_text}, "top_k": 3},  # structured format
#             fields=["chunk_text", "source"]
#         )

#         hits = results.get("result", {}).get("hits", [])
#         if not hits:
#             print("❌ No relevant context found in Pinecone.\n")
#             continue

#         print(f"\n✅ Top {len(hits)} results:")
#         for i, hit in enumerate(hits, 1):
#             score = hit.get("_score", 0.0)
#             chunk = hit.get("fields", {}).get("chunk_text", "")
#             source = hit.get("fields", {}).get("source", "")
#             print(f"[{i}] Score={score:.3f}, Source={source}")
#             print(f"Chunk: {chunk}\n")

#     except Exception as e:
#         print(f"❌ Error querying Pinecone: {e}\n")


# test.py
import os
import re
import textwrap
import requests
from pinecone import Pinecone
from dotenv import load_dotenv

# -----------------------------
# Load environment variables
# -----------------------------
load_dotenv()
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama2-70b-4096")
PINECONE_HOST = "https://giki-content-p9nr3sp.svc.aped-4627-b74a.pinecone.io"
NAMESPACE = "default"
TOP_K = 5
GROQ_API_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

if not PINECONE_API_KEY or not GROQ_API_KEY:
    raise ValueError("Missing Pinecone or Groq API key in environment variables.")

# -----------------------------
# Initialize Pinecone client
# -----------------------------
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(host=PINECONE_HOST)

# -----------------------------
# Helper: retrieve chunks
# -----------------------------
def retrieve_chunks(query_text: str):
    """
    Retrieve top-k chunks from Pinecone using the new structured query format.
    """
    try:
        results = index.search(
            namespace=NAMESPACE,
            query={
                "inputs": {"text": query_text},
                "top_k": TOP_K  # ✅ Pass top_k inside the query dict
            },
            fields=["chunk_text", "source"]  # optional depending on your Pinecone SDK version
        )
        # parse results
        hits = results.get("result", {}).get("hits", [])
        chunks = []
        for hit in hits:
            chunk_text = hit.get("fields", {}).get("chunk_text", "")
            source = hit.get("fields", {}).get("source", "")
            score = hit.get("_score", 0.0)
            chunks.append({"text": chunk_text, "source": source, "score": score})
        return chunks
    except TypeError:
        # fallback if 'fields' is not supported
        results = index.search(
            namespace=NAMESPACE,
            query={
                "inputs": {"text": query_text},
                "top_k": TOP_K
            }
        )
        hits = results.get("result", {}).get("matches", [])
        chunks = []
        for hit in hits:
            # old metadata format
            meta = hit.get("metadata", {})
            chunk_text = meta.get("chunk_text", "") or meta.get("text", "")
            source = meta.get("source", "")
            score = hit.get("score", 0.0)
            chunks.append({"text": chunk_text, "source": source, "score": score})
        return chunks


# -----------------------------
# Helper: build context
# -----------------------------
def build_context(chunks):
    if not chunks:
        return ""
    ctx = "\n\n---\n\n".join(
        f"[{i+1}] (score={ch['score']:.3f}) (source={ch['source']})\n{ch['text']}"
        for i, ch in enumerate(chunks)
    )
    return ctx

# -----------------------------
# Helper: call LLM
# -----------------------------
def call_groq_llm(context: str, user_query: str):
    system_prompt = textwrap.dedent(f"""
    You are a helpful university assistant.
    Answer the user's question directly and concisely using ONLY the provided context.Read all the context before answering.
    - Do NOT show reasoning or internal thoughts.
    -Do NOT reference the chunk numbers.
    - Do not SHOW think statements.
    - Do NOT repeat information.
    - Do NOT invent answers.
    - If the context does not contain the answer, respond: "I don't know".
    - Format the answer in a friendly, human-readable way.
    - Only return the final answer, nothing else.
    -Give a proper answer based on the context.


        Context:
        {context}
    """)
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        "temperature": 0.0,
        "max_tokens": 600
    }
    resp = requests.post(GROQ_API_CHAT_URL, headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]
# -----------------------------
# CLI loop
# -----------------------------
if __name__ == "__main__":
    print("📌 Pinecone + LLM CLI - type 'exit' to quit.\n")
    while True:
        user_query = input("Ask your question: ").strip()
        if user_query.lower() in ["exit", "quit"]:
            break

        # 1️⃣ Retrieve chunks from Pinecone
        chunks = retrieve_chunks(user_query)
        if not chunks:
            print("❌ No relevant context found in Pinecone.\n")
            continue

        # 2️⃣ Build context
        context = build_context(chunks)

        # 3️⃣ Call LLM with context + query
        try:
            answer = call_groq_llm(context, user_query)
            print("\n=== Answer ===")
            print(answer)
            print("\n")
        except Exception as e:
            print(f"❌ LLM call failed: {e}\n")
