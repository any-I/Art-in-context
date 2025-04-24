from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

# Get the directory where the script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
print(f"--- LLM Service Starting Up ---")
print(f"Script directory: {script_dir}")

# Construct absolute paths
researcher_prompt_path = os.path.join(script_dir, "researcher_prompt.txt")
historian_prompt_path = os.path.join(script_dir, "historian_prompt.txt")
researcher_network_prompt_path = os.path.join(script_dir, "researcher_network_prompt.txt")
historian_network_prompt_path = os.path.join(script_dir, "historian_network_prompt.txt")
researcher_art_movements_prompt_path = os.path.join(script_dir, "researcher_art_movements_prompt.txt")
historian_art_movements_prompt_path = os.path.join(script_dir, "historian_art_movements_prompt.txt")

### Initialize FastAPI app ###
app = FastAPI()
print("FastAPI app object created.")

# --- CORS Configuration --- START ---
# Replace with your actual S3 website endpoint
# e.g., "http://your-bucket-name.s3-website.us-east-2.amazonaws.com"
s3_frontend_url = "http://Art-Context-Engine-Frontend.s3-website.us-east-2.amazonaws.com" # <-- *** REPLACE WITH YOUR ACTUAL S3 URL ***

origins = [
    s3_frontend_url,
    "http://localhost:3000",  # For local React development (if you use port 3000)
    "http://localhost:8080",  # If you ever proxy locally
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # DEBUG ONLY
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],  # Allow GET, POST and OPTIONS for preflight
    allow_headers=["*"],  # Allow all headers
)
# --- CORS Configuration --- END ---


### Load APIs ###
load_dotenv()
print("Loading environment variables.")
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
print("Setting up agents...")
print(f"Looking for main researcher prompt at: {researcher_prompt_path}")
print(f"Looking for main historian prompt at: {historian_prompt_path}")

try:
    with open(researcher_prompt_path, "r", encoding="utf-8") as f:
        researcher_prompt = f.read()
    with open(historian_prompt_path, "r", encoding="utf-8") as f:
        historian_prompt = f.read()
    print("Successfully loaded main researcher and historian prompts.")
except FileNotFoundError as e:
    print(f"\n*** FATAL ERROR: Could not load main prompt file: {e} ***\n")
    # Raise an exception to ensure startup failure is obvious in logs
    raise RuntimeError(f"Failed to load essential prompt file: {e}")

# Load network prompts
print(f"Looking for researcher network prompt at: {researcher_network_prompt_path}")
print(f"Looking for historian network prompt at: {historian_network_prompt_path}")
try:
    with open(researcher_network_prompt_path, "r", encoding="utf-8") as f:
        researcher_network_prompt = f.read()
    with open(historian_network_prompt_path, "r", encoding="utf-8") as f:
        historian_network_prompt = f.read()
    print("Successfully loaded network prompts.")
except FileNotFoundError:
    print("Warning: Network prompt files not found. Artist network scope may not function correctly.")
    researcher_network_prompt = None
    historian_network_prompt = None

# Load art movement prompts
print(f"Looking for researcher art movements prompt at: {researcher_art_movements_prompt_path}")
print(f"Looking for historian art movements prompt at: {historian_art_movements_prompt_path}")
try:
    with open(researcher_art_movements_prompt_path, "r", encoding="utf-8") as f:
        researcher_art_movements_prompt = f.read()
    with open(historian_art_movements_prompt_path, "r", encoding="utf-8") as f:
        historian_art_movements_prompt = f.read()
    print("Successfully loaded art movement prompts.")
except FileNotFoundError:
    print("Warning: Art movement prompt files not found. Art movements scope may not function correctly.")
    researcher_art_movements_prompt = None
    historian_art_movements_prompt = None

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
print("Defining request models...")

class SummarizeRequest(BaseModel):
    artistName: str
    events: list # containing {'title':'...', 'snippet':'...'} elements

class AgentsRequest(BaseModel):
    artistName: str
    context: list
print("Request models defined.")


### ENDPOINTS ###
print("Defining endpoints...")

@app.get("/")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok", "message": "Art Context Engine API is running!"}
print("Defined / endpoint.")


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
        raise HTTPException(status_code=500, detail=f"Error summarizing events: {e}")
print("Defined /summarize endpoint.")


