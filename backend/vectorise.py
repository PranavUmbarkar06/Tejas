import os
import json
import pypdf
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from google import genai
from google.genai import types


class DOCVectorDB:
    def __init__(self, db_path: str = "./chroma_db"):
        # Initialize persistent disk storage for Chroma
        self.chroma_client = chromadb.PersistentClient(path=db_path)
        
        # Using standard default embedding function provided by Chroma locally
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        
        self.collection = self.chroma_client.get_or_create_collection(
            name="bank_credit_policies",
            embedding_function=self.embedding_fn
        )

    def ingest_policy_pdf(self, pdf_path: str, chunk_size: int = 1000, overlap: int = 200):
        """Extracts text from a policy PDF and indexes overlapping semantic chunks into ChromaDB."""
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Target compliance PDF not found at path: {pdf_path}")

        reader = pypdf.PdfReader(pdf_path)
        full_text = "".join([page.extract_text() or "" for page in reader.pages])
        
        chunks = []
        start = 0
        while start < len(full_text):
            end = start + chunk_size
            chunks.append(full_text[start:end])
            start += chunk_size - overlap

        # Batch upsert entries into the vector collection
        documents_ids = [f"chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"source": os.path.basename(pdf_path)} for _ in chunks]
        
        self.collection.upsert(
            documents=chunks,
            ids=documents_ids,
            metadatas=metadatas
        )

    def retrieve_context(self, search_keyword: str, max_results: int = 2) -> str:
        """Queries the Chroma vector index using semantic keyword matching."""
        results = self.collection.query(
            query_texts=[search_keyword],
            n_results=max_results
        )
        
        # Flatten matching documents list into a cohesive block of text
        flattened_documents = results.get("documents", [[]])[0]
        return "\n--- Policy Section Boundary ---\n".join(flattened_documents)
    




if __name__ == "__main__":
    compliance_pdf = "../database/policy/Retail_Banking_Credit_Policy_v2026.2.pdf"
    DOCVectorDB(db_path="./chroma_db").ingest_policy_pdf(compliance_pdf)