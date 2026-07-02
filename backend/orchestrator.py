"""
orchestrator.py

Unified Prompt Receiver / Orchestrator
========================================
Single entry point that:
  1. Accepts raw, unstructured user input (+ a user id to key into the profile DB)
  2. Uses Gemini to classify intent and extract structured parameters
  3. Loads the user's financial profile from a local JSON store (data-extraction utility)
  4. Routes the request to the appropriate downstream module (purchase.py / enquiry.py)
  5. Returns a uniform, structured response envelope and handles failure/edge cases gracefully

Requires: purchase.py and enquiry.py to be importable on the path, plus a chroma_db
already ingested via vectorise.py.
"""

import os
import json
import logging
from enum import Enum
from typing import Optional, TypedDict, Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

from purchase import run_purchase_advisor_pipeline
from enquiry import run_policy_rag_query

load_dotenv()
API_KEY = os.environ.get("GEMINI_API_KEY")

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("orchestrator")


# =====================================================================
# INTENT SCHEMA
# =====================================================================
class Intent(str, Enum):
    PURCHASE_ADVISORY = "purchase_advisory"
    POLICY_ENQUIRY = "policy_enquiry"
    UNKNOWN = "unknown"


class ClassifiedRequest(TypedDict):
    intent: str
    confidence: float
    target_product: Optional[str]
    purchase_amount: Optional[float]
    policy_query_text: Optional[str]
    clarification_needed: bool
    clarification_prompt: Optional[str]


_INTENT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "intent": {
            "type": "STRING",
            "enum": [e.value for e in Intent],
        },
        "confidence": {"type": "NUMBER"},
        "target_product": {"type": "STRING", "nullable": True},
        "purchase_amount": {"type": "NUMBER", "nullable": True},
        "policy_query_text": {"type": "STRING", "nullable": True},
        "clarification_needed": {"type": "BOOLEAN"},
        "clarification_prompt": {"type": "STRING", "nullable": True},
    },
    "required": [
        "intent",
        "confidence",
        "target_product",
        "purchase_amount",
        "policy_query_text",
        "clarification_needed",
        "clarification_prompt",
    ],
}
_CLASSIFIER_SYSTEM_INSTRUCTION = """
You are an intent-routing classifier for a retail banking assistant. Route requests into one of two categories:

1. purchase_advisory: The user is asking for a personal approval decision on a SPECIFIC, immediate purchase (e.g., "Can I buy a $50k car?", "Approve my 80 lakh home loan"). 
   - This requires BOTH a `target_product` AND a `purchase_amount`. 
   - ONLY set `clarification_needed=true` if the user explicitly asks for personal approval on a purchase but forgot to include the amount.

2. policy_enquiry: The user is asking general questions about bank policies, loan types, or eligibility (e.g., "Does the policy cover home loans?", "What are the rules for car loans?").
   - If they mention a product category (like a home loan) BUT do not mention an amount or ask for a personal approval ruling, route it here. 
   - Do NOT ask for clarification for general policy questions.

Extract structured parameters where present. Respond with strict JSON only, matching the provided schema.
"""


