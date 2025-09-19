import re
import requests
from smolagents import DuckDuckGoSearchTool

#### SEARCH TOOLS
SEARCH_CALL_LIMIT = 4  # Maximum number of searches per query
class RateLimitedSearchTool(DuckDuckGoSearchTool):
    name = "rate_limited_search_tool"
    description = """Searches the web for the information given in the query, and 
    returns several links as well as a brief summary of the information found at those links.
    Limits the number of searches to 4 searches."""
    inputs = {
        "query": {
            "type": "string",
            "description": "The search query you will perform on the search engine"
        }
    }
    output_type = "string"
    def __init__(self):
        super().__init__()
        self.call_count = 0
    def forward(self, query):
        if self.call_count >= SEARCH_CALL_LIMIT:
            print(f"Search limit hit. Skipping query: {query}")
            return "No additional searches allowed due to rate limits. Continue to next step and DO NOT ATTEMPT TO SEARCH AGAIN."
        self.call_count += 1
        try:
            return super().forward(query)
        except Exception as e:
            print(e)
            return "Could not search. Continue to the next step and DO NOT ATTEMPT TO SEARCH AGAIN."
    def reset(self):  # Reset after each full query cycle
        self.call_count = 0

#### PARSING HELPERS

# able to take structured string output and convert it to a JSON timeline event
# useful for political/historical events, personal events, and economic events
# technically speaking genre/art movement should also work too - but need to figure out a way to make this work with the historian response for them
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

# function to search for artwork image URL given title
def get_artwork_image(artwork_title, GOOGLE_API_KEY, GOOGLE_CSE_ID):
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