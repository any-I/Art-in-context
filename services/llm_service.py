from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
import os
import openai
from pydantic import BaseModel
from typing import Optional
from huggingface_hub import login
from smolagents import ToolCallingAgent, OpenAIServerModel, PythonInterpreterTool
# for images:
import llm_service_helpers as helpers

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

### Set up for handling different scopes ###

# Mapping each scope (as requested via calls to the API) to:
#   a) the prompt file names corresponding to the scope (if there are multiple prompts, they will be run in
#      sequence on the list of agents defined further below, passing the result of one prompt to the next)
#      "prompts" contain the prompts for the artist name only, while "artwork_prompts" contains prompts for 
#       queries including artwork titles and artwork names
#   b) the type of output the scope is expected to return, either "event" for timeline events or "network" for
#      artist network data - this determines which parser is used to parse the output
#   c) the human-readable version of the scope to be printed in error messages, logging messages, etc.
# An additional "prompt_files" key will be filled below after loading the actual files, being empty if an error 
# occurred while loading the files
scope_info = {
    "political-events": {
        "prompts": ["researcher_prompt"],
        "artwork_prompts": ["researcher_artwork_prompt"],
        "prompt_files": [],
        "artwork_prompt_files": [],
        "output_parse_type": "event",
        "name": "Political / historical"
    },
    "artist-network": {
        "prompts": ["researcher_network_prompt", "historian_network_prompt"],
        "artwork_prompts": [], # artwork title not supported for this scope
        "prompt_files": [],
        "artwork_prompt_files": [],
        "output_parse_type": "network",
        "name": "Artist network"
    },
    "art-movements": {
        "prompts": ["researcher_art_movements_prompt"],
        "artwork_prompts": ["researcher_artwork_art_movements_prompt", "historian_art_movements_prompt"],
        "prompt_files": [],
        "artwork_prompt_files": [],
        "output_parse_type": "event",
        "name": "Art movement"
    },
    "personal-events": {
        "prompts": ["researcher_personal_events_prompt"],
        "artwork_prompts": ["researcher_artwork_personal_events_prompt"],
        "prompt_files": [],
        "artwork_prompt_files": [],
        "output_parse_type": "event",
        "name": "Personal event"
    },
    "economic-events": {
        "prompts": ["researcher_economic_events_prompt"],
        "artwork_prompts": ["researcher_artwork_economic_events_prompt"],
        "prompt_files": [],
        "artwork_prompt_files": [],
        "output_parse_type": "event",
        "name": "Economic event"
    },
    "genre": {
        "prompts": ["researcher_genre_prompt", "historian_genre_prompt"],
        "artwork_prompts": ["researcher_artwork_genre_prompt", "historian_genre_prompt"],
        "prompt_files": [],
        "artwork_prompt_files": [],
        "output_parse_type": "event",
        "name": "Genre"
    },
    "medium": {
        "prompts": ["researcher_medium_prompt", "historian_medium_prompt"],
        "artwork_prompts": ["researcher_artwork_medium_prompt", "historian_medium_prompt"],
        "prompt_files": [],
        "artwork_prompt_files": [],
        "output_parse_type": "event",
        "name": "Medium"
    },
    # will never be called in an API request, but used as a fallback if an unrecognized scope is requested
    "default": {
        "prompts": ["researcher_prompt"],
        "artwork_prompts": ["researcher_artwork_prompt"],
        "prompt_files": [],
        "artwork_prompt_files": [],
        "output_parse_type": "event",
        "name": "Political / historical (DEFAULT)"
    }
}

# Helper to load a list of files into a target_key in the scope info structure
# given a list of the file names in info[source_key]
def load_prompt_files(info: dict[str, any], target_key: str, source_key: str):
    try:
        # loop through all prompt names and try to open their corresponding files, 
        # appending them to the prompt_files list in scope info
        for prompt in info[source_key]:
            newFile = open(prompt + ".txt", "r", encoding="utf-8").read()
            info[target_key].append(newFile) 
    except FileNotFoundError:
        # on error, set prompt_files to empty list and print warning
        info[target_key] = []
        prompt_name = info["name"]
        print("Warning: " + prompt_name + " prompt files (for: " + target_key + ") not found. " + prompt_name + " scope may not function correctly.")

# loading the corresponding prompt files for each scope
for scope, info in scope_info.items():
    load_prompt_files(info, "prompt_files", "prompts")
    load_prompt_files(info, "artwork_prompt_files", "artwork_prompts")

### Set up for parsing different scope output types ###

# Construct parsers to take structured output and convert it to specific JSON objects
# These will be referenced in the scope info below to indicate which how each scope's output
# should be parsed
event_parser = helpers.JSONParser(
    {
        "year": "date",
        "title": "event_title",
        "description": "detailed_summary",
        "location": "location_name",
        "source": "source_url",
        "related": "related_artwork"
    }, # label of information in structured text output to JSON key mapping
    {
        "date": None,
        "event_title": "",
        "detailed_summary": "",
        "location_name": "",
        "latitude": None,
        "longitude": None,
        "source_url": "",
        "related_artwork": ""
    }, # structure of default object
    ["latitude", "longitude", "related_artwork"] # optional fields 
)
network_parser = helpers.JSONParser(
    {
        "name": "connected_entity_name",
        "type": "entity_type",
        "summary": "relationship_summary",
        "duration": "relationship_duration",
        "score": "connection_score",
        "source": "source_url"
    }, # label of information in structured text output to JSON key mapping
    {
        "connected_entity_name": "",
        "entity_type": "",
        "relationship_summary": "",
        "relationship_duration": "",
        "connection_score": 1,
        "source_url": ""
    }, # structure of default object
    [],
    {
        # processing function to convert a string with a number to an actual
        # integer, clamped from 1 to 10
        "connection_score": lambda num: min(max(int(num), 1), 10)
    }
) 
output_types = {
    "event": {
        "parser": event_parser,
        "return_key": "timelineEvents"
    },
    "network": {
        "parser": network_parser,
        "return_key": "networkData"
    }
}

