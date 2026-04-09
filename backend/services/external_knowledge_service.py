import os
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def get_external_answer(question: str, role: str = "Employee"):
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",   # ✅ FIXED MODEL
            messages=[
                {
                    "role": "system",
                    "content": f"You are an enterprise AI assistant. Role: {role}"
                },
                {
                    "role": "user",
                    "content": question
                }
            ]
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"Error: {str(e)}"