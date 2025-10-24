# Chat Assistant + Pinecone DB

---

## 📘 Project Summary
This project builds a **retrieval-based chat assistant** for the GIKI website.  
It scrapes content such as departments, faculty, research domains, and academic programs; preprocesses and chunks the data; creates embeddings stored in **Pinecone DB**; and implements a **LangChain + RAG pipeline** served via a **FastAPI endpoint**.  
Deployment is done on **AWS EC2** behind **Nginx** for production-level hosting.

---

## ✨ Features
- Scrapes static and dynamic web pages (BeautifulSoup + Selenium)
- Preprocesses & chunks text for embeddings
- Creates and upserts vectors into Pinecone DB
- RAG pipeline using LangChain + Groq LLM
- REST API using FastAPI (`/query`, `/health`)
- Deployed on AWS EC2 with Nginx as reverse proxy

---

## 🧰 Requirements
- Python 3.10+
- Virtualenv
- Pinecone account & API key
- Groq (LLM) API key (or another LLM)
- Git (for version control)
- AWS EC2 instance for deployment

> All Python dependencies are listed in `requirements.txt`.

---

## ⚙️ Quickstart / Local Setup

### 1️⃣ Clone the repository
```bash
git clone https://github.com/anum-imm/giki-ai-lab project
cd project

2️⃣ Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

3️⃣ Create a .env file
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_ENV=your_pinecone_env
GROQ_API_KEY=your_groq_api_key
OPENAI_API_KEY=your_openai_if_used

4️⃣ Run scraping & preprocessing (optional if data provided)
python scripts/giki_selenium.py     # writes giki_data.json
python scripts/preprocess.py        # creates chunks and metadata

5️⃣ Create Pinecone index and upsert data
python scripts/create_index.py
python scripts/upsert_vectors.py

6️⃣ Run the API locally
uvicorn app:app --host 0.0.0.0 --port 8000


Then open your browser at
👉 http://127.0.0.1:8000/docs
 to test your endpoints.

🌐 Deployment (AWS EC2 + Nginx)

Launch an Ubuntu EC2 instance.

Install dependencies:

sudo apt update && sudo apt install python3-pip python3-venv nginx git -y


Clone your repo and set up the virtual environment.

Run FastAPI with Uvicorn on port 8000.

Configure Nginx as a reverse proxy to 127.0.0.1:8000.

Allow HTTP traffic (sudo ufw allow 80) and restart Nginx.

Access via your public IP:
http://<your-ec2-public-ip>