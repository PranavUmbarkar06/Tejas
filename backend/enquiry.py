"""
Policy Enquiry RAG System
Retrieves verified context fragments from the local vector space 
and runs a structured generative analysis via Gemini.
"""
import os
from google import genai
# Import your original DOCVectorDB class definition
from vectorise import DOCVectorDB  
from dotenv import load_dotenv


load_dotenv() 


api_key=os.getenv("GEMINI_API_KEY")  # Load environment variables from .env file

def run_policy_rag_query(user_query: str, db_path: str = "./chroma_db") -> str:
    """
    Executes a clean RAG loop:
    1. Connects to the local database instance.
    2. Retrieves top matching policy chunks.
    3. Fuses chunks into a strict prompt template.
    4. Executes a production-grade LLM call.
    """
    # 1. Verify database existence before processing the network call
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Active vector space not found at '{db_path}'. "
            f"Please run your initialization / update script first."
        )

    # 2. Instantiate connection to the existing database index
    print(f"[RAG Subsystem] Connecting to database index at: {db_path}")
    vector_db = DOCVectorDB(db_path=db_path)

    # 3. Pull the top 3 most semantically accurate context blocks from the PDF
    print(f"[RAG Subsystem] Extracting matching policy context for query: '{user_query}'")
    retrieved_policy_context = vector_db.retrieve_context(
        search_keyword=user_query, 
        max_results=3
    )

    if not retrieved_policy_context.strip():
        return "Error: No matching policy data found in the database instance."

    # 4. Construct a strict system context prompt template
    # This prevents the model from generating fake rules or codes
    rag_prompt = f"""
    You are an elite automated banking compliance officer auditing credit policy documentation.
    Analyze the user's inquiry using ONLY the verified policy sections provided below.

    CRITICAL COMPLIANCE DIRECTIVES:
    - Base your response strictly on the factual data fragments provided.
    - If a specific metric, percentage, tier boundary, or alphanumeric error code is not present in the context below, state clearly that it is omitted from the current policy documentation. Do not invent codes.
    - Keep the final response clear, concise, and structured.

    [VERIFIED BANK POLICY CONTEXT FRAGMENTS]
    {retrieved_policy_context}

    [USER COMPLIANCE INQUIRY]
    {user_query}
    
    SYSTEM RESPONSE:
    """

    # 5. Initialize the modern Google Gen AI Client
    # Ensure GEMINI_API_KEY is configured in your system environment variables
    client = genai.Client(api_key=api_key)

    # 6. Execute the generative inference call
    print("[RAG Subsystem] Dispatched context blocks to Gemini API engine...")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=rag_prompt
    )

    return response.text.strip()


# ==========================================
# PRODUCTION TEST EXECUTIONS
# ==========================================
if __name__ == "__main__":
    # Ensure your database path matches where your ingestion script wrote the data
    DATABASE_PATH = "./chroma_db"
    
    
    answer_2 = run_policy_rag_query(user_query="Can i apply for home loans through this policy?", db_path=DATABASE_PATH)
    print("\n[Gemini Answer]:\n", answer_2)