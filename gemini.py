import os
from dotenv import load_dotenv
from google import genai
load_dotenv()
def test_gemini_connection():
    # 1. Load the .env file explicitly
    
    
    # 2. Check if the key exists in the environment variables
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ Error: GEMINI_API_KEY not found in environment variables.")
        print("Ensure your file is named exactly '.env' and contains: GEMINI_API_KEY=\"your_key_here\"")
        return

    print(f"Key found in .env (Prefix: {api_key[:6]}...)")
    print("Connecting to Gemini API...")
    
    try:
        # 3. Initialize the client (automatically reads GEMINI_API_KEY)
        client = genai.Client(api_key=api_key)
        
        # 4. Fire a fast, low-cost verification call
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents='How are you today gemini'
        )
        
        print("\n====================================")
        print(f"🎉 API Status: {response.text.strip()}")
        print("====================================")
        print("Your credentials are correct. You can now safely run the main pipeline.")
        
    except Exception as e:
        print("\n====================================")
        print("❌ API Connection Failed")
        print("====================================")
        print(f"Details: {str(e)}")
        print("\nTroubleshooting steps:")
        print("1. Double-check for typos or extra spaces in your .env file.")
        print("2. Ensure your billing or account tier allows access to the model 'gemini-2.5-flash'.")

if __name__ == "__main__":
    test_gemini_connection()