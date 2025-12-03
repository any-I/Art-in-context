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
    url_re = re.compile(r"(?:https?:\/\/)?(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=\-]*)")
    artwork_title_re = re.compile(r"\+\+([^\+\n]+)\+\+") # titles surrounded by ++

    #### Public functions
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
                # process/add on to the last-added result in the list
                current_result = results[-1]

                # find the proper JSON key matching the info label
                info_label = matches.group(1).strip().lower()
                json_label = self._find_json_label(info_label)

                # if we can't find a label, we assume the line is a continuation
                # of the previous object, so we just add the entire match (stripped
                # of leading/trailing whitespace) to the current info
                # if it is whitespace, we reset the current key we're adding stuff onto
                if json_label == "":
                    whole_match = matches.group(0).strip()
                    current_key = JSONParser._handle_whole_line_match(whole_match, current_key, current_result)
                    continue

                # otherwise, get actual info, processing it as necessary
                info = matches.group(2).strip()
                processed_info = self._handle_info(info, json_label, current_result)

                # update the current key/value we're constructing with this info
                current_key = json_label 
                current_result[current_key] = processed_info
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
    
    #### Helper functions when parsing
    # finding json label (key in object) given label (e.g. "date" given "Year(s)")
    # returns "" if label is unable to be found
    def _find_json_label(self, label):
        for sub_label, actual_label in self.name_to_key.items():
            if sub_label in label:
                return actual_label
        return ""
    
    # handling a line that may be a continuation of the previous key (i.e. no label)
    # returns what key we added the match onto (or "" if the line is just whitespace
    # and we should reset the key)
    @staticmethod
    def _handle_whole_line_match(match, current_key, current_result):
        # if match is "" (i.e. an empty line), reset the current key and don't do anything else
        if match == "":
            return ""
        # perform artwork search on the match as necessary, and append match to the current result
        if current_key == "detailed_summary" and "related_artwork" in current_result:
            match = JSONParser._find_related_artwork(match, current_result)
        current_result[current_key] += " " + match
        return current_key

    # helper function to handle particular info given its json label; this will call
    # appropriate methods to handle URL inputs, to search for artwork in descriptions,
    # or to do custom processing functions on special labels, returning the info 
    # unchanged if nothing applies
    def _handle_info(self, info, json_label, current_result):
        if json_label == "source_url":
            return JSONParser._handle_url(info)
        elif json_label == "detailed_summary" and "related_artwork" in self.default_obj:
            return JSONParser._find_related_artwork(info, current_result)
        elif json_label in self.special_labels:
            return self.special_labels[json_label](info)
        return info
    
    # URL parsing - strip extra information from the URL, and perhaps remove a closing
    # parentheses (as URLs are often of the form [text](url))
    @staticmethod
    def _handle_url(source):
        url = re.search(JSONParser.url_re, source)
        if url:
            parsed_url = url.group(0)
            return parsed_url[:-1] if parsed_url[-1] == ')' else parsed_url 
        return source
    
    # Function to find replacement for artwork title match
    @staticmethod
    def _replace_artwork_title(match):
        title = match.group(1).strip()
        return "\"" + title + "\""
    
    # Function to flip punctuation from inside to outside quotes
    @staticmethod
    def _flip_punctuation(match):
        punct = match.group(1)
        return punct + "\""
    
    # Finding related artwork within an event description, then add it to
    # the current result; also replace any ++title++ with "title" in
    # the description
    @staticmethod
    def _find_related_artwork(info, result_obj):
        # only find the first title that occurs and place it within the object; if 
        # the related artwork field is already filled, skip this step
        if not result_obj["related_artwork"]:
            title_match = re.search(JSONParser.artwork_title_re, info)
            if title_match:
                title = title_match.group(1).strip()
                result_obj["related_artwork"] = title
        # return the description with ++ replaced with quotes
        # be sure to flip the punctuation from outside to inside the quotes
        new_info = re.sub(JSONParser.artwork_title_re, JSONParser._replace_artwork_title, info)
        return re.sub(r"\"([,\.])", JSONParser._flip_punctuation, new_info)

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