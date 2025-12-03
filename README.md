## Overview
This summarizes how to set up the repository on your local computer and contains the same information as the "Local Quickstart Instructions" section of the documentation.

## First-time setup
### Set up Python services
1. Install Conda if you don't already have it ([installation page here](https://docs.conda.io/projects/conda/en/stable/user-guide/install/index.html)); the Miniconda distribution is fine for this project
2. `cd services`
3. Run the following commands to create and activate a Conda environment (replace `<env_name>` with a name of your choice):  
   `conda create --name <env_name> python=3.10`  
   `conda activate <env_name>`
5. `pip install -r requirements.txt`

### Set up frontend
1. `cd frontend`
2. `npm install`

### Set up API keys
API keys should not be hardcoded into the source code nor committed to the repository for security reasons. Because of that, it's necessary to create a `services/.env` file with the following structure:
```
GOOGLE_API_KEY=<your_google_api_key_here>
GOOGLE_CSE_ID=<your_google_cse_id_here>
HF_API_TOKEN=<your_hf_api_key_here>
OPENAI_API_KEY=<your_openai_api_key_here>
PINECONE_KEY=<your_pinecone_api_key_here>
```
The values of these keys should be found in the shared project drive.

## Running the app locally
### Java backend:
1. `cd backend`
2. `mvn clean spring-boot:run`, which starts the backend server at `localhost:8080`

### Javascript frontend:
1. `cd frontend`
2. (if running for the first time, or updated dependencies:) `npm install`
3. `npm start`

Wait for a couple of minutes for the app to open automatically in your browser.

### Python microservices (RAG):
1. `cd services`
2. `conda activate <env_name>` with the `<env_name>` you set when creating the environment during setup
3. `uvicorn llm_service:app --host 0.0.0.0 --port 5001 --reload` to make the services accessible at `localhost:5001`

### Testing components individually
Use `curl` (or `Invoke-RestMethod -Uri` on Windows Powershell) to query the Java backend or Python microservices independently of the other components. As an example of how to query the Java backend independently:

```
curl -X GET "http://localhost:8080/api/agent?artistName=<name>&context=<scope>" \
     -H "Accept: text/event-stream" \
     -H "Keep-Alive: 60"
```
or
```
Invoke-RestMethod -Uri "http://localhost:8080/api/agent?artistName=<name>&context=<scope>" `
    -Method GET `
    -Headers @{ `
         "Accept" = "text/event-stream"
         "Keep-Alive" = 60
    }
```
