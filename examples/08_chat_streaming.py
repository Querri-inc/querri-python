"""Chat streaming — stream AI responses chunk by chunk.

Demonstrates:
- Creating a chat on a project
- Streaming a response token by token
- Getting the full response text with .text()
- Listing and deleting chats

Prerequisites:
    export QUERRI_API_KEY="qk_..."
    export QUERRI_ORG_ID="org_..."

    You need an existing project with data for meaningful AI responses.
    Set PROJECT_ID to a project UUID that has step results.
"""

import os

from querri import Querri

# Replace with a real project ID, or set via environment variable
PROJECT_ID = os.environ.get("PROJECT_ID", "your-project-uuid-here")
USER_ID = os.environ.get("USER_ID", "your-user-id-here")


def main():
    client = Querri(
        api_key=os.environ["QUERRI_API_KEY"],
        org_id=os.environ["QUERRI_ORG_ID"],
    )

    chat_id = None

    try:
        # Create a chat
        print("=== Creating chat ===")
        chat = client.projects.chats.create(
            PROJECT_ID,
            name="SDK Example Chat",
        )
        chat_id = chat.id
        print(f"  Chat ID: {chat.id}")

        # Stream a response chunk by chunk
        print("\n=== Streaming response ===")
        stream = client.projects.chats.stream(
            PROJECT_ID,
            chat_id,
            prompt="Summarize the data in this project",
            user_id=USER_ID,
        )
        for chunk in stream:
            print(chunk, end="", flush=True)
        print("\n")

        # Send another message and get the full text at once
        print("=== Full text response ===")
        stream = client.projects.chats.stream(
            PROJECT_ID,
            chat_id,
            prompt="What are the key insights?",
            user_id=USER_ID,
        )
        full_text = stream.text()
        print(full_text)

        # List chats on the project
        print("\n=== Listing chats ===")
        chats = client.projects.chats.list(PROJECT_ID, limit=10)
        for c in chats:
            print(f"  {c.id}: {c.name}")

    finally:
        # Cleanup
        if chat_id:
            client.projects.chats.delete(PROJECT_ID, chat_id)
            print(f"\nDeleted chat {chat_id}")
        client.close()


if __name__ == "__main__":
    main()
