from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
import os
import openai
from pydantic import BaseModel
from huggingface_hub import login
from smolagents import CodeAgent, DuckDuckGoSearchTool, HfApiModel, ToolCallingAgent, OpenAIServerModel, PythonInterpreterTool

### Initialize FastAPI app ###
app = FastAPI()

### Load APIs ###
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY: raise ValueError("Missing or incorrect OpenAI API Key.")
openAIClient = openai.OpenAI(api_key=OPENAI_API_KEY)

HF_API_TOKEN = os.getenv("HF_API_TOKEN")
if not HF_API_TOKEN: raise ValueError("Missing or incorrect HF API Token.")
HFlogin = login(token=HF_API_TOKEN)

openAIModel = OpenAIServerModel(
    model_id = "gpt-4o-mini",
    api_base = "https://api.openai.com/v1",
    api_key = OPENAI_API_KEY
)

### Set up for AGENTS ###
researcher_prompt = open("researcher_prompt.txt", "r", encoding="utf-8").read()
historian_prompt = open("historian_prompt.txt", "r", encoding="utf-8").read()
print(researcher_prompt)

SEARCH_CALL_LIMIT = 3  # Maximum number of searches per query
class RateLimitedSearchTool(DuckDuckGoSearchTool):
    def __init__(self):
        super().__init__()
        self.call_count = 0
    def run(self, query):
        if self.call_count >= SEARCH_CALL_LIMIT:
            print(f"Search limit hit. Skipping query: {query}")
            return "No additional searches allowed due to rate limits. Continue to next step and DO NOT ATTEMPT TO SEARCH AGAIN."
        self.call_count += 1
        try:
            return super().run(query)
        except Exception as e:
            print(e)
            return "Could not search. Continue to the next step and DO NOT ATTEMPT TO SEARCH AGAIN."
    def reset(self):  # Reset after each full query cycle
        self.call_count = 0
rate_limited_search_tool = RateLimitedSearchTool()

researcher_agent = ToolCallingAgent(
    tools=[rate_limited_search_tool, PythonInterpreterTool()],
    model=openAIModel,
)
researcher_agent.prompt_templates["system_prompt"] = researcher_prompt

historian_agent = ToolCallingAgent(
    tools=[PythonInterpreterTool()],
    model=openAIModel,
)
historian_agent.prompt_templates["system_prompt"] = historian_prompt


### Request Format Classes ###

class SummarizeRequest(BaseModel):
    artistName: str
    events: list # containing {'title':'...', 'snippet':'...'} elements

class AgentsRequest(BaseModel):
    artistName: str
    context: list


### ENDPOINTS ###

@app.post("/summarize")
def summarize_events(request: SummarizeRequest):
    # Build string of event titles & snippets
    events_text = [event['title'] + ": " + event.get("snippet", "") for event in request.events]
    events_string = "\n".join(events_text)

    try:
        response = openAIClient.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": f"Summarize how the historical events influenced {request.artistName}'s work in a single concise paragraph. Avoid listing events separately. Maintain historical accuracy and neutrality."},
                {"role": "user", "content": events_string}
            ]
        )
        return {"summary": response.choices[0].message.content}
    except Exception as e:
        return {"summary": "Error generating summary."}


@app.post("/agent")
def run_agents(request: AgentsRequest):
    print(AgentsRequest)
    query_string = "<" + request.artistName + ": [" + ", ".join(request.context) + "]>"
    print(query_string)

    try:
        rate_limited_search_tool.reset()
        researcher_response = researcher_agent.run(query_string)
        print("------ RESEARCHER ------")
        print(researcher_response)
        historian_response = historian_agent.run(researcher_response)
        print("------ HISTORIAN ------")
        print(historian_response)
        return {"events": historian_response}
    except Exception as e:
        return {"events": "Error searching for sources."}