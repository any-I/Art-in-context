from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from dotenv import load_dotenv
import os
import openai
from pydantic import BaseModel
from huggingface_hub import login
from smolagents import ToolCallingAgent, OpenAIServerModel, PythonInterpreterTool
import json
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

### Set up for AGENTS ###

# Mapping each scope (as requested via calls to the API) to:
#   a) the prompt file names corresponding to the scope (if there are multiple prompts, they will be run in
#      sequence on the list of agents defined further below, passing the result of one prompt to the next)
#   b) the type of output the scope is expected to return, either "event" for timeline events or "network" for
#      artist network data - this determines which parser is used to parse the output
#   c) the human-readable version of the scope to be printed in error messages, logging messages, etc.
# An additional "prompt_files" key will be filled below after loading the actual files, being empty if an error 
# occurred while loading the files
scope_info = {
    "political-events": {
        "prompts": ["researcher_prompt"],
        "prompt_files": [],
        "output_parse_type": "event",
        "name": "Political / historical"
    },
    "artist-network": {
        "prompts": ["researcher_network_prompt", "historian_network_prompt"],
        "prompt_files": [],
        "output_parse_type": "network",
        "name": "Artist network"
    },
    "art-movements": {
        "prompts": ["researcher_art_movements_prompt"],
        "prompt_files": [],
        "output_parse_type": "event",
        "name": "Art movement"
    },
    "personal-events": {
        "prompts": ["researcher_personal_events_prompt"],
        "prompt_files": [],
        "output_parse_type": "event",
        "name": "Personal event"
    },
    "economic-events": {
        "prompts": ["researcher_economic_events_prompt"],
        "prompt_files": [],
        "output_parse_type": "event",
        "name": "Economic event"
    },
    "genre": {
        "prompts": ["researcher_genre_prompt", "historian_genre_prompt"],
        "prompt_files": [],
        "output_parse_type": "event",
        "name": "Genre"
    },
    "medium": {
        "prompts": ["researcher_medium_prompt", "historian_medium_prompt"],
        "prompt_files": [],
        "output_parse_type": "event",
        "name": "Medium"
    },
    # will never be called in an API request, but used as a fallback if an unrecognized scope is requested
    "default": {
        "prompts": ["researcher_prompt"],
        "prompt_files": [],
        "output_parse_type": "event",
        "name": "Political / historical (DEFAULT)"
    }
}

# loading the corresponding prompt files for each scope
for scope, info in scope_info.items():
    try:
        # loop through all prompt names and try to open their corresponding files, 
        # appending them to the prompt_files list in scope info
        for prompt in info["prompts"]:
            newFile = open(prompt + ".txt", "r", encoding="utf-8").read()
            info["prompt_files"].append(newFile) 
    except FileNotFoundError:
        # on error, set prompt_files to empty list and print warning
        info["prompt_files"] = []
        prompt_name = info["name"]
        print("Warning: " + prompt_name + " prompt files not found. " + prompt_name + " scope may not function correctly.")

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

# construct parsers to take structured output and convert it to specific JSON objects
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
async def run_agents(request: AgentsRequest):
    return StreamingResponse(
        run_agents_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable proxy buffering
        }
    )

async def run_agents_stream(request: AgentsRequest):
    try:
        print(AgentsRequest)
        yield f"data: {json.dumps({'status': 'starting', 'message': f'Starting analysis for {request.artistName}'})}\n\n"

        # Ensure context is a list and not empty before accessing
        if not request.context or not isinstance(request.context, list):
            yield f"data: {json.dumps({'status': 'error', 'error': 'Invalid context provided'})}\n\n"
            return        
        scope = request.context[0] # Get the primary scope
        query_string = "<" + request.artistName + ": [" + ", ".join(request.context) + "]>"
        print(f"Running agents for scope: {scope}")
        print(f"Query string: {query_string}")

        yield f"data: {json.dumps({'status': 'processing', 'message': 'Running researcher agent...'})}\n\n"
        
        rate_limited_search_tool.reset()

        # get "target scope" - if scope is in scope_info and has a non-empty prompt file list,
        # use the given prompt; otherwise default to the "default" scope and its prompt
        target_scope = scope 
        if scope not in scope_info or len(scope_info[target_scope]["prompt_files"]) == 0:
            target_scope = "default" 
            print(f"Warning: Scope '{scope}' not explicitly handled or network prompts missing. Using default prompt(s).")
            
        # run agents on as many prompts as is specified (some scopes have 1, some scopes have 2),
        # passing in the result from the previous step
        result = query_string
        for index, prompt in enumerate(scope_info[target_scope]["prompt_files"]):
            print(f"Running agent with prompt #{index + 1} for scope {target_scope}")
            agent_name = "Researcher" if index == 0 else "Historian"
            yield f"data: {json.dumps({'status': 'processing', 'message': f'Running {agent_name} agent...'})}\n\n"
            current_agent = agents[index]
            current_agent.prompt_templates["system_prompt"] = prompt
            result = current_agent.run(result)

        yield f"data: {json.dumps({'status': 'processing', 'message': 'Parsing results...'})}\n\n"
            
        # parse and return the final result - either an event result or a network result
        # handle event results
        if scope_info[target_scope]["output_parse_type"] == "event":
            event_list = event_parser.parse(result)
            is_valid, error_message = event_parser.validate_parsed(event_list)
            if not is_valid:
                yield f"data: {json.dumps({'status': 'error', 'error': f'Parsing error: {error_message}'})}\n\n"
                return
            
            # if valid, also do artwork search for events in the list
            if len(event_list) > 0 and "related_artwork" in event_list[0]:
                yield f"data: {json.dumps({'status': 'processing', 'message': 'Searching for artwork images...'})}\n\n"

                for event in event_list:
                    artwork_title = event["related_artwork"]
                    if len(artwork_title) > 0 and artwork_title != "<none>":
                        image_url = helpers.get_artwork_image(artwork_title, request.artistName, GOOGLE_API_KEY, GOOGLE_CSE_ID)
                        event["artwork_image_url"] = image_url
                    else:
                        event["artwork_image_url"] = None 
                    del event["related_artwork"] # once done, remove this key from event

            # return response
            response_data = {"timelineEvents": event_list}
            # return response_data
            yield f"data: {json.dumps({'status': 'complete', 'data': response_data})}\n\n"
            
        # handle network results
        elif scope_info[target_scope]["output_parse_type"] == "network":
            network_list = network_parser.parse(result)
            is_valid, error_message = network_parser.validate_parsed(network_list)
            if not is_valid:
                yield f"data: {json.dumps({'status': 'error', 'error': f'Parsing error: {error_message}'})}\n\n"
                return
            response_data = {"networkData": network_list}
            # return response_data
            yield f"data: {json.dumps({'status': 'complete', 'data': response_data})}\n\n"

    except Exception as e:
        print(f"Error during agent execution: {e}")
        error_data = {
            'status': 'error',
            'error': str(e),
            'networkData': [] if scope == 'artist-network' else None,
            'timelineEvents': [] if scope != 'artist-network' else None
        }
        yield f"data: {json.dumps(error_data)}\n\n"