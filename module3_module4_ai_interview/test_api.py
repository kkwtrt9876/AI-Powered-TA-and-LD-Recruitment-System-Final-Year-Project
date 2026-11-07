import os
from groq import Groq
from dotenv import load_dotenv

print("Loading environment variables...")
load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
print(f"API Key found: {'Yes' if api_key else 'No'}")

if api_key:
    # Print first/last chars to check for whitespace issues
    print(f"Key starts with: '{api_key[:4]}'")
    print(f"Key ends with: '{api_key[-4:]}'")
    
    try:
        print("Attempting to connect to Groq...")
        client = Groq(api_key=api_key)
        
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": "Say hello",
                }
            ],
            model="llama-3.3-70b-versatile",
        )
        print("Success! Response from Groq:")
        print(chat_completion.choices[0].message.content)
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
else:
    print("ERROR: No API Key found. Please check your .env file.")
