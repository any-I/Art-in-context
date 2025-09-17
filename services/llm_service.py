from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
import os
import openai
import json
from pydantic import BaseModel
from huggingface_hub import login
from smolagents import CodeAgent, DuckDuckGoSearchTool, ToolCallingAgent, OpenAIServerModel, PythonInterpreterTool
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
# Mapping each scope (as requested via calls to the API) to:
#   a) the prompt file name (prefixed with researcher_/historian_ and postfixed with _prompt.txt)
#      corresponding to the scope, and
#   b) the human-readable version of the scope to be printed in error messages, logging messages, etc.
scope_info = {
    "artist-network": {
        "prompt": "network",
        "name": "Artist network"
    },
    "art-movements": {
        "prompt": "art_movements",
        "name": "Art movement"
    },
    "personal-events": {
        "prompt": "personal_events",
        "name": "Personal event"
    },
    "economic-events": {
        "prompt": "economic_events",
        "name": "Economic event"
    },
    "genre": {
        "prompt": "genre",
        "name": "Genre"
    },
    "medium": {
        "prompt": "medium",
        "name": "Medium"
    }
}
researcher_prompt_files = {}
historian_prompt_files = {}
for scope, prompt_info in scope_info.items():
    try:
        researcher_file_name = "researcher_" + prompt_info["prompt"] + "_prompt.txt"
        historian_file_name = "historian_" + prompt_info["prompt"] + "_prompt.txt"
        researcher_prompt_files[scope] = open(researcher_file_name, "r", encoding="utf-8").read()
        historian_prompt_files[scope] = open(historian_file_name, "r", encoding="utf-8").read()
    except FileNotFoundError:
        prompt_name = prompt_info["name"]
        print("Warning: " + prompt_name + " prompt files not found. " + prompt_name + " scope may not function correctly.")
        researcher_prompt_files[scope] = None # Set to None or a default fallback prompt
        historian_prompt_files[scope] = None

# Additional, standalone prompts to use when calling LLM directly, not using Huggingface agents
# Load genre prompt
try:
    genre_finder_prompt = open("genre_finder_prompt.txt", "r", encoding="utf-8").read()
except FileNotFoundError:
    print("Warning: Genre prompt file not found. Genre scope may not function correctly.")
    genre_finder_prompt = None

# Load medium prompt (New)
try:
    medium_finder_prompt = open("medium_finder_prompt.txt", "r", encoding="utf-8").read()
except FileNotFoundError:
    print("Warning: Medium prompt file not found. Medium scope may not function correctly.")
    medium_finder_prompt = None

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
    max_steps=5
)
researcher_agent.prompt_templates["system_prompt"] = researcher_prompt

historian_agent = ToolCallingAgent(
    tools=[PythonInterpreterTool()],
    model=openAIModel,
    max_steps=4
)
historian_agent.prompt_templates["system_prompt"] = historian_prompt