### Set up for agents ###

# construct rate-limited search tool and agents to be used across scopes
rate_limited_search_tool = helpers.RateLimitedSearchTool()
agents = [
    ToolCallingAgent(
        tools=[rate_limited_search_tool, PythonInterpreterTool()],
        model=openAIModel,
        max_steps=5
    ), # researcher
    ToolCallingAgent(
        tools=[PythonInterpreterTool()],
        model=openAIModel,
        max_steps=4
    ) # historian
]

### Request Format Class ###

class AgentsRequest(BaseModel):
    artistName: str
    artworkTitle: Optional[str] = None
    context: list

### Main Logic for Endpoint ###

# Main function to run agents given a specific query string and the name of the key
# in scope_info containing the prompt files to run
# Returns the resultsas well as the type that it should be parsed as (handing it off to
# calling code to process it accordingly)
def query_agents(scope: str, query: str, prompt_files_key: str):
    # reset rate-limited search tool on each run
    rate_limited_search_tool.reset()

    # attempt to find target scope - falling back to default if unrecognized
    target_scope = scope 
    if scope not in scope_info or len(scope_info[target_scope][prompt_files_key]) == 0:
        target_scope = "default" 
        print(f"Warning: Scope '{scope}' not explicitly handled. Using default prompt(s).")
            
    # run agents on as many prompts as is specified (some scopes have 1, some scopes have 2),
    # passing in the result from the previous step
    result = query
    for index, prompt in enumerate(scope_info[target_scope][prompt_files_key]):
        print(f"Running agent with prompt #{index + 1} for scope {target_scope}")
        current_agent = agents[index]
        current_agent.prompt_templates["system_prompt"] = prompt
        result = current_agent.run(result)
    
    # return output type and result string
    return result, scope_info[target_scope]["output_parse_type"]

# Helper function to parse a result string with a given parse type, raising a runtime error
# if the parsed result is not valid or if the parser type is unrecognized, and returning the 
# results otherwise
def parse_into_list(result_str: str, output_type: str):
    if output_type not in output_types:
        raise RuntimeError("No corresponding parser for this output type")
    parser = output_types[output_type]["parser"]
    parsed_list = parser.parse(result_str)
    is_valid, error_message = parser.validate_parsed(parsed_list)
    if not is_valid:
        raise RuntimeError("Error parsing AI response for data (" + error_message + ")")
    return parsed_list

# Helper function to additionally process an event list by searching for artworks referenced
# within an event; modifies the event list in-place so doesn't return it
def find_artworks_for_events(event_list: list[dict[str, any]], artist_name: str):
    for event in event_list:
        if "related_artwork" in event:
            artwork_title = event["related_artwork"]
            if len(artwork_title) > 0 and artwork_title != "<none>":
                image_url = helpers.get_artwork_image(artwork_title, artist_name, GOOGLE_API_KEY, GOOGLE_CSE_ID)
                event["artwork_image_url"] = image_url
            else:
                event["artwork_image_url"] = None 
            del event["related_artwork"] # once done, remove this key from event

### ENDPOINT(S) ###

# health check endpoint for deploymnet
@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {"status": "ok", "service": "llm_service"}

@app.post("/agent")
def run_agents(request: AgentsRequest):
    # Ensure context is a list and not empty before accessing
    if not request.context or not isinstance(request.context, list):
        raise HTTPException(status_code=400, detail="Invalid context provided. Expected a non-empty list.")
    
    # Construct query string, which is of the form <Artist Name: [artwork title] [scope]>
    # or, if no artwork title is provided, <Artist Name: [scope]>
    scope = request.context[0] # Get the primary scope
    query_string = "<" + request.artistName + ": "
    if(request.artworkTitle):
        query_string += "[" + request.artworkTitle + "] "
    query_string += "[" + ", ".join(request.context) + "]>"

    print(f"Running agents for scope: {scope}")
    print(f"Query string: {query_string}")

    try:
        # query the agents for a result list + the type which it should be parsed as
        # we use artwork-title-specific prompts if the request provides the artwork title, and otherwise
        # use a more general prompt only taking into consideration the artist name
        prompt_files_key = "artwork_prompt_files" if request.artworkTitle else "prompt_files"
        result_str, parse_type = query_agents(scope, query_string, prompt_files_key)

        # parse the result string, and if it contains events, search for artworks within it
        result_list = parse_into_list(result_str, parse_type)
        if(parse_type == "event"):
            find_artworks_for_events(result_list, request.artistName)
        
        # return a dictionary with a key depending on the type of data being returned
        response_key = output_types[parse_type]["return_key"]
        return { response_key: result_list }

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
