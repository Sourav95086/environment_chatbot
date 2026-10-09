
import requests
import uuid

API_URL = "http://127.0.0.1:8000/chat"

session_id = str(uuid.uuid4())

print("\n" + "=" * 55)
print("      ENVIRONMENTAL ESG REPORTING CHATBOT")
print("=" * 55)
print("Type 'exit' to quit | 'new' to start a new conversation\n")

while True:
    try:
        message = input("You: ").strip()

        if not message:
            continue

        if message.lower() == "exit":
            print("\nChat ended. Goodbye!")
            break

        if message.lower() == "new":
            session_id = str(uuid.uuid4())
            print("\nStarted a new conversation.\n")
            continue

        payload = {
            "message": message,
            "session_id": session_id,
            "project_id": 1
        }

        print("\nBot: Thinking...\n")

        response = requests.post(
            API_URL,
            json=payload,
            timeout=360
        )

        if response.ok:
            data = response.json()
            print(f"Bot: {data['reply']}\n")
        else:
            print(f"Error {response.status_code}: {response.text}\n")

    except requests.exceptions.ConnectionError:
        print("Cannot connect to the chatbot API.")
        print("Make sure the FastAPI server is running.\n")

    except requests.exceptions.Timeout:
        print("The request took too long. Check the server logs.\n")

    except KeyboardInterrupt:
        print("\n\nChat ended.")
        break

    except Exception as error:
        print(f"Unexpected error: {error}\n")

