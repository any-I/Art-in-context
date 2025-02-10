package com.example;

import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import org.springframework.http.ResponseEntity;
import org.json.JSONObject;
import org.json.JSONArray;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

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
            String searchQuery = URLEncoder.encode(name, StandardCharsets.UTF_8);
            String searchUrl = WIKI_API_URL + "?action=query&format=json&list=search&srsearch=" + searchQuery + "&srlimit=1";
            
            String searchResponse = restTemplate.getForObject(searchUrl, String.class);
            JSONObject searchData = new JSONObject(searchResponse);
            JSONArray searchResults = searchData.getJSONObject("query").getJSONArray("search");

            if (searchResults.length() > 0) {
                JSONObject result = new JSONObject();
                String title = searchResults.getJSONObject(0).getString("title");
                String pageId = String.valueOf(searchResults.getJSONObject(0).getInt("pageid"));
                String wikiUrl = "https://en.wikipedia.org/?curid=" + pageId;
                
                switch(scope) {
                    case "political-events":
                        // TODO: Add logic for political events
                        result.put("url", wikiUrl)
                             .put("scope", "political-events")
                             .put("message", "Political events data will be implemented");
                        break;
                    case "art-movements":
                        // TODO: Add logic for art movements
                        result.put("url", wikiUrl)
                             .put("scope", "art-movements")
                             .put("message", "Art movements data will be implemented");
                        break;
                    case "personal-events":
                        // TODO: Add logic for personal events
                        result.put("url", wikiUrl)
                             .put("scope", "personal-events")
                             .put("message", "Personal events data will be implemented");
                        break;
                    case "artist-network":
                        // TODO: Add logic for artist network
                        result.put("url", wikiUrl)
                             .put("scope", "artist-network")
                             .put("message", "Artist network data will be implemented");
                        break;
                    default:
                        return ResponseEntity.badRequest().body(new JSONObject()
                            .put("error", "Invalid scope provided").toString());
                }
                
                return ResponseEntity.ok(result.toString());
            }

            return ResponseEntity.ok(new JSONObject().put("error", "Artist not found").toString());

        } catch (Exception e) {
            return ResponseEntity.badRequest().body(new JSONObject()
                .put("error", "Error searching artist").toString());
        }
    }
}