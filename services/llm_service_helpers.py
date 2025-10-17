import re
import requests
import copy
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
            return "No additional searches allowed due to rate limits. Call the final_answer tool and DO NOT ATTEMPT TO SEARCH AGAIN."
        self.call_count += 1
        try:
            return super().forward(query)
        except Exception as e:
            print(e)
            return "Could not search. Call the final_answer tool and DO NOT ATTEMPT TO SEARCH AGAIN."
    def reset(self):  # Reset after each full query cycle
        self.call_count = 0

#### PARSING HELPERS
class JSONParser:
    # patterns to search for - the start of a new entry, a <label>: <info> field, and a URL pattern
    obj_start_re = re.compile(r"\s*\d+\.")
    obj_field_re = re.compile(r"\s*(?:\d+\.)?\s*\*{0,2}([^:']+):?\*{0,2}\s*(.+)")
    url_re = re.compile(r"(?:https?:\/\/)?(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=\-]*)")

    def __init__(self, name_to_key, default_object, optional_fields = None, special_labels = None):
        # Name_to_key is a dictionary that maps textual labels of data -> the name of the key in
        # the JSON object. For instance, it'll map textual info labeled with "Year(s)" to "date"
        self.name_to_key = name_to_key

        # Default object specifies the default structure of any parsed object in the list
        self.default_obj = default_object 

        # Optional fields specify which fields don't need to change from the default for an
        # object to still be considered valid; this field is optional
        self.optional_fields = optional_fields if optional_fields else []

        # Special labels is a dict mapping the JSON key to a lambda function that does any
        # additional processing necessary for the information before assigning it as a value
        # in the JSON object
        self.special_labels = special_labels if special_labels else {}

    def parse(self, str):
        results = []
        current_key = ""
        for line in str.splitlines():
            # adding a new event if we've reached a new event in the list (detected number
            # at start of the line) (note that we need a copy of the default object
            # so we're not changing the default object itself)
            if re.match(JSONParser.obj_start_re, line):
                results.append(copy.copy(self.default_obj))
        
            # try to match the line to the <info label>: <info> pattern
            matches = re.match(JSONParser.obj_field_re, line)
            if matches and len(results) > 0: 
                # find the proper JSON key matching the info label
                info_label = matches.group(1).strip().lower()
                json_label = ""
                for sub_label, actual_label in self.name_to_key.items():
                    if sub_label in info_label:
                        json_label = actual_label
                        break
                # if we can't find a label, we assume the line is a continuation
                # of the previous object, so we just add the entire match (stripped
                # of leading/trailing whitespace) to the current info
                whole_match = matches.group(0).strip()
                if json_label == "":
                    # as long as current key is valid and the match isn't just whitespace,
                    # add it onto the current key info
                    whole_match = matches.group(0).strip()
                    if current_key in results[-1] and whole_match != "":
                        results[-1][current_key] += " " + whole_match
                    # reset the key we're working on if we get a line of just whitespace
                    elif whole_match == "":
                        current_key = ""
                    continue
                # otherwise, get actual info, stripping extra info from the url
                # as is necessary (sometimes the url is wrapped within
                # parentheses, so an extra closing ) must be removed)
                info = matches.group(2).strip()
                if json_label == "source_url":
                    url = re.search(JSONParser.url_re, info)
                    if url:
                        parsed_url = url.group(0)
                        if parsed_url[-1] == ')':
                            info = parsed_url[:-1]
                        else:
                            info = parsed_url
                elif json_label in self.special_labels:
                    # execute the corresponding lambda to process the info
                    info = self.special_labels[json_label](info) 
                # update the current key/value we're constructing with this info
                current_key = json_label 
                results[-1][current_key] = info
        return results

    # loops through given list and returns a pair, the first value being a boolean indicating
    # whether something is valid, and the second giving any optional error info
    def validate_parsed(self, parsed_list):
        for obj in parsed_list:
            for key, val in obj.items():
                if key not in self.default_obj:
                    return False, "Unrecognized key in object"
                if val == self.default_obj[key] and key not in self.optional_fields:
                    return False, "Default value still present for required field in object"
        return True, ""

# function to search for artwork image URL given title
def get_artwork_image(artwork_title, artist_name, GOOGLE_API_KEY, GOOGLE_CSE_ID):
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
            'q': artwork_title + " " + artist_name + " artwork", # context for query
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