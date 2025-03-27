package com.example;

import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpEntity;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.json.JSONObject;
import org.apache.catalina.valves.JsonAccessLogValve;
import org.json.JSONArray;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.concurrent.ConcurrentHashMap;
import java.util.UUID;

@CrossOrigin(origins = "*")
@RestController
@RequestMapping("/api")
public class AppController {
    private static final String WIKI_API_URL = "https://en.wikipedia.org/w/api.php";
    private static final String PYTHON_SERVICE_URL = "http://localhost:5001";

    private final ConcurrentHashMap<String, JSONArray> politicalEventSearchCache = new ConcurrentHashMap<String, JSONArray>();

    @GetMapping("/artwork")
    public ResponseEntity<String> getArtistInfo(
            @RequestParam String name,
            @RequestParam String scopes) {
        
        RestTemplate restTemplate = new RestTemplate();
        
        try {
            // Parse the scopes JSON array
            ObjectMapper mapper = new ObjectMapper();
            List<String> scopesList = mapper.readValue(scopes, new TypeReference<List<String>>() {});
            
            String artistPageId = getArtistPageId(name, restTemplate);
            if (artistPageId == null) {
                return ResponseEntity.ok(new JSONObject()
                    .put("error", "Artist not found")
                    .toString());
            }

            int[] lifespan = getArtistLifespan(artistPageId, restTemplate);
            if (lifespan == null) {
                return ResponseEntity.ok(new JSONObject()
                    .put("error", "Could not determine artist's lifespan")
                    .toString());
            }
            System.out.println("hello world: " +  lifespan[0] + " - " + lifespan[1]);


            JSONObject result = new JSONObject();
            result.put("artistUrl", "https://en.wikipedia.org/?curid=" + artistPageId);

            // Unique identifier for each search request
            String searchID = UUID.randomUUID().toString();
            result.put("searchID", searchID);
            System.out.println("ID: " + searchID);

            if (scope.equals("political-events")) {
                String politicalEventsQuery = buildPoliticalEventsQuery(lifespan[0], lifespan[1]);
                JSONArray events = searchPoliticalEvents(politicalEventsQuery, restTemplate);

                // Store events in cache with unique identifier
                politicalEventSearchCache.put(searchID, events);

                result.put("events", events);
                
                // indexPoliticalEvents(events, restTemplate);
            } else if (scope.equals("art-movements")) {
                String artMovementsQuery = buildArtMovementsQuery(lifespan[0], lifespan[1]);
                JSONArray movements = searchArtMovements(artMovementsQuery, restTemplate);
                result.put("events", movements);
            } else if (scope.equals("artist-network")) {
                JSONArray network = searchArtistNetwork(artistPageId, restTemplate);
                result.put("events", network);
            }
            result.put("events", allEvents);

            return ResponseEntity.ok(result.toString());

        } catch (Exception e) {
            return ResponseEntity.badRequest().body(new JSONObject()
                .put("error", "Error searching artist: " + e.getMessage())
                .toString());
        }
    }

    @GetMapping("/summarize")
    public ResponseEntity<String> summarizeSearchResults(
        @RequestParam String searchID,
        @RequestParam String artistName
    ) {
        // Check search results are in the cache
        if (!politicalEventSearchCache.containsKey(searchID)) {
            System.out.println("Search ID not not found in cache");
            return ResponseEntity.badRequest().body(new JSONObject()
                .put("error", "Invalid search ID or cache expired").toString());
        }

        try {
            System.out.println("/summarize " + searchID);
            JSONArray events = politicalEventSearchCache.get(searchID);
            // Check events is not empty - prevents spurious LLM calls
            if (events.length() == 0) {
                return ResponseEntity.badRequest().body(new JSONObject()
                    .put("error", "No search results to summarize").toString());
            }

            RestTemplate restTemplate = new RestTemplate();

            // Send request to Python microservices to get summary from events
            JSONObject pythonServiceRequest = new JSONObject();
            pythonServiceRequest.put("artistName", artistName);
            pythonServiceRequest.put("events", events);

            String llmServiceURL = PYTHON_SERVICE_URL + "/summarize";

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<String> entity = new HttpEntity<>(pythonServiceRequest.toString(), headers);
            
            ResponseEntity<String> response = restTemplate.postForEntity(llmServiceURL, entity, String.class);
            return response;
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(new JSONObject()
                .put("error", "Error summarizing search results: " + e.getMessage()).toString());
        }
    }

    @GetMapping("/agent")
    public ResponseEntity<String> searchWithAgents(
        @RequestParam String artistName,
        @RequestParam String context
    ) {
        System.out.println("/agent: " + artistName + ", " + context);
        try {
            RestTemplate restTemplate = new RestTemplate();

            JSONObject pythonServiceRequest = new JSONObject();
            pythonServiceRequest.put("artistName", artistName);
            JSONArray contextArray = new JSONArray(context.split(","));
            pythonServiceRequest.put("context", contextArray);

            String llmServiceURL = PYTHON_SERVICE_URL + "/agent";

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<String> entity = new HttpEntity<>(pythonServiceRequest.toString(), headers);

            ResponseEntity<String> response = restTemplate.postForEntity(llmServiceURL, entity, String.class);
            return response;
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(new JSONObject()
                .put("error", "Error searching with agents: " + e.getMessage()).toString());
        }
    }

