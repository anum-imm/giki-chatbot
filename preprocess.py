import json
import re
import os
import uuid
from tqdm import tqdm

def clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'http\S+', '', text)
    return text.strip()

def chunk_text(text, max_words=200, overlap=50):
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words - overlap):
        chunks.append(" ".join(words[i:i + max_words]))
    return chunks

def preprocess(input_path="data/raw/giki_scraped.json", output_path="data/processed/giki_chunks.json"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    processed = []
    for page in tqdm(data, desc="Processing pages"):
        content = clean_text(page.get("content", ""))
        if not content:
            continue
        chunks = chunk_text(content)
        for chunk in chunks:
            processed.append({
                "id": str(uuid.uuid4()),
                "source": page.get("url", ""),
                "title": page.get("title", "Untitled"),
                "text": chunk
            })
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(processed, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Preprocessed {len(processed)} text chunks saved to {output_path}")
    print(f"📊 Pages processed: {len(data)}")

if __name__ == "__main__":
    preprocess()
