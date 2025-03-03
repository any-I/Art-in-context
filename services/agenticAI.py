from fastapi import FastAPI
from dotenv import load_dotenv
from huggingface_hub import login
from smolagents import CodeAgent, DuckDuckGoSearchTool, HfApiModel, ToolCallingAgent, PythonInterpreterTool
import os
import openai

load_dotenv()
app = FastAPI()

def init_fns():
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_API_KEY: raise ValueError("Missing or incorrect OpenAI API Key.")
    openAIClient = openai.OpenAI(api_key=OPENAI_API_KEY)

    HF_API_TOKEN = os.getenv("HF_API_TOKEN")
    if not HF_API_TOKEN: raise ValueError("Missing or incorrect HF API Token.")
    HFlogin = login(token=HF_API_TOKEN)

model = HfApiModel()

agent = ToolCallingAgent(
    tools=[DuckDuckGoSearchTool(), PythonInterpreterTool()],
    model=model,
)

# todo:
#  1. search + filters --> agent query
#  2. tune system prompt to use more reputable sources
#  3. maybe cite sources per fact that is stated
#  4. use OpenAI model from HF

modified_prompt = open("system_prompt.txt", "r", encoding="utf-8").read()
agent.prompt_templates["system_prompt"] = modified_prompt
print(agent.prompt_templates["system_prompt"])
# from Michaelangelo: history, political background -> chatgpt ask for query for agent ai: "Michelangelo history and political background" -> Explore Michelangelo Buonarroti's historical context, including his political influences, affiliations, and impact of Renaissance politics on his work.
agent_query = "Explore Michelangelo Buonarroti's historical context, including his political influences, affiliations, and impact of Renaissance politics on his work. Make sure to cite sources!"

response = agent.run(agent_query)

# print(response)