
import os
from groq import Groq


# ✅ Lazy initialization (VERY IMPORTANT)
def get_client():
    return Groq(api_key=os.getenv("GROQ_API_KEY"))


def get_external_answer(question: str, role: str = "Employee"):
    try:
        # ✅ Handle invalid input
        if not question or not str(question).strip():
            return "Invalid input"

        client = get_client()

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": f"You are an enterprise AI assistant. Role: {role}"
                },
                {
                    "role": "user",
                    "content": str(question)
                }
            ]
        )

        # ✅ Safe response handling
        if not response or not hasattr(response, "choices") or not response.choices:
            return "No response from model"

        message = response.choices[0].message

        if not message or not hasattr(message, "content"):
            return "No response from model"

        return message.content.strip()

    except Exception as e:
        return f"Error: {str(e)}"