def classify_intent(user_input: str, client: genai.Client) -> ClassifiedRequest:
    """
    Calls Gemini to classify raw user input into a structured routing decision.
    Falls back to UNKNOWN with a clarification prompt on any parsing/API failure.
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_input,
            config=types.GenerateContentConfig(
                system_instruction=_CLASSIFIER_SYSTEM_INSTRUCTION,
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=_INTENT_SCHEMA,
            ),
        )
        parsed: ClassifiedRequest = json.loads(response.text)
        return parsed
    except Exception as exc:  # broad on purpose: this is the routing safety net
        logger.warning("Intent classification failed, defaulting to UNKNOWN: %s", exc)
        return {
            "intent": Intent.UNKNOWN.value,
            "confidence": 0.0,
            "target_product": None,
            "purchase_amount": None,
            "policy_query_text": user_input,
            "clarification_needed": True,
            "clarification_prompt": (
                "I couldn't confidently understand your request. Could you clarify whether "
                "you're asking a general policy question or want a compliance check on a "
                "specific purchase (and if so, which product and amount)?"
            ),
        }


# =====================================================================
# DATA-EXTRACTION: USER PROFILE CONTEXT PAYLOAD
# =====================================================================
def load_user_profile_context(uid: str, db_path: str = "../database/users/users.json") -> dict[str, Any]:
    """
    Boilerplate data-extraction utility.

    Retrieves a user's profile record from a local JSON 'database' (a flat file keyed by
    uid, or a list of profile records) and formats it as a clean, LLM-ready context payload.

    Edge cases handled:
      - Missing/unreadable DB file
      - Malformed JSON
      - uid not found
      - DB stored as either {uid: {...}} dict or [{...}, {...}] list
    """
    if not os.path.exists(db_path):
        logger.error("User database not found at %s", db_path)
        return {"uid": uid, "error": "profile_database_unavailable", "profile": None}

    try:
        with open(db_path, "r", encoding="utf-8") as f:
            raw_db = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read/parse user database: %s", exc)
        return {"uid": uid, "error": "profile_database_corrupt", "profile": None}

    # Normalize both supported DB shapes into a single lookup
    if isinstance(raw_db, dict):
        record = raw_db.get(uid)
    elif isinstance(raw_db, list):
        record = next((r for r in raw_db if r.get("uid") == uid), None)
    else:
        record = None

    if record is None:
        logger.warning("No profile found for uid=%s", uid)
        return {"uid": uid, "error": "profile_not_found", "profile": None}

    # Strip PII / noisy fields not needed downstream; keep only what LLM calls consume
    context_payload = {
        "uid": record.get("uid"),
        "name": record.get("name"),
        "financial_profile": record.get("financial_profile", {}),
        "purchasing_history": record.get("purchasing_history", []),
    }
    return {"uid": uid, "error": None, "profile": context_payload}


# =====================================================================
# ORCHESTRATOR / PROMPT RECEIVER
# =====================================================================
def handle_user_request(
    raw_user_input: str,
    uid: str,
    user_db_path: str = "../database/users/users.json",
    chroma_db_path: str = "./chroma_db",
) -> dict[str, Any]:
    """
    Single unified entry point ("prompt receiver").

    1. Classifies raw input into an intent + extracted params via Gemini.
    2. If clarification is needed, short-circuits and returns the clarification prompt
       instead of guessing/routing incorrectly.
    3. Loads the user's profile context from the JSON store (only if needed).
    4. Dispatches to the correct downstream module.
    5. Returns a structured, uniform response envelope regardless of which module ran.
    """
    if not raw_user_input or not raw_user_input.strip():
        return _envelope(intent=Intent.UNKNOWN, status="error", message="Empty request received.")

    if not API_KEY:
        return _envelope(intent=Intent.UNKNOWN, status="error", message="GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=API_KEY)

    classification = classify_intent(raw_user_input, client)
    intent = classification.get("intent", Intent.UNKNOWN.value)

    if classification.get("clarification_needed"):
        return _envelope(
            intent=intent,
            status="needs_clarification",
            message=classification.get("clarification_prompt") or "Could you provide more detail?",
        )

    # ---- Route: purchase advisory ----
    if intent == Intent.PURCHASE_ADVISORY.value:
        profile_ctx = load_user_profile_context(uid, db_path=user_db_path)
        if profile_ctx["error"]:
            return _envelope(
                intent=intent,
                status="error",
                message=f"Unable to load user profile ({profile_ctx['error']}).",
            )

        target_product = classification.get("target_product")
        purchase_amount = classification.get("purchase_amount")
        if not target_product or not purchase_amount:
            return _envelope(
                intent=intent,
                status="needs_clarification",
                message="Please specify both the product you want to purchase and the amount.",
            )

        try:
            result_text = run_purchase_advisor_pipeline(
                user_profile_json=json.dumps(profile_ctx["profile"]),
                target_product=target_product,
                purchase_amount=float(purchase_amount),
                pdf_path="",  # kept for interface compatibility; ingestion runs separately via vectorise.py
            )
            return _envelope(intent=intent, status="ok", message=result_text)
        except Exception as exc:
            logger.exception("Purchase advisory pipeline failed")
            return _envelope(intent=intent, status="error", message=f"Purchase advisory failed: {exc}")

    # ---- Route: policy enquiry ----
    if intent == Intent.POLICY_ENQUIRY.value:
        query_text = classification.get("policy_query_text") or raw_user_input
        try:
            result_text = run_policy_rag_query(user_query=query_text, db_path=chroma_db_path)
            return _envelope(intent=intent, status="ok", message=result_text)
        except FileNotFoundError as exc:
            return _envelope(intent=intent, status="error", message=str(exc))
        except Exception as exc:
            logger.exception("Policy enquiry pipeline failed")
            return _envelope(intent=intent, status="error", message=f"Policy enquiry failed: {exc}")

    # ---- Fallback ----
    return _envelope(
        intent=Intent.UNKNOWN,
        status="needs_clarification",
        message="I'm not sure whether this is a purchase check or a policy question — could you rephrase?",
    )


def _envelope(intent: Any, status: str, message: str) -> dict[str, Any]:
    """Uniform response shape returned to callers (API layer, CLI, chatbot frontend, etc.)."""
    intent_value = intent.value if isinstance(intent, Intent) else intent
    return {"intent": intent_value, "status": status, "message": message}


# =====================================================================
# CLI ENTRY POINT
# =====================================================================
if __name__ == "__main__":
    test_uid = "U001"

    for sample_input in [
        
        "I want to buy a luxury car worth 80 lakhs, am I eligible?"
    ]:
        print(f"\n>>> USER: {sample_input}")
        result = handle_user_request(sample_input, uid=test_uid)
        print(json.dumps(result, indent=2))

    