// package com.example;

// import org.springframework.web.bind.annotation.GetMapping;
// import org.springframework.web.bind.annotation.RequestMapping;
// import org.springframework.web.bind.annotation.RestController;
// import org.springframework.web.client.RestTemplate;
// import org.springframework.web.bind.annotation.RequestParam;
// import org.springframework.http.ResponseEntity;
// import org.springframework.web.bind.annotation.CrossOrigin;
// import org.json.JSONObject;
// import org.json.JSONArray;

// @CrossOrigin(origins = "*") // allows frontend requests ?? idk how it works tho
// @RestController
// @RequestMapping("/api")
// public class AppController {

//     private static final String BASE_URL = "https://collectionapi.metmuseum.org/public/collection/v1";

//     @GetMapping("/artwork")
//     public ResponseEntity<String> getArtworkInfo(@RequestParam String name) {

//         RestTemplate restTemplate = new RestTemplate();

//         String searchURL = BASE_URL + "/search?q=" + name;
//         String searchResponse = restTemplate.getForObject(searchURL, String.class);

//         if (searchResponse == null) return ResponseEntity.badRequest().body(new JSONObject().put("error", "error searching artwork from MET!").toString());

//         JSONObject searchData = new JSONObject(searchResponse);
//         System.out.println("Search Response: " + searchData.toString(4)); // Debugging: Print the full search response

//         if (!searchData.has("objectIDs") || searchData.getJSONArray("objectIDs").isEmpty()) return ResponseEntity.ok(new JSONObject().put("error", "no artwork matched!").toString());

//         JSONArray objectIDs = searchData.getJSONArray("objectIDs");
//         int validArtworkId = -1;

//         // Loop through object IDs to find the first valid one
//         for (int i = 0; i < objectIDs.length(); i++) {
//             int candidateId = objectIDs.getInt(i);
//             String testUrl = BASE_URL + "/objects/" + candidateId;

//             try {
//                 String testResponse = restTemplate.getForObject(testUrl, String.class);
//                 if (testResponse != null) {
//                     validArtworkId = candidateId;
//                     break; // Found a valid object, stop checking
//                 }
//             } catch (Exception e) {
//                 System.out.println("Skipping invalid object ID: " + candidateId);
//             }
//         }

//         // If no valid artwork was found
//         if (validArtworkId == -1) return ResponseEntity.ok(new JSONObject().put("error", "No valid artwork found!").toString());

//         String artworkURL = BASE_URL + "/objects/" + validArtworkId;
//         String artworkResponse = restTemplate.getForObject(artworkURL, String.class);
//         JSONObject artwork = new JSONObject(artworkResponse);

//         // chatGPT generated print statements
//         System.out.println("\n-------------------------PRIMARY INFORMATION------------------------------\n");
//         System.out.println("Title: " + artwork.optString("title", "Unknown"));
//         System.out.println("Artist: " + artwork.optString("artistDisplayName", "Unknown"));
//         System.out.println("Date: " + artwork.optString("objectDate", "Unknown"));
//         System.out.println("Medium: " + artwork.optString("medium", "Unknown"));
//         if (!artwork.optString("primaryImage").isEmpty()) System.out.println("Image: " + artwork.optString("primaryImage"));
//         System.out.println("\n-----------------------ALL JSON INFORMATION--------------------------\n");
//         System.out.println(artwork.toString(4));

// //        return artwork;// can't do this since frontend doesn't take JSONs?
//         return ResponseEntity.ok(artwork.toString());
//     }
// }

package com.example;

import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import org.springframework.http.ResponseEntity;
import org.json.JSONObject;
import org.json.JSONArray;
import java.util.ArrayList;
import java.util.List;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

@CrossOrigin(origins = "*")
@RestController
@RequestMapping("/api")
public class AppController {
    private static final String WIKI_API_URL = "https://en.wikipedia.org/w/api.php";
    private static final String WIKI_MEDIA_API = "https://commons.wikimedia.org/w/api.php";

    @GetMapping("/artwork")
    public ResponseEntity<String> getArtworkInfo(@RequestParam String name) {
        RestTemplate restTemplate = new RestTemplate();
        List<JSONObject> artworks = new ArrayList<>();

        try {
            String searchQuery = URLEncoder.encode(name + " artwork painting", StandardCharsets.UTF_8);
            String searchUrl = WIKI_API_URL + "?action=query&format=json&list=search&srsearch=" + searchQuery + "&srlimit=9";
            
            String searchResponse = restTemplate.getForObject(searchUrl, String.class);
            JSONObject searchData = new JSONObject(searchResponse);
            JSONArray searchResults = searchData.getJSONObject("query").getJSONArray("search");

            for (int i = 0; i < searchResults.length() && i < 9; i++) {
                JSONObject result = searchResults.getJSONObject(i);
                String title = result.getString("title");
                String pageId = String.valueOf(result.getInt("pageid"));

                String detailUrl = WIKI_API_URL + "?action=query&format=json&prop=extracts|pageimages&exintro=1&piprop=original&titles=" + URLEncoder.encode(title, StandardCharsets.UTF_8);
                String detailResponse = restTemplate.getForObject(detailUrl, String.class);
                JSONObject pages = new JSONObject(detailResponse).getJSONObject("query").getJSONObject("pages");
                JSONObject pageData = pages.getJSONObject(pages.keys().next());

                JSONObject artwork = new JSONObject();
                artwork.put("title", title);
                artwork.put("artistDisplayName", extractArtist(pageData.optString("extract", "")));
                artwork.put("objectDate", extractDate(pageData.optString("extract", "")));
                artwork.put("medium", "Artwork");
                artwork.put("objectURL", "https://en.wikipedia.org/?curid=" + pageId);
                
                if (pageData.has("original")) {
                    artwork.put("primaryImage", pageData.getJSONObject("original").getString("source"));
                }

                artworks.add(artwork);
            }

            if (artworks.isEmpty()) {
                return ResponseEntity.ok(new JSONObject().put("error", "No artworks found!").toString());
            }

            return ResponseEntity.ok(new JSONArray(artworks).toString());

        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
            return ResponseEntity.badRequest().body(new JSONObject().put("error", "Error searching artwork!").toString());
        }
    }

    private String extractArtist(String extract) {
        String[] keywords = {"painted by", "created by", "by", "artist"};
        String lowercaseExtract = extract.toLowerCase();
        
        for (String keyword : keywords) {
            int index = lowercaseExtract.indexOf(keyword);
            if (index != -1) {
                int end = lowercaseExtract.indexOf(".", index);
                if (end != -1) {
                    return extract.substring(index + keyword.length(), end).trim();
                }
            }
        }
        return "Unknown";
    }

    private String extractDate(String extract) {
        String[] years = extract.replaceAll("[^0-9]", " ").trim().split("\\s+");
        return years.length > 0 ? years[0] : "Unknown";
    }
}