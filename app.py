from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from test import retrieve_chunks, build_context, call_groq_llm
import uvicorn
import os

app = FastAPI()

# Enable CORS so frontend JS can call /ask
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class Query(BaseModel):
    question: str

# Serve index.html
@app.get("/", response_class=FileResponse)
def read_index():
    return FileResponse("index.html")  # make sure index.html is in the same folder as app.py

# Chat endpoint
@app.post("/ask")
async def ask_question(query: Query):
    chunks = retrieve_chunks(query.question)
    if not chunks:
        return JSONResponse({"answer": "I don't know"})
    context = build_context(chunks)
    answer = call_groq_llm(context, query.question)
    return JSONResponse({"answer": answer})

# Run server
if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
