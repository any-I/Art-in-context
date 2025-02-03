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

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.json.JSONObject;
import org.json.JSONArray;
import java.util.ArrayList;
import java.util.List;

@CrossOrigin(origins = "*")
@RestController
@RequestMapping("/api")
public class AppController {

    private static final String BASE_URL = "https://collectionapi.metmuseum.org/public/collection/v1";

    @GetMapping("/artwork")
    public ResponseEntity<String> getArtworkInfo(@RequestParam String name) {
        RestTemplate restTemplate = new RestTemplate();

        String searchURL = BASE_URL + "/search?q=" + name;
        String searchResponse = restTemplate.getForObject(searchURL, String.class);

        if (searchResponse == null) {
            return ResponseEntity.badRequest().body(new JSONObject().put("error", "error searching artwork from MET!").toString());
        }

        JSONObject searchData = new JSONObject(searchResponse);
        System.out.println("Search Response: " + searchData.toString(4));

        if (!searchData.has("objectIDs") || searchData.getJSONArray("objectIDs").isEmpty()) {
            return ResponseEntity.ok(new JSONObject().put("error", "no artwork matched!").toString());
        }

        JSONArray objectIDs = searchData.getJSONArray("objectIDs");
        List<JSONObject> validArtworks = new ArrayList<>();
        int count = 0;

        for (int i = 0; i < objectIDs.length() && count < 9; i++) {
            try {
                int objectId = objectIDs.getInt(i);
                String artworkURL = BASE_URL + "/objects/" + objectId;
                String artworkResponse = restTemplate.getForObject(artworkURL, String.class);
                
                if (artworkResponse != null) {
                    JSONObject artwork = new JSONObject(artworkResponse);
                    validArtworks.add(artwork);
                    count++;
                    
                    System.out.println("\n----- Artwork " + count + " Information -----");
                    System.out.println("Title: " + artwork.optString("title", "Unknown"));
                    System.out.println("Artist: " + artwork.optString("artistDisplayName", "Unknown"));
                    System.out.println("Date: " + artwork.optString("objectDate", "Unknown"));
                }
            } catch (Exception e) {
                System.out.println("Error fetching artwork ID: " + objectIDs.getInt(i));
            }
        }

        if (validArtworks.isEmpty()) {
            return ResponseEntity.ok(new JSONObject().put("error", "No valid artworks found!").toString());
        }

        JSONArray artworksArray = new JSONArray(validArtworks);
        return ResponseEntity.ok(artworksArray.toString());
    }
}