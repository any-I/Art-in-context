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

# Load network prompts
try:
    researcher_network_prompt = open("researcher_network_prompt.txt", "r", encoding="utf-8").read()
    historian_network_prompt = open("historian_network_prompt.txt", "r", encoding="utf-8").read()
except FileNotFoundError:
    print("Warning: Network prompt files not found. Artist network scope may not function correctly.")
    researcher_network_prompt = None # Set to None or a default fallback prompt
    historian_network_prompt = None

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
    # Ensure context is a list and not empty before accessing
    if not request.context or not isinstance(request.context, list):
        raise HTTPException(status_code=400, detail="Invalid context provided. Expected a non-empty list.")
        
    scope = request.context[0] # Get the primary scope
    query_string = "<" + request.artistName + ": [" + ", ".join(request.context) + "]>"
    print(f"Running agents for scope: {scope}")
    print(f"Query string: {query_string}")

    try:
        rate_limited_search_tool.reset()

        # --- Conditional Prompt Assignment ---
        if scope == 'artist-network' and researcher_network_prompt and historian_network_prompt:
            print("Using NETWORK prompts")
            researcher_agent.prompt_templates["system_prompt"] = researcher_network_prompt
            historian_agent.prompt_templates["system_prompt"] = historian_network_prompt
        elif scope == 'political-events': # Or other timeline-based scopes
            print("Using POLITICAL/HISTORICAL prompts")
            researcher_agent.prompt_templates["system_prompt"] = researcher_prompt
            historian_agent.prompt_templates["system_prompt"] = historian_prompt
        elif scope == 'art-movements': # Or other timeline-based scopes
            print("Using POLITICAL/HISTORICAL prompts")
            researcher_agent.prompt_templates["system_prompt"] = researcher_prompt
            historian_agent.prompt_templates["system_prompt"] = historian_prompt
        else:
            # Handle other scopes or fallback if network prompts are missing
            print(f"Warning: Scope '{scope}' not explicitly handled or network prompts missing. Using default political/historical prompts.")
            researcher_agent.prompt_templates["system_prompt"] = researcher_prompt
            historian_agent.prompt_templates["system_prompt"] = historian_prompt
        # ------------------------------------

        researcher_response = researcher_agent.run(query_string)
        print("------ RESEARCHER ------")
        print(researcher_response)
        historian_response_raw = historian_agent.run(researcher_response)
        print("------ HISTORIAN ------")
        print(historian_response_raw)

        # --- Parse Historian Response ---
        error_message = None
        timeline_events = []
        network_data = []
        try:
            # Attempt to parse the raw response (expecting string or list)
            if isinstance(historian_response_raw, list):
                print("Historian response is already a list.")
                parsed_data = historian_response_raw
            elif isinstance(historian_response_raw, str):
                print("Historian response is a string. Parsing JSON.")
                json_part = historian_response_raw.strip()
                if json_part.startswith("```json"):
                    json_part = json_part[len("```json"):].strip()
                if json_part.endswith("```"):
                    json_part = json_part[:-len("```")].strip()
                
                # Attempt to fix common missing comma errors between JSON objects in a list
                try:
                    json_part = re.sub(r'}\s*\{', '}, {', json_part)
                except Exception as regex_err:
                    print(f"Warning: Regex correction failed: {regex_err}") # Log if regex fails, but proceed

                try:
                    parsed_data = json.loads(json_part)
                    if not isinstance(parsed_data, list):
                         print("Warning: Parsed JSON is not a list.")
                         error_message = "Error: AI response format incorrect (expected a list)."
                         parsed_data = [] # Reset if not a list
                except json.JSONDecodeError as json_err:
                    print(f"Error decoding JSON: {json_err}")
                    print(f"Problematic JSON string: {json_part}")
                    error_message = f"Error: Could not parse AI response as JSON. Details: {json_err}"
                    parsed_data = []
            else:
                print(f"Warning: Historian response is of unexpected type: {type(historian_response_raw)}")
                error_message = "Error: AI response was not in the expected format (string or list)."
                parsed_data = []

            # === SCOPE-SPECIFIC VALIDATION AND DATA EXTRACTION ===
            # Reverted: Validate structure within the parsed_data list for timeline scopes
            if not error_message: # Only validate if parsing was successful
                if scope == 'political-events' or scope == 'art-movements':
                    # Validate common timeline structure for both scopes
                    if isinstance(parsed_data, list) and all(isinstance(item, dict) and
                           'date' in item and
                           'event_title' in item and
                           'detailed_summary' in item and
                           'location_name' in item and
                           'latitude' in item and isinstance(item['latitude'], (int, float, type(None))) and # Allow None
                           'longitude' in item and isinstance(item['longitude'], (int, float, type(None))) and # Allow None
                           'source_url' in item for item in parsed_data):
                        timeline_events = parsed_data # Assign validated list
                        print(f"Validated {len(timeline_events)} timeline events for scope '{scope}'.")
                    else:
                        print(f"Warning: Parsed list items have incorrect timeline structure for scope '{scope}'.")
                        error_message = f"Error: AI response format incorrect for scope '{scope}' (missing required fields or wrong types)."
                        timeline_events = [] # Ensure empty on validation failure

                elif scope == 'artist-network':
                    # Validate network structure (ensure connection_score check remains if needed)
                    if isinstance(parsed_data, list) and all(isinstance(item, dict) and
                           'connected_entity_name' in item and
                           'entity_type' in item and
                           'relationship_summary' in item and
                           'relationship_duration' in item and
                           'connection_score' in item and isinstance(item['connection_score'], (int, float)) and
                           'source_url' in item for item in parsed_data):
                        network_data = parsed_data
                        print(f"Validated {len(network_data)} network connections.")
                    else:
                        print("Warning: Parsed list items have incorrect network structure.")
                        error_message = "Error: AI response format incorrect for network data (missing fields or wrong types)."
                        network_data = [] # Ensure empty on validation failure
                else:
                     # Handle unknown scopes
                    print(f"Warning: Validation not defined for scope '{scope}'.")
                    # Keep error_message as None or set a specific one if needed
                    # error_message = f"Error: Unknown scope '{scope}' received for validation."
                    # Ensure data lists remain empty
                    timeline_events = []
                    network_data = []
            # ---------------------------------------------------------------

            # --- Image Search for Timeline Events (if any extracted) ---
            # Refactored: Moved outside scope-specific block to apply to any timeline scope
            if timeline_events: # Check if timeline_events list is populated
                print(f"Checking {len(timeline_events)} timeline events for artwork images...")
                artwork_pattern = re.compile(r'\*\*(.*?)\*\*') # pattern to find **Artwork Title**
                
                def get_artwork_image(artwork_title):
                    # google API key config check
                    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
                        print("Google API Key/CSE ID not configured, skipping image search.")
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
                    # print(f"Checking summary for artwork: {summary[:100]}...") # Optional: reduce verbosity
                    match = artwork_pattern.search(summary)
                    
                    if match:
                        print(f"Artwork pattern matched in summary!") 
                        artwork_title = match.group(1).strip()
                        image_url = get_artwork_image(artwork_title)
                        event['artwork_image_url'] = image_url # Add key if found
                    else:
                        event['artwork_image_url'] = None # Ensure the key exists even if no artwork found
            # --------------------------------------------------------------

            # --- CONSTRUCT FINAL RESPONSE --- 
            response_data = {}
            if scope == 'political-events':
                response_data = {"timelineEvents": timeline_events}
                # Add warning if validation failed but we still proceed (e.g., if fallback logic existed)
                # For now, if error_message is set, timeline_events should be empty, 
                # but we can add the message just in case.
                if error_message:
                    response_data["error"] = error_message 

            elif scope == 'art-movements': 
                response_data = {"timelineEvents": timeline_events}
                if error_message:
                    response_data["error"] = error_message 

            elif scope == 'artist-network':
                response_data = {"networkData": network_data}
            else:
                # Fallback for unhandled scopes
                response_data = {"error": error_message if error_message else f"Unhandled scope: {scope}"} 

            print(f"Final response data keys: {list(response_data.keys())}")
            return response_data

        except Exception as e:
            print(f"Error processing historian response: {e}")
            # return error structure, ensuring keys match potential frontend expectation even on error
            error_resp = {"error": f"Error processing AI response: {e}"}
            if scope == 'artist-network':
                error_resp["networkData"] = []
            else: # Default or political-events
                error_resp["timelineEvents"] = []
            return error_resp

    except HTTPException as http_err:
        # Re-raise HTTP exceptions to be handled by FastAPI
        raise http_err 
    except Exception as e:
        print(f"Error during agent execution: {e}")
        # return error structure, ensuring keys match potential frontend expectation even on error
        error_resp = {"error": f"Error during agent execution: {e}"}
        if scope == 'artist-network':
            error_resp["networkData"] = []
        else: # Default or political-events
            error_resp["timelineEvents"] = []
        return error_resp