    private String getArtistPageId(String name, RestTemplate restTemplate) throws Exception {
        String searchQuery = URLEncoder.encode(name, StandardCharsets.UTF_8);
        String searchUrl = WIKI_API_URL + "?action=query&format=json&list=search&srsearch=" + searchQuery + "&srlimit=1";
        
        String searchResponse = restTemplate.getForObject(searchUrl, String.class);
        JSONObject searchData = new JSONObject(searchResponse);
        JSONArray searchResults = searchData.getJSONObject("query").getJSONArray("search");

        return searchResults.length() > 0 ? 
               String.valueOf(searchResults.getJSONObject(0).getInt("pageid")) : null;
    }

    private int[] getArtistLifespan(String pageId, RestTemplate restTemplate) throws Exception {
        String contentUrl = WIKI_API_URL + "?action=query&format=json&prop=revisions&rvprop=content&pageids=" + pageId;
        String contentResponse = restTemplate.getForObject(contentUrl, String.class);
        JSONObject contentData = new JSONObject(contentResponse);
        String content = contentData.getJSONObject("query")
                                  .getJSONObject("pages")
                                  .getJSONObject(pageId)
                                  .getJSONArray("revisions")
                                  .getJSONObject(0)
                                  .getString("*");

        Pattern birthPattern = Pattern.compile("\\|\\s*birth_date\\s*=\\s*\\{\\{.*?(\\d{4})");
        Pattern deathPattern = Pattern.compile("\\|\\s*death_date\\s*=\\s*\\{\\{.*?(\\d{4})");

        Matcher birthMatcher = birthPattern.matcher(content);
        Matcher deathMatcher = deathPattern.matcher(content);

        if (birthMatcher.find()) {
            int birthYear = Integer.parseInt(birthMatcher.group(1));
            int deathYear = deathMatcher.find() ? 
                          Integer.parseInt(deathMatcher.group(1)) : 
                          java.time.Year.now().getValue();
            return new int[]{birthYear, deathYear};
        }

        return null;
    }

    private String buildPoliticalEventsQuery(int birthYear, int deathYear) {
        return String.format(
            "(\"political revolution\" OR \"civil war\" OR \"world war\" OR " +
            "\"political movement\" OR \"rebellion\" OR \"uprising\" OR " + 
            "\"revolution\" OR \"coup\" OR \"revolt\") " +
            "%d..%d",
            birthYear, deathYear
        );
    }

    private JSONArray searchPoliticalEvents(String query, RestTemplate restTemplate) throws Exception {
        String eventsUrl = WIKI_API_URL + "?action=query&format=json&list=search&srlimit=10&srsearch=" + query;
        System.out.println(query);
        System.out.println(eventsUrl);
    
        String eventsResponse = restTemplate.getForObject(eventsUrl, String.class);
        JSONObject eventsData = new JSONObject(eventsResponse);
    
        System.out.println("Total hits: " + eventsData.getJSONObject("query").getJSONObject("searchinfo").getInt("totalhits"));
    
        JSONArray searchResults = eventsData.getJSONObject("query").getJSONArray("search");
        
        JSONArray filteredResults = new JSONArray();
        for (int i = 0; i < searchResults.length(); i++) {
            JSONObject event = searchResults.getJSONObject(i);
            if (isValidPoliticalEvent(event.getString("title"))) {
                filteredEvents.put(new JSONObject()
                    .put("title", event.getString("title"))
                    .put("url", "https://en.wikipedia.org/?curid=" + event.getInt("pageid"))
                    .put("snippet", event.getString("snippet")));
            }
        }

        return filteredEvents;
    }
    
    private boolean isValidPoliticalEvent(String title) {
        String lowerTitle = title.toLowerCase();
        return (lowerTitle.contains("revolution") ||
               lowerTitle.contains("war") ||
               lowerTitle.contains("rebellion") ||
               lowerTitle.contains("uprising") ||
               lowerTitle.contains("revolt") ||
               lowerTitle.contains("coup") ||
               lowerTitle.contains("political") ||
               lowerTitle.contains("movement") ||
               lowerTitle.contains("protest")) &&
               !lowerTitle.contains("list of");
    }

    private void indexPoliticalEvents(JSONArray events, RestTemplate restTemplate) {
        System.out.println("indexPoliticalEvents");
        String vectorDBServiceUrl = PYTHON_SERVICE_URL + "/index";

        System.out.println("--- article titles:");
        JSONArray article_titles = new JSONArray();
        for (int i = 0; i < events.length(); i++) {
            System.out.println(events.getJSONObject(i).getString("title"));
            article_titles.put(events.getJSONObject(i).getString("title"));
        }
        System.out.println("---");

        JSONObject request = new JSONObject();
        request.put("article_titles", article_titles);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        HttpEntity<String> entity = new HttpEntity<>(request.toString(), headers);
        ResponseEntity<String> response = restTemplate.postForEntity(vectorDBServiceUrl, entity, String.class);
        System.out.println(response);
    }

