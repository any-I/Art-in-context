package com.example;

import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import org.springframework.http.ResponseEntity;
import org.json.JSONObject;
import org.json.JSONArray;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.List;

@CrossOrigin(origins = "*")
@RestController
@RequestMapping("/api")
public class AppController {
    private static final String WIKI_API_URL = "https://en.wikipedia.org/w/api.php";

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

            JSONObject result = new JSONObject();
            result.put("artistUrl", "https://en.wikipedia.org/?curid=" + artistPageId);
            
            // Process each scope
            JSONArray allEvents = new JSONArray();
            for (String scope : scopesList) {
                JSONArray eventsForScope = searchWithScope(scope, lifespan, artistPageId, restTemplate);
                // Combine results
                for (int i = 0; i < eventsForScope.length(); i++) {
                    allEvents.put(eventsForScope.getJSONObject(i));
                }
            }
            result.put("events", allEvents);

            return ResponseEntity.ok(result.toString());

        } catch (Exception e) {
            return ResponseEntity.badRequest().body(new JSONObject()
                .put("error", "Error searching artist: " + e.getMessage())
                .toString());
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

    private JSONArray searchWithScope(String scope, int[] lifespan, String artistPageId, RestTemplate restTemplate) throws Exception {
        String query = buildScopeQuery(scope, lifespan[0], lifespan[1]);
        String searchUrl = WIKI_API_URL + "?action=query&format=json&list=search&srlimit=10&srsearch=" + 
                          URLEncoder.encode(query, StandardCharsets.UTF_8);
        
        String searchResponse = restTemplate.getForObject(searchUrl, String.class);
        JSONObject searchData = new JSONObject(searchResponse);
        JSONArray searchResults = searchData.getJSONObject("query").getJSONArray("search");
        
        JSONArray filteredResults = new JSONArray();
        for (int i = 0; i < searchResults.length(); i++) {
            JSONObject result = searchResults.getJSONObject(i);
            
            // Get the page content for contextual filtering
            String pageContent = getPageContent(String.valueOf(result.getInt("pageid")), restTemplate);
            if (isRelevantResult(pageContent, scope)) {
                filteredResults.put(new JSONObject()
                    .put("title", result.getString("title"))
                    .put("url", "https://en.wikipedia.org/?curid=" + result.getInt("pageid"))
                    .put("snippet", result.getString("snippet")));
            }
        }
        
        return filteredResults;
    }

    private String buildScopeQuery(String scope, int startYear, int endYear) {
        return String.format("(%s) %d..%d", scope, startYear, endYear);
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
}