def parse_events_to_JSON(str):
    # regex patterns to use to 1) identify the start of another event (in the form #. at the start
    # of a line) and 2) to identify the event label + value (in the form [#.] **label:** value, with
    # flexibility in the **s, the presence of a number, and the presence of a colon)
    event_start_re = re.compile(r"\s*\d+\.")
    event_re = re.compile(r"\s*(?:\d+\.)?\s*\*{0,2}([^:']+):?\*{0,2}\s*(.+)")
    url_re = re.compile(r"(?:https?:\/\/)?(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)")

    # if the label for the information contains any of these words, case insensitive, put 
    # the content into the JSON object with the corresponding key
    # i.e. for a line that contains 'year,' put the information for the year into the JSON
    # object with key "date"
    infoNameToKey = {
        "year": "date",
        "title": "event_title",
        "description": "detailed_summary",
        "location": "location_name",
        "source": "source_url"
    }

    # construct final event list by going line-by-line
    event_list = []
    current_key = ""
    for line in str.splitlines():
        # adding a new event if we've reached a new event in the list (detected number
        # at start of the line)
        if re.match(event_start_re, line):
            event_list.append({
                "date": None,
                "event_title": "",
                "detailed_summary": "",
                "location_name": "",
                "latitude": None,
                "longitude": None,
                "source_url": ""
            })
        
        # try to match the line to the <info label>: <info> pattern
        matches = re.match(event_re, line)
        if matches and len(event_list) > 0: 
            # find the proper JSON key matching the info label
            info_label = matches.group(1).strip().lower()
            json_label = ""
            for sub_label, actual_label in infoNameToKey.items():
                if sub_label in info_label:
                    json_label = actual_label
                    break
            # if we can't find a label, we assume the line is a continuation
            # of the previous event, so we just add the entire match (stripped
            # of leading/trailing whitespace) to the current info
            whole_match = matches.group(0).strip()
            if json_label == "":
                # as long as current key is valid and the match isn't just whitespace,
                # add it onto the current key info
                whole_match = matches.group(0).strip()
                if current_key in event_list[-1] and whole_match != "":
                    event_list[-1][current_key] += " " + whole_match
                # reset the key we're working on if we get a line of just whitespace
                elif whole_match == "":
                    current_key = ""
                continue
            # otherwise, get actual info, stripping extra info from the url
            # as is necessary (sometimes the url is wrapped within
            # parentheses, so an extra closing ) must be removed)
            info = matches.group(2).strip()
            if json_label == "source_url":
                url = re.search(url_re, info)
                if url:
                    parsed_url = url.group(0)
                    if parsed_url[-1] == ')':
                        info = parsed_url[:-1]
                    else:
                        info = parsed_url
            # update the current key/value we're constructing with this info
            current_key = json_label 
            event_list[-1][current_key] = info
    return event_list

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
        if scope == 'political-events':
            print("Using POLITICAL/HISTORICAL prompts")
            researcher_agent.prompt_templates["system_prompt"] = researcher_prompt
            historian_agent.prompt_templates["system_prompt"] = historian_prompt
        elif scope in scope_info and researcher_prompt_files[scope] and historian_prompt_files[scope]:
            print("Using " + scope_info[scope]["name"].upper() + " prompts")
            researcher_agent.prompt_templates["system_prompt"] = researcher_prompt_files[scope]
            historian_agent.prompt_templates["system_prompt"] = historian_prompt_files[scope]
        
        # Direct LLM call for Genre
        elif scope == 'Genre' and genre_finder_prompt:
            print("Using GENRE prompts")
            try:
                # Format the simple prompt
                formatted_prompt = genre_finder_prompt.format(query=request.artistName)

                # Direct call to LLM
                completion = openAIClient.chat.completions.create(
                    model="gpt-4-turbo", # Or your preferred model
                    messages=[
                        {"role": "system", "content": "You are an art historian assistant.", "content": "Respond with ONLY the primary genre name."}, # System prompt reinforcement
                        {"role": "user", "content": formatted_prompt}
                    ],
                    temperature=0.1 # Low temperature for factual recall
                )
                genre_result = completion.choices[0].message.content.strip()
                print(f"Genre result from LLM: {genre_result}")
                # Return the specific simple format
                return {"genre": genre_result}
            except Exception as e:
                print(f"Error during direct LLM call for scope '{scope}': {e}")
                return {"error": f"Failed to retrieve genre for {request.artistName}"}

        # Direct LLM call for Medium (New)
        elif scope == 'artist-medium' and medium_finder_prompt: 
            print("Using MEDIUM prompt for direct LLM call")
            try:
                formatted_prompt = medium_finder_prompt.format(query=request.artistName)
                completion = openAIClient.chat.completions.create(
                    model="gpt-4", # Or your preferred fast model
                    messages=[
                        {"role": "system", "content": "You are an art historian assistant. Respond with ONLY the primary, specific artistic medium (e.g., 'oil paints', 'bronze sculpture')."},
                        {"role": "user", "content": formatted_prompt}
                    ],
                    temperature=0.1
                )
                medium_result = completion.choices[0].message.content.strip()
                print(f"Medium result from LLM: {medium_result}")
                return {"medium": medium_result} 
            except Exception as e:
                print(f"Error during direct LLM call for scope '{scope}': {e}")
                return {"error": f"Failed to retrieve medium for {request.artistName}"}

        else:
            # Handle other scopes or fallback if network prompts are missing
            print(f"Warning: Scope '{scope}' not explicitly handled or network prompts missing. Using default political/historical prompts.")
            researcher_agent.prompt_templates["system_prompt"] = researcher_prompt
            historian_agent.prompt_templates["system_prompt"] = historian_prompt
        # ------------------------------------

        researcher_response = researcher_agent.run(query_string)
        print("------ RESEARCHER ------")
        print(researcher_response)
        if scope != 'personal-events' and scope != 'economic-events':
            historian_response_raw = historian_agent.run(researcher_response)
        else:
            historian_response_raw = parse_events_to_JSON(researcher_response)
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
                except json.JSONDecodeError as json_err:
                    print(f"Error decoding JSON: {json_err}")
                    print(f"Problematic JSON string: {json_part}")
                    error_message = f"Error: AI response was not valid JSON: {json_err}"
                    parsed_data = [] # Ensure empty list on JSON error
            else:
                print(f"Warning: Historian response is of unexpected type: {type(historian_response_raw)}")
                error_message = "Error: AI response was not in the expected format (string or list)."
                parsed_data = []

            # === Handle potential extra list wrapping by LLM for timeline scopes ===
            if not error_message and scope in ['political-events', 'art-movements', 'personal-events', 'economic-events', 'genre', 'medium']:
                if isinstance(parsed_data, list) and len(parsed_data) > 0 and isinstance(parsed_data[0], list):
                    print("Warning: Detected nested list structure, extracting inner list.")
                    parsed_data = parsed_data[0] # Use the inner list
                elif not isinstance(parsed_data, list):
                     # If it's not a list at all after parsing, log a warning.
                     # The main validation will catch this and set an error message.
                     print(f"Warning: Parsed data for timeline scope '{scope}' is not a list.")

            # === SCOPE-SPECIFIC VALIDATION AND DATA EXTRACTION ===
            if not error_message: # Only validate if parsing was successful
                if scope in ['political-events', 'art-movements', 'personal-events', 'economic-events', 'genre', 'medium']: 
                    # Validate common timeline structure for all timeline scopes
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
            if scope in ['political-events', 'art-movements', 'personal-events', 'economic-events', 'genre', 'medium']: 
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