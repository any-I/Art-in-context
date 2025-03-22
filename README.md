### Java backend:
1. `cd backend`
2. `mvn clean spring-boot:run`

Can independently test backend with something like `localhost:8080/api/artwork?name=Mona Lisa`


### Javascript frontend:
1. `cd frontend`
2. `npm start`

Should open on local


### Python microservices (RAG):
1. `cd services`
2. `conda activate <env_name>`
3. `uvicorn llm_service:app --host 0.0.0.0 --port 5001 --reload`

When running microservices for the first time, set up a conda environment:
- Download conda if not already
- `conda create --name <env_name> python=3.10`
- `conda activate <env_name>`
- `pip install -r requirements.txt`

Can independently test Python microservices with something like:
```
curl -X POST "http://localhost:5001/summarize" \
     -H "Content-Type: application/json" \
     -d '{"events": [{"title": "French Revolution", "snippet": "A major event in the late 18th century..."}, {"title": "Impressionism", "snippet": "An art movement that originated in the 19th century..."}]}'
```
Windows (Powershell):
```
Invoke-RestMethod -Uri "http://localhost:5001/summarize" `
    -Method POST `
    -Headers @{ "Content-Type" = "application/json" } `
    -Body '{
        "artistName": "Monet",
        "events": [
            { "title": "French Revolution", "snippet": "A major event in the late 18th century..." },
            { "title": "Impressionism", "snippet": "An art movement that originated in the 19th century..." }
        ]
    }'
```


### API Keys
API keys should not be hardcoded into the source code for security reasons.

To use **OpenAI API** for the RAG microservices, create a `services/.env` file containing:
```
OPENAI_API_KEY=<your_openai_api_key_here>
```