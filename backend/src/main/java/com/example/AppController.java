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
    public ResponseEntity<String> getArtistInfo(@RequestParam String name) {
        RestTemplate restTemplate = new RestTemplate();
        
        try {
            // Fix: Remove unnecessary quotes from search query
            String searchQuery = URLEncoder.encode(name, StandardCharsets.UTF_8);
            String searchUrl = WIKI_API_URL + "?action=query&format=json&list=search&srsearch=" + searchQuery + "&srlimit=1";
            
            System.out.println("Search URL: " + searchUrl);
            String searchResponse = restTemplate.getForObject(searchUrl, String.class);
            System.out.println("Search Response: " + searchResponse);
            
            JSONObject searchData = new JSONObject(searchResponse);
            JSONArray searchResults = searchData.getJSONObject("query").getJSONArray("search");

            if (searchResults.length() > 0) {
                String title = searchResults.getJSONObject(0).getString("title");
                String pageId = String.valueOf(searchResults.getJSONObject(0).getInt("pageid"));
                
                System.out.println("First search result title: " + title);
                
                // Fetch all categories, handling pagination properly
                boolean artistFound = false;
                String clContinue = null;

                do {
                    // Construct category URL
                    String categoryUrl = WIKI_API_URL + "?action=query&format=json&prop=categories&titles=" +
                            URLEncoder.encode(title, StandardCharsets.UTF_8);
                    
                    if (clContinue != null) {
                        categoryUrl += "&clcontinue=" + clContinue;  // ⚠️ Don't encode `clcontinue` again!
                    }

                    System.out.println("Category URL: " + categoryUrl);
                    String categoryResponse = restTemplate.getForObject(categoryUrl, String.class);
                    System.out.println("Category Response: " + categoryResponse);

                    JSONObject categoryJson = new JSONObject(categoryResponse);

                    // Ensure the response has the "query" key before accessing it
                    if (!categoryJson.has("query")) {
                        System.err.println("Invalid response: " + categoryResponse);
                        break;
                    }

                    JSONObject pages = categoryJson.getJSONObject("query").getJSONObject("pages");
                    JSONObject pageData = pages.getJSONObject(pageId);

                    if (pageData.has("categories")) {
                        JSONArray categories = pageData.getJSONArray("categories");

                        for (int i = 0; i < categories.length(); i++) {
                            String category = categories.getJSONObject(i).getString("title").toLowerCase();

                            // Fix: Allow all artists, painters, and sculptors
                            if (category.contains("artist") || category.contains("painter") || category.contains("sculptor")) {
                                artistFound = true;
                                break;
                            }
                        }
                    }

                    // Handle pagination correctly
                    clContinue = categoryJson.optJSONObject("continue") != null
                            ? categoryJson.getJSONObject("continue").optString("clcontinue", null)
                            : null;

                } while (clContinue != null && !artistFound); // Keep fetching until a match is found

                if (artistFound) {
                    String wikiUrl = "https://en.wikipedia.org/?curid=" + pageId;
                    System.out.println("Sending Wiki URL to frontend: " + wikiUrl);
                    return ResponseEntity.ok(new JSONObject().put("url", wikiUrl).toString());
                }
            }

            return ResponseEntity.ok(new JSONObject().put("error", "Artist not found").toString());

        } catch (Exception e) {
            System.err.println("Error occurred: " + e.getMessage());
            e.printStackTrace();
            return ResponseEntity.badRequest().body(new JSONObject().put("error", "Error searching artist").toString());
        }
    }
}
