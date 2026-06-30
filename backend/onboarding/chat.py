import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from details import UnifiedOcrPipeline


pipeline=UnifiedOcrPipeline()



class OnboardingSession:
    """Manages the conversation state and data collection using structured OCR dictionary outputs."""

    def __init__(self) -> None:
        self.uid: str = str(uuid.uuid4())
        self.name: Optional[str] = None
        self.dob: Optional[str] = None
        self.pan_card_number: Optional[str] = None
        self.aadhar_card_number: Optional[str] = None

        # States: 'START', 'AWAITING_NAME', 'AWAITING_DOB',
        #         'AWAITING_PAN', 'AWAITING_AADHAAR', 'COMPLETED'
        self.current_state: str = "START"

    def get_next_prompt(self) -> str:
        """Returns the appropriate conversational prompt based on the current state."""
        if self.current_state == "START":
            self.current_state = "AWAITING_NAME"
            return (
                "Welcome to Tejas, your very own personalized banking solution!\n"
                "Please enter your name:"
            )
        elif self.current_state == "AWAITING_NAME":
            return "Please enter your name:"
        elif self.current_state == "AWAITING_DOB":
            return "Please enter your date of birth (DD/MM/YYYY):"
        elif self.current_state == "AWAITING_PAN":
            return "Please upload your PAN card:"
        elif self.current_state == "AWAITING_AADHAAR":
            return "Please upload your Aadhaar card:"
        elif self.current_state == "COMPLETED":
            return "Onboarding is complete! Thank you."
        return "System error: Unknown state."

    def process_text_input(self, user_input: str) -> Optional[str]:
        """Processes regular conversational text inputs (Name, DOB)."""
        user_input = user_input.strip()
        if not user_input:
            return "Input cannot be empty. Please try again."

        if self.current_state == "AWAITING_NAME":
            self.name = user_input
            self.current_state = "AWAITING_DOB"
            return None

        elif self.current_state == "AWAITING_DOB":
            try:
                datetime.strptime(user_input, "%d/%m/%Y")
                self.dob = user_input
                self.current_state = "AWAITING_PAN"
                return None
            except ValueError:
                return "Invalid date format. Please use DD/MM/YYYY (e.g., 15/08/1947)."

        return "Expecting a document upload, not a text entry."



    def extract_text_from_document(self,file_path: str) -> Dict[str, Any]:
        """Your existing OCR function structure.

        Returns the dictionary payload with extracted information.
        """

        
        result = pipeline.process_document(file_path)
        if result['document_type']=='PAN':
            self.pan_card_number=result['pan_number']
        elif result['document_type']=='AADHAAR':
            self.aadhar_card_number=result['aadhaar_number']
        # This matches the dictionary your backend or OCR function returns
        
        

    def to_json(self) -> str:
        """Compiles the finalized onboarding data into the target JSON structure."""
        if self.current_state != "COMPLETED":
            raise ValueError("Cannot generate JSON: Onboarding is incomplete.")

        data: Dict[str, Any] = {
            "uid": self.uid,
            "name": self.name,
            "dob": self.dob,
            "aadhar_card_number": self.aadhar_card_number,
            "pan_card_number": self.pan_card_number,
            "websites":{}
        }
        return json.dumps(data, indent=4)


    # --- Simulating workflow execution ---
if __name__ == "__main__":
    # Instantiate the state machine session
    session = OnboardingSession()

    # 1. Step 1: Initial Welcome & Process Name
    print(f"Platform: {session.get_next_prompt()}")
    name_error = session.process_text_input("Pranav Umbarkar")
    if name_error:
        print(f"Validation Error: {name_error}")
    else:
        print("User input accepted: Name saved.\n")

    # 2. Step 2: Prompt for DOB & Process DOB
    print(f"Platform: {session.get_next_prompt()}")
    dob_error = session.process_text_input("25/12/2000")
    if dob_error:
        print(f"Validation Error: {dob_error}")
    else:
        print("User input accepted: DOB saved.\n")

    # 3. Step 3: Prompt for PAN Card & Execute Pipeline
    print(f"Platform: {session.get_next_prompt()}")
    # Your method runs the pipeline internally and mutates self.pan_card_number
    session.extract_text_from_document("data/pan_card.jpeg")
    
    # Explicitly advance state since internal method doesn't modify state engine
    session.current_state = "AWAITING_AADHAAR" 
    print(f"PAN Extraction updated field -> pan_card_number: {session.pan_card_number}\n")

    # 4. Step 4: Prompt for Aadhaar Card & Execute Pipeline
    print(f"Platform: {session.get_next_prompt()}")
    # Your method runs the pipeline internally and mutates self.aadhar_card_number
    session.extract_text_from_document("data/fake aadhar.pdf")
    
    # Complete the session state
    session.current_state = "COMPLETED"
    print(f"Aadhaar Extraction updated field -> aadhar_card_number: [Redacted for Privacy]\n")

    # 5. Compile and Output Final JSON Structured Output
    print(f"Platform: {session.get_next_prompt()}")
    print("\n--- Final Generated JSON Payload ---")
    try:
        print(session.to_json())
    except ValueError as e:
        print(f"Execution failed: {e}")
    

    # Welcome & Name step
    
    # Simulating your function running on a file path and returning its extraction dictionary
    
    
    