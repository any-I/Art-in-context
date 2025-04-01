from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
import os
import openai
import json
from pydantic import BaseModel
from huggingface_hub import login
from smolagents import CodeAgent, DuckDuckGoSearchTool, HfApiModel, ToolCallingAgent, OpenAIServerModel, PythonInterpreterTool
# for images:
import re 
import requests

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

# for google programmable search engine - images
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")

if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
    print("Error: GOOGLE_API_KEY or GOOGLE_CSE_ID not found in .env file. Image search will be disabled.")

openAIModel = OpenAIServerModel(
    model_id = "gpt-4o-mini",
    api_base = "https://api.openai.com/v1",
    api_key = OPENAI_API_KEY
)

### Set up for AGENTS ###
researcher_prompt = open("researcher_prompt.txt", "r", encoding="utf-8").read()
historian_prompt = open("historian_prompt.txt", "r", encoding="utf-8").read()
#print(researcher_prompt)

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

        # parsing logic (JSON)
        timeline_events = []
        error_message = None # hold potential error messages for the 'error' field
        
        try:
            json_part = historian_response.strip()

            if json_part.startswith("```json"):
                json_part = json_part[len("```json"):].strip()
            
            if json_part.endswith("```"):
                json_part = json_part[:-len("```")].strip()

            # attempt to parse the entire response as JSON
            try:
                timeline_events = json.loads(json_part)
                
                # validation: check if it's a list of dicts
                if not isinstance(timeline_events, list):
                    print("Warning: Parsed JSON is not a list.")
                    error_message = "Error: AI response format incorrect (expected a list)."
                    timeline_events = []

                elif not all(isinstance(item, dict) and
                               'date' in item and
                               'event_title' in item and
                               'detailed_summary' in item and
                               'location_name' in item and
                               'latitude' in item and isinstance(item['latitude'], (int, float)) and
                               'longitude' in item and isinstance(item['longitude'], (int, float)) and
                               'source_url' in item for item in timeline_events):
                    print("Warning: Parsed JSON list items have incorrect structure.")
                    error_message = "Error: AI response format incorrect (missing required fields or wrong types for location/coordinates in events)."
                    timeline_events = []
                # if validation passes, timeline_events is good

            except json.JSONDecodeError as json_err:
                print(f"Error decoding JSON: {json_err}")
                print(f"Problematic JSON string: {json_part}")
                error_message = "Error: Could not parse AI response as JSON."
                timeline_events = []

        except Exception as e:
            print(f"Error processing historian response: {e}")
            error_message = f"Error processing AI response: {e}"
            timeline_events = []

        print(f"Returning timeline events count: {len(timeline_events)}")

        response_data = {"timelineEvents": timeline_events}
        if error_message:
            response_data["error"] = error_message
            
        # find and add artwork images
        # eric additions !!!
        artwork_pattern = re.compile(r'\*\*(.*?)\*\*') # pattern to find **Artwork Title**
        
        def get_artwork_image(artwork_title):
            # google API key config check
            if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
                return None 

            print(f"Searching for image: {artwork_title}") 

            try:
                search_url = "https://www.googleapis.com/customsearch/v1"
                params = {
                    'key': GOOGLE_API_KEY,
                    'cx': GOOGLE_CSE_ID,
                    'q': artwork_title + " artwork painting", # context for query
                    'searchType': 'image',
                    'num': 1 # just get the top result
                }

                response = requests.get(search_url, params=params, timeout=10) # timeout
                response.raise_for_status() # raise an exception for bad status codes

                data = response.json()

                # check if 'items' exist and has at least one image result
                if 'items' in data and len(data['items']) > 0:
                    image_url = data['items'][0].get('link')
                    
                    # check that image url is valid
                    if image_url:
                        print(f"Found image URL: {image_url}")
                        return image_url
                        
                    else:
                        print(f"No image link found in the first item for: {artwork_title}")
                
                else:
                    print(f"No image items found for: {artwork_title}")

            except requests.exceptions.RequestException as e:
                print(f"Error fetching image for '{artwork_title}': {e}")
            except Exception as e:
                print(f"An unexpected error occurred during image search: {e}")

            return None # return None if search fails or no image found

        for event in timeline_events:
            summary = event.get('detailed_summary', '')
            print(f"Checking summary for artwork: {summary[:100]}...")  # print first 100 chars
            match = artwork_pattern.search(summary)
            
            if match:
                print(f"Artwork pattern matched!") 
                artwork_title = match.group(1).strip()

                image_url = get_artwork_image(artwork_title)  # get image URL for the found artwork

                if image_url:
                    event['artwork_image_url'] = image_url
                   
            else:
                 event['artwork_image_url'] = None # Ensure the key exists even if no artwork found

        return response_data

    except Exception as e:
        print(f"Error during agent execution: {e}")
        # return error structure
        return {"error": f"Error during agent execution: {e}", "timelineEvents": []}