    private String buildArtMovementsQuery(int birthYear, int deathYear) {
        //return String.format("\"art movement\" %d..%d", birthYear, deathYear);
        
        return String.format(
            
            "(\"art movement\" OR \"artistic movement\" OR modernism OR " +
            "expressionism OR surrealism OR cubism OR futurism OR " +
            "dadaism OR impressionism OR \"abstract art\") " +
            "%d..%d",
            birthYear, deathYear

        );

    }

    private JSONArray searchArtMovements(String query, RestTemplate restTemplate) throws Exception {
        //String movementsUrl = WIKI_API_URL + "?action=query&format=json&list=search&srlimit=10&srsearch=" + 
        //                    URLEncoder.encode(query, StandardCharsets.UTF_8);
        String movementsUrl = WIKI_API_URL + "?action=query&format=json&list=search&srlimit=10&srsearch=" + query;
        System.out.println(query);
        System.out.println(movementsUrl);
        //WORKS
        //movementsUrl = "https://en.wikipedia.org/w/api.php?action=query&format=json&list=search&srlimit=10&srsearch=\"art movement\" 1853..1890";

        String movementsResponse = restTemplate.getForObject(movementsUrl, String.class);
        JSONObject movementsData = new JSONObject(movementsResponse);

        // One-liner to print the total number of search results
        System.out.println("Total hits: " + movementsData.getJSONObject("query").getJSONObject("searchinfo").getInt("totalhits"));

        JSONArray searchResults = movementsData.getJSONObject("query").getJSONArray("search");
        
        JSONArray filteredMovements = new JSONArray();
        for (int i = 0; i < searchResults.length(); i++) {
            JSONObject movement = searchResults.getJSONObject(i);
            if (isValidArtMovement(movement.getString("title"))) {
                filteredMovements.put(new JSONObject()
                    .put("title", movement.getString("title"))
                    .put("url", "https://en.wikipedia.org/?curid=" + movement.getInt("pageid"))
                    .put("snippet", movement.getString("snippet")));
            }
        }
        
        return filteredMovements;
    }

    private String getPageContent(String pageId, RestTemplate restTemplate) throws Exception {
        String contentUrl = WIKI_API_URL + "?action=query&format=json&prop=extracts&pageids=" + pageId + "&explaintext=1";
        String contentResponse = restTemplate.getForObject(contentUrl, String.class);
        return new JSONObject(contentResponse)
            .getJSONObject("query")
            .getJSONObject("pages")
            .getJSONObject(pageId)
            .getString("extract");
    }

    private boolean isRelevantResult(String content, String scope) {
        if (content == null || content.isEmpty()) {
            return false;
        }

        // Convert to lower case for case-insensitive matching
        content = content.toLowerCase();
        scope = scope.toLowerCase();

        // Split scope into individual terms
        String[] terms = scope.split("\\s+");
        
        // Check if all terms appear in the content
        for (String term : terms) {
            if (!content.contains(term)) {
                return false;
            }
        }

        // Additional relevance checks can be added here
        return true;
    }

    private String findRelationshipContext(String content, String searchTerm) {
        if (content == null || searchTerm == null) return null;
        
        // Make case-insensitive
        String lowerContent = content.toLowerCase();
        String lowerSearchTerm = searchTerm.toLowerCase();
        
        int termIndex = lowerContent.indexOf(lowerSearchTerm);
        if (termIndex == -1) return null;
        
        // Expand context window and ensure proper sentence boundaries
        int start = Math.max(0, termIndex - 150);
        int end = Math.min(content.length(), termIndex + searchTerm.length() + 150);
        
        // Find sentence boundaries
        while (start > 0 && content.charAt(start) != '.') start--;
        while (end < content.length() && content.charAt(end) != '.') end++;
        
        // Adjust boundaries
        start = start == 0 ? 0 : start + 1;
        end = end == content.length() ? end : end + 1;
        
        return content.substring(start, end).trim();
    }

    private boolean isValidArtMovement(String title) {
        String lowerTitle = title.toLowerCase();
        return lowerTitle.contains("movement") ||
               lowerTitle.contains("modernism") ||
               lowerTitle.contains("expressionism") ||
               lowerTitle.contains("surrealism") ||
               lowerTitle.contains("cubism") ||
               lowerTitle.contains("futurism") ||
               lowerTitle.contains("dadaism") ||
               lowerTitle.contains("impressionism") ||
               lowerTitle.contains("abstract art") ||
               lowerTitle.contains("renaissance") ||
               lowerTitle.contains("realism") ||
               lowerTitle.contains("pop") ||
               lowerTitle.contains("ism");
    }
}