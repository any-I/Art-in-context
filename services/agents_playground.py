from fastapi import FastAPI
from dotenv import load_dotenv
from huggingface_hub import login
from smolagents import CodeAgent, DuckDuckGoSearchTool, ToolCallingAgent, OpenAIServerModel, PythonInterpreterTool
import os
import openai

load_dotenv()
app = FastAPI()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY: raise ValueError("Missing or incorrect OpenAI API Key.")
openAIClient = openai.OpenAI(api_key=OPENAI_API_KEY)

HF_API_TOKEN = os.getenv("HF_API_TOKEN")
if not HF_API_TOKEN: raise ValueError("Missing or incorrect HF API Token.")
HFlogin = login(token=HF_API_TOKEN)

model = OpenAIServerModel(
    model_id = "gpt-4o-mini",
    api_base = "https://api.openai.com/v1",
    api_key = OPENAI_API_KEY
)

# agent = ToolCallingAgent(
#     tools=[DuckDuckGoSearchTool(), PythonInterpreterTool()],
#     model=model
# )

# modified_prompt = open("system_prompt.txt", "r", encoding="utf-8").read()
# agent.prompt_templates["system_prompt"] = modified_prompt
# print(agent.prompt_templates["system_prompt"])
# agent_query = "Michelangelo: [history, political background]"

# response = agent.run(agent_query)

researcher_prompt = open("researcher_prompt.txt", "r", encoding="utf-8").read()
historian_prompt = open("historian_prompt.txt", "r", encoding="utf-8").read()

researcher_agent = ToolCallingAgent(
    tools=[DuckDuckGoSearchTool()],
    model=model,
)
researcher_agent.prompt_templates["system_prompt"] = researcher_prompt

historian_agent = ToolCallingAgent(
    tools=[PythonInterpreterTool()],
    model=model,
)
historian_agent.prompt_templates["system_prompt"] = historian_prompt

agent_query = "Frida Kahlo: [political background]"
researcher_response = researcher_agent.run(agent_query)
print("------ RESEARCHER ------")
print(researcher_response)
historian_response = historian_agent.run(researcher_response)
print("------ HISTORIAN ------")
print(historian_response)