print("Defining /agent_search endpoint...")
@app.post("/agent_search")
def run_agents(request: AgentsRequest):
    print(f"\n--- Received request for /agent_search ---")
    print(f"Request Body: {request}")
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
        elif scope == 'art-movements' and researcher_art_movements_prompt and historian_art_movements_prompt:
             print("Using ART MOVEMENT prompts")
             researcher_agent.prompt_templates["system_prompt"] = researcher_art_movements_prompt
             historian_agent.prompt_templates["system_prompt"] = historian_art_movements_prompt
        elif scope == 'political-events': # Or other timeline-based scopes handled by default prompts
            print("Using POLITICAL/HISTORICAL prompts")
            researcher_agent.prompt_templates["system_prompt"] = researcher_prompt
            historian_agent.prompt_templates["system_prompt"] = historian_prompt
        else:
            # Fallback or error for unhandled/missing prompts
            print(f"Warning: Scope '{scope}' not explicitly handled or required prompts missing. Using default political/historical prompts as fallback.")
            researcher_agent.prompt_templates["system_prompt"] = researcher_prompt
            historian_agent.prompt_templates["system_prompt"] = historian_prompt
        # ------------------------------------

        researcher_response = researcher_agent.run(query_string)
        print("------ RESEARCHER ------")
        print(researcher_response)
        historian_response_raw = historian_agent.run(researcher_response)
        print("------ HISTORIAN ------")
        print(historian_response_raw)

        # --- Parse Historian Response as JSON ---
        timeline_events = []
        network_data = []
        error_message = None
        parsed_data = None # Initialize parsed_data

        # Attempt to parse the historian's response as JSON
        try:
            # Try to find JSON block even if there's surrounding text
            # Look for a structure starting with '[' and ending with ']'
            json_match = re.search(r'\[.*\]', historian_response_raw, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                parsed_data = json.loads(json_str)
                print(f"Successfully parsed JSON for scope '{scope}'") # Log success
            else:
                print("Warning: Could not find JSON list structure in historian response.")
                error_message = "Historian did not return a valid JSON list structure."
                # Keep parsed_data as None

        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {e}")
            print(f"Raw historian response causing error:\n{historian_response_raw}")
            error_message = f"Failed to parse historian response as JSON: {e}"
            # Ensure response lists are empty on error
            timeline_events = []
            network_data = []
            parsed_data = None # Reset on error
        except Exception as e: # Catch other potential errors during parsing
            print(f"Unexpected error during JSON parsing: {e}")
            error_message = f"An unexpected error occurred during JSON parsing: {e}"
            timeline_events = []
            network_data = []
            parsed_data = None # Reset on error


        # --- Data Validation (only if JSON parsing succeeded) ---
        if parsed_data is not None and error_message is None:
            try:
                # Basic validation: check if it's a list
                if not isinstance(parsed_data, list):
                    print("Warning: Parsed JSON is not a list.")
                    error_message = "Historian response format error: Expected a JSON list."
                    # Reset data if basic structure is wrong
                    timeline_events = []
                    network_data = []
                else:
                    # --- Scope-specific validation ---
                    print(f"Performing validation for scope: {scope}")
                    if scope == 'political-events':
                         # Validate political event structure based on original prompt expectations
                         if all(isinstance(item, dict) and
                                'date' in item and
                                'event_title' in item and          # Check for event_title
                                'detailed_summary' in item and
                                'location_name' in item and        # Check for location_name
                                'latitude' in item and isinstance(item['latitude'], (int, float, type(None))) and # Allow None
                                'longitude' in item and isinstance(item['longitude'], (int, float, type(None))) and # Allow None
                                'source_url' in item for item in parsed_data): # Check for source_url
                             timeline_events = parsed_data
                             print(f"Validated {len(timeline_events)} political events.")
                         else:
                             # Find the first item that fails validation for better logging
                             failing_item = next((item for item in parsed_data if not (
                                isinstance(item, dict) and
                                'date' in item and
                                'event_title' in item and
                                'detailed_summary' in item and
                                'location_name' in item and
                                'latitude' in item and isinstance(item.get('latitude'), (int, float, type(None))) and # Use .get for safety
                                'longitude' in item and isinstance(item.get('longitude'), (int, float, type(None))) and # Use .get for safety
                                'source_url' in item
                             )), None) # Provide None if all pass somehow (shouldn't happen here)
                             print(f"Warning: Parsed list items have incorrect political event structure.")
                             print(f"Example failing item: {failing_item}") # Log the specific item causing issues
                             error_message = "Error: AI response format incorrect (missing required fields or wrong types for political events)."
                             timeline_events = []
                    elif scope == 'artist-network':
                         # Validate artist network structure based on likely prompt expectations
                         if all(isinstance(item, dict) and
                                'connected_entity_name' in item and
                                'entity_type' in item and
                                'relationship_summary' in item and
                                # 'relationship_duration' in item and # Optional? Comment out if not always required
                                'connection_score' in item and isinstance(item['connection_score'], (int, float)) and # Ensure score is numeric
                                'source_url' in item for item in parsed_data): # Optional? Add check if needed
                            network_data = parsed_data
                            print(f"Validated {len(network_data)} network connections.")
                         else:
                            # Find the first item that fails validation for better logging
                             failing_item = next((item for item in parsed_data if not (
                                isinstance(item, dict) and
                                'connected_entity_name' in item and
                                'entity_type' in item and
                                'relationship_summary' in item and
                                # 'relationship_duration' in item and # Mirror check above
                                'connection_score' in item and isinstance(item.get('connection_score'), (int, float)) and # Use .get for safety
                                'source_url' in item # Mirror check above
                             )), None)
                             print("Warning: Parsed list items have incorrect network structure.")
                             print(f"Example failing item: {failing_item}") # Log the specific item causing issues
                             error_message = "Error: AI response format incorrect (missing required fields or wrong types for network data)."
                             network_data = []
                    elif scope == 'art-movements':
                         # Validate art movement structure based on the prompt (date, summary, detailed_summary)
                         if all(isinstance(item, dict) and
                                'date' in item and             # Expecting 'date'
                                'summary' in item and          # Expecting 'summary'
                                'detailed_summary' in item for item in parsed_data): # Expecting 'detailed_summary'
                             timeline_events = parsed_data
                             print(f"Validated {len(timeline_events)} art movement events.")
                         else:
                             print("Warning: Parsed list items have incorrect art movement structure (expected date, summary, detailed_summary).")
                             # This specific error message is sent to the frontend
                             error_message = "Error: AI response format incorrect (missing required fields or wrong types for art movement events)."
                             timeline_events = []
                    else:
                        # Handle unknown scopes - maybe treat as error or default?
                        print(f"Warning: Validation not defined for scope '{scope}'. No data will be returned.")
                        error_message = f"Validation logic not implemented for scope: {scope}"
                        timeline_events = []
                        network_data = []
            except Exception as e: # Catch errors during validation phase
                 print(f"Unexpected error during data validation: {e}")
                 error_message = f"An unexpected error occurred during data validation: {e}"
                 timeline_events = []
                 network_data = []
        # Ensure data lists are empty if an error occurred at any point
        if error_message:
            timeline_events = []
            network_data = []

        # --- Construct final response ---
        if scope in ['political-events', 'art-movements']:
            response_data = {"timelineEvents": timeline_events}
            if error_message:
                response_data["error"] = error_message
            
            # --- Conditional Image Search (Only for Political Events) --- 
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
                summary_to_search = event.get('detailed_summary', '') if scope == 'art-movements' else event.get('summary', '')
                # print(f"Checking summary for artwork: {summary_to_search[:100]}...") # Optional: reduce verbosity
                match = artwork_pattern.search(summary_to_search) # Search the chosen summary

                if match:
                    print(f"Artwork pattern matched in summary!") 
                    artwork_title = match.group(1).strip()
                    image_url = get_artwork_image(artwork_title)
                    event['artwork_image_url'] = image_url # Add key if found
                else:
                    event['artwork_image_url'] = None # Ensure the key exists even if no artwork found
            # --------------------------------------------------------------

        elif scope == 'artist-network':
            response_data = {"networkData": network_data}
            if error_message:
                response_data["error"] = error_message
        else:
            # Fallback for unhandled scopes
            response_data = {"error": error_message if error_message else f"Unhandled scope: {scope}"} 

        print(f"Final response data keys: {list(response_data.keys())}")
        return response_data

    except HTTPException as http_err:
        # Re-raise HTTP exceptions to be handled by FastAPI
        raise http_err 
    except Exception as e:
        print(f"Error during agent execution: {e}")
        # return error structure, ensuring keys match potential frontend expectation even on error
        error_resp = {"error": f"Error during agent execution: {e}"}
        if scope in ['political-events', 'art-movements']:
            error_resp["timelineEvents"] = []
        elif scope == 'artist-network':
            error_resp["networkData"] = []
        return error_resp

# --- Uvicorn startup (if running directly) ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)