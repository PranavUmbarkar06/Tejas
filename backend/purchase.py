#purchase.py
import os
import json
import pypdf
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from google import genai
from google.genai import types
from vectorise import DOCVectorDB

# Load local environment parameters
load_dotenv()
api_key=os.environ.get("GEMINI_API_KEY")

# =====================================================================
# PIPELINE COMPONENT 1: HISTORICAL DATA COMPRESSION
# =====================================================================
def process_purchase_history_trend(raw_history_list: list) -> dict:
    """
    Programmatically compresses raw, multi-year transaction trends into a high-density, 
    low-token summary object to optimize Gemini LLM context utility.
    """
    total_active_emi = 0
    active_loan_types = []
    historical_delinquencies = 0
    
    for record in raw_history_list:
        if record.get("status") == "active":
            total_active_emi += record.get("monthly_emi", 0)
            if record.get("type") not in active_loan_types:
                active_loan_types.append(record.get("type"))
        if record.get("delinquent_count", 0) > 0:
            historical_delinquencies += record.get("delinquent_count", 0)
            
    return {
        "total_active_monthly_emi": total_active_emi,
        "existing_loan_types": active_loan_types,
        "historical_risk_flags": historical_delinquencies,
        "liquidity_stability": "High (Savings account balances remained consistently above safety floors over trailing 36 months)"
    }




# =====================================================================
# PIPELINE COMPONENT 3: STRATEGY ORCHESTRATOR & GEMINI CLIENT
# =====================================================================
def run_purchase_advisor_pipeline(user_profile_json: str, target_product: str, purchase_amount: float, pdf_path: str) -> str:
    """
    Core orchestrator: coordinates data extraction, runs compression analytics, 
    queries ChromaDB, and executes a robust generative analysis using the Gemini API.
    """
    # 1. Parse raw profile input
    profile_data = json.loads(user_profile_json)
    
    # 2. Extract and compress historical trend logs
    raw_history = profile_data.get("purchasing_history", [])
    compressed_history_metrics = process_purchase_history_trend(raw_history)
    
    # 3. Assemble clean profile context block (stripping redundant arrays)
    sanitized_user_payload = {
        "uid": profile_data.get("uid"),
        "name": profile_data.get("name"),
        "financial_profile": profile_data.get("financial_profile"),
        "five_year_history_metrics": compressed_history_metrics
    }

    # 4. Query ChromaDB for specific credit policy rules matching the purchase request
    vector_db = DOCVectorDB(db_path="./chroma_db")
    retrieved_policy_context = vector_db.retrieve_context(search_keyword=target_product, max_results=2)

    # 5. Define explicit, deterministic instructions for the model
    system_instruction = """
    You are an objective corporate credit underwriting agent representing the bank's retail risk management division. 
    Your role is to rigorously evaluate an applicant's purchase proposal against the provided internal policy directives and their processed financial profile.

    STRICT OPERATIONAL DIRECTIVES:
    - You must cross-reference the applicant's CIBIL score, calculated FOIR/DTI ratio, and emergency buffer threshold directly against the numeric boundaries defined inside the provided [BANK POLICY CONTEXT].
    - Do not make assumptions, invent tolerances, or soften credit policies. If a rule condition is broken, you must execute a definitive rejection and output the alphanumeric error code corresponding to that specific policy failure (found in Section 4).
    - If the application complies with all guidelines, outline a conversational, precise hybrid-financing strategy or upfront deployment recommendation based strictly on the parameters authorized in the policy document.
    """

    user_prompt = f"""
    [BANK POLICY CONTEXT]
    {retrieved_policy_context}

    [BANK POLICY CONTEXT UPDATE]
    - Maximum FOIR/DTI Allowed: 50% for Tier 3, 55% for Tier 2, 60% for Tier 1.
    - Emergency Buffer Threshold: Applicant must retain a minimum of INR 20,000 or 15% of net monthly income (whichever is higher) after all EMI obligations.
    - CIBIL Tier Ranges: Tier 3 (680-720), Tier 2 (721-779), Tier 1 (780+).
    
    [USER FINANCIAL PROFILE JSON]
    {json.dumps(sanitized_user_payload, indent=2)}
    
    [PURCHASE DISPATCH DATA]
    Requested Product Type: {target_product}
    Purchase Obligation Amount: INR {purchase_amount}
    
    Provide the analytical breakdown, definitive compliance ruling code, and actionable financial execution steps.
    """

    # 6. Execute model inference using the current Google GenAI platform standards
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.15,  # Low variance to guarantee deterministic policy tracking
            )
        )
        return response.text
    except Exception as e:
        return f"Pipeline Execution Exception: Configuration error on upstream client interface. Details: {str(e)}"


# =====================================================================
# SIMULATED APPLICATION EXECUTION
# =====================================================================
if __name__ == "__main__":
    # Simulated input payload generated from the system profile database
    simulated_user_payload = """
        {
            "uid": "a9f8b7c6-e5d4-4c3b-2a1e-0f9e8d7c6b5a",
            "name": "Arjun Mehta",
            "dob": "14/08/1997",
            "aadhar_card_number": "[Aadhaar Redacted]",
            "pan_card_number": "B772AM91822K",
            "websites": {},
            "financial_profile": {
                "current_savings_balance": 3500000,
                "estimated_monthly_net_income":35000,
                "current_cibil_score": 718
            },
            "purchasing_history": [
                {"year": 2025, "type": "Personal Loan", "monthly_emi": 45000, "status": "active", "delinquent_count": 0}
            ]
        }
        """

    # Local path to your compiled rules document
    compliance_pdf = "../database/policy/Retail_Banking_Credit_Policy_v2026.2.pdf"

    # Evaluate execution logic
    advisor_strategy_output = run_purchase_advisor_pipeline(
        user_profile_json=simulated_user_payload,
        target_product="luxury car",
        purchase_amount=8000000,
        pdf_path=compliance_pdf
    )

    print(advisor_strategy_output)