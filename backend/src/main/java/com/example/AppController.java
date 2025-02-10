package com.example;

import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import org.springframework.http.ResponseEntity;
import org.json.JSONObject;
import org.json.JSONArray;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@CrossOrigin(origins = "*")
@RestController
@RequestMapping("/api")
public class AppController {
    private static final String WIKI_API_URL = "https://en.wikipedia.org/w/api.php";

    @GetMapping("/artwork")
    public ResponseEntity<String> getArtistInfo(
            @RequestParam String name,
            @RequestParam(defaultValue = "political-events") String scope) {
        
        RestTemplate restTemplate = new RestTemplate();
        
        try {
            // Get artist details
            String artistPageId = getArtistPageId(name, restTemplate);
            if (artistPageId == null) {
                return ResponseEntity.ok(new JSONObject().put("error", "Artist not found").toString());
            }

            // Get artist's birth/death years
            int[] lifespan = getArtistLifespan(artistPageId, restTemplate);
            if (lifespan == null) {
                return ResponseEntity.ok(new JSONObject().put("error", "Could not determine artist's lifespan").toString());
            }

            JSONObject result = new JSONObject();
            result.put("artistUrl", "https://en.wikipedia.org/?curid=" + artistPageId);

            if (scope.equals("political-events")) {
                String politicalEventsQuery = buildPoliticalEventsQuery(lifespan[0], lifespan[1]);
                JSONArray events = searchPoliticalEvents(politicalEventsQuery, restTemplate);
                result.put("events", events);
            }

            return ResponseEntity.ok(result.toString());

        } catch (Exception e) {
            return ResponseEntity.badRequest().body(new JSONObject()
                .put("error", "Error searching artist: " + e.getMessage()).toString());
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
            "(revolution OR war OR political OR uprising OR conflict OR regime) " +
            "%d..%d", 
            birthYear, deathYear
        );
    }

    private JSONArray searchPoliticalEvents(String query, RestTemplate restTemplate) throws Exception {
        String eventsUrl = WIKI_API_URL + "?action=query&format=json&list=search&srlimit=10&srsearch=" + 
                          URLEncoder.encode(query, StandardCharsets.UTF_8);
        
        String eventsResponse = restTemplate.getForObject(eventsUrl, String.class);
        JSONObject eventsData = new JSONObject(eventsResponse);
        JSONArray searchResults = eventsData.getJSONObject("query").getJSONArray("search");
        
        JSONArray filteredEvents = new JSONArray();
        for (int i = 0; i < searchResults.length(); i++) {
            JSONObject event = searchResults.getJSONObject(i);
            filteredEvents.put(new JSONObject()
                .put("title", event.getString("title"))
                .put("url", "https://en.wikipedia.org/?curid=" + event.getInt("pageid"))
                .put("snippet", event.getString("snippet")));
        }
        
        return filteredEvents;
    }
}