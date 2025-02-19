from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
import os
import openai
from pydantic import BaseModel

# Initialize FastAPI app
app = FastAPI()

# Load openai
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Missing OpenAI API Key. Set OPENAI_API_KEY as an environment variable or in a .env file.")
client = openai.OpenAI(api_key=OPENAI_API_KEY)


class SummarizeRequest(BaseModel):
    artistName: str
    events: list # containing {'title':'...', 'snippet':'...'} elements

@app.post("/summarize")
def summarize_events(request: SummarizeRequest):
    # Build string of event titles & snippets
    events_text = [event['title'] + ": " + event.get("snippet", "") for event in request.events]
    events_string = "\n".join(events_text)

    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": f"Summarize how the historical events influenced {request.artistName}'s work in a single concise paragraph. Avoid listing events separately. Maintain historical accuracy and neutrality."},
                {"role": "user", "content": events_string}
            ]
        )
        return {"summary": response.choices[0].message.content}
    except Exception as e:
        return {"summary": "Error generating summary."}
