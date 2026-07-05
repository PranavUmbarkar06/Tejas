import os
import cv2
import re
import numpy as np
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
# test comment 
# Set explicit Tesseract path if needed
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class UnifiedOcrPipeline:
    def __init__(self):
        self.tesseract_config = r'--oem 3 --psm 11'
        # Set this if poppler isn't added to your Windows PATH globally
        self.poppler_path = r"C:\Program Files\poppler-26.02.0\Library\bin"


    def preprocess_cv_image(self, cv_img) -> np.ndarray:
        """Applies OpenCV transformations to clean up the text lines."""
        img = cv2.resize(cv_img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        filtered = cv2.bilateralFilter(gray, 9, 75, 75)
        _, binary_img = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary_img

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Converts PDF pages into images and concatenates their OCR extractions."""
        try:
            # Convert all pages of the PDF into a list of PIL Images
            pages = convert_from_path(pdf_path, dpi=200, poppler_path=self.poppler_path)
            combined_text = ""

            for page in pages:
                # Convert PIL Image format to an OpenCV format NumPy array
                open_cv_image = np.array(page)
                # PIL uses RGB, OpenCV uses BGR layout
                open_cv_image = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2BGR)
                
                # Clean using our standard preprocessing setup
                processed = self.preprocess_cv_image(open_cv_image)
                page_text = pytesseract.image_to_string(processed, config=self.tesseract_config)
                combined_text += page_text + "\n"
                
            return combined_text
        except Exception as e:
            raise RuntimeError(f"Failed to process PDF file: {str(e)}")

    def extract_text_from_image(self, image_path: str) -> str:
        """Loads a traditional flat image file and processes it."""
        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"Image not found at path: {image_path}")
        
        processed = self.preprocess_cv_image(img)
        return pytesseract.image_to_string(processed, config=self.tesseract_config)

    def classify_document_type(self, text: str) -> str:
        """Analyzes the raw OCR string text to classify the card type."""
        clean_text = text.upper()

        # Define high-confidence keyword markers
        pan_keywords = ["INCOME TAX DEPARTMENT", "PERMANENT ACCOUNT NUMBER", "INCOMETAX"]
        aadhaar_keywords = ["UNIQUE IDENTIFICATION", "UIDAI", "ENROLLMENT NO", "MALE", "FEMALE"]

        # Check for matching keywords
        if any(keyword in clean_text for keyword in pan_keywords):
            return "PAN"
        elif any(keyword in clean_text for keyword in aadhaar_keywords):
            return "AADHAAR"
        
        return "UNKNOWN"
    





    def process_document(self, file_path: str) -> dict:
        """Routes, extracts, classifies, and targets parsing patterns dynamically."""
        # 1. Image/PDF Routing Step
        import os
        _, ext = os.path.splitext(file_path.lower())
        if ext == '.pdf':
            raw_text = self.extract_text_from_pdf(file_path)
        elif ext in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']:
            raw_text = self.extract_text_from_image(file_path)
        else:
            raise ValueError(f"Unsupported extension: {ext}")

        clean_text = raw_text.upper().strip()
        
        # 2. Automatically Detect Card Type
        doc_type = self.classify_document_type(clean_text)
        
        # 3. Base Extraction Schema
        extracted_data = {
            "document_type": doc_type,
            "pan_number": None,
            "dob": None,
            "aadhaar_number": None, # Kept in schema initialization
            "raw_text_dump": raw_text
        }

        # Common DOB regex for both cards
        dob_pattern = r'(\b\d{2}[/\-]\d{2}[/\-]\d{4}\b|\b\d{4}[/\-]\d{2}[/\-]\d{2}\b)'
        dob_match = re.search(dob_pattern, clean_text)
        if dob_match:
            extracted_data["dob"] = dob_match.group(0)

        # 4. Target Specific Fields Based on Card Classification
        if doc_type == "PAN":
            pan_pattern = r'[A-Z]{5}[0-9]{4}[A-Z]{1}'
            pan_match = re.search(pan_pattern, clean_text)
            if pan_match:
                extracted_data["pan_number"] = pan_match.group(0)
                
        elif doc_type == "AADHAAR":
            aadhaar_pattern = r'\b\d{4}\s?\d{4}\s?\d{4}\b'
            aadhaar_match = re.search(aadhaar_pattern, clean_text)
            if aadhaar_match:
                extracted_data["aadhaar_number"] = aadhaar_match.group(0).replace(" ", "")

        return extracted_data

# --- Execution Example ---
if __name__ == "__main__":
    # Use the exact path you verified
    
    pipeline = UnifiedOcrPipeline()

    try:
        result = pipeline.process_document("data/fake aadhar.pdf")
        
        print(f"Card Detected: {result['document_type']}")
        print(f"PAN Number:    {result.get('pan_number')}")
        print(f"DOB:           {result.get('dob')}")
        print(f"Aadhaar No:    {result.get('aadhaar_number')}") # Double 'a' validation check
        
    except Exception as e:
        print(f"Pipeline Error: {e}")