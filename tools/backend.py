import os 
import certifi
import time
from dotenv import load_dotenv

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

from typing import TypedDict, Annotated
import operator
import uuid

import psycopg
from psycopg.rows import dict_row

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)
from langchain_groq import ChatGroq
from tavily_tool import tavily_search
from flight_tool import search_flights


def get_database_url():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "DATABASE_URL is missing. Please add your Render PostgreSQL External Database URL to .env"
        )

    if "sslmode=" not in database_url:
        separator = "&" if "?" in database_url else "?"
        database_url = f"{database_url}{separator}sslmode=require"

    return database_url


GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing. Please add it to your .env file.")


# =========================
# LLM
# =========================

llm = ChatGroq(
    model="mixtral-8x7b-32768",
    api_key=GROQ_API_KEY,
    temperature=0.3
)


# =========================
# Retry Helper for Rate Limits
# =========================

def invoke_with_retry(llm_instance, messages, max_retries=3):
    """Invoke LLM with exponential backoff for rate limit handling"""
    from groq import APIStatusError
    
    for attempt in range(max_retries):
        try:
            return llm_instance.invoke(messages)
        except APIStatusError as e:
            if e.status_code == 429:  # Rate limit error
                wait_time = (2 ** attempt) + 1  # Exponential backoff: 2s, 4s, 8s
                print(f"Rate limit hit. Retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                raise
    
    raise Exception(f"Failed after {max_retries} retries due to rate limiting")


# =========================
# State
# =========================

class TravelState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    flight_results: str
    hotel_results: str
    itinerary: str
    llm_calls: int


# =========================
# Helper function to truncate results
# =========================
def truncate_results(text: str, max_chars: int = 1500) -> str:
    """Truncate results to avoid API payload limits."""
    if len(text) > max_chars:
        return text[:max_chars] + "...\n(Results truncated for brevity)"
    return text


# =========================
# Flight Agent
# =========================

def flight_agent(state: TravelState):
    query = state["user_query"]
    flight_data = search_flights(query)
    # Truncate to 1500 chars to reduce payload
    flight_data = truncate_results(flight_data, max_chars=1500)

    return {
        "flight_results": flight_data,
        "messages": [
            AIMessage(content="Flight results fetched.")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }



# =========================
# Hotel Agent
# =========================

def hotel_agent(state: TravelState):
    query = f"Best hotels for {state['user_query']}"
    hotel_results = tavily_search(query)
    # Truncate to 1500 chars to reduce payload
    hotel_results = truncate_results(hotel_results, max_chars=1500)

    return {
        "hotel_results": hotel_results,
        "messages": [
            AIMessage(content="Hotel information fetched.")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }




# =========================
# Itinerary Agent
# =========================

def itinerary_agent(state: TravelState):
    prompt = f"""Create a travel itinerary based on:

Trip: {state['user_query']}

Flight info: {state['flight_results'][:800] if state['flight_results'] else 'N/A'}

Hotel info: {state['hotel_results'][:800] if state['hotel_results'] else 'N/A'}

Provide practical, budget-aware itinerary."""

    response = invoke_with_retry(llm, [
        SystemMessage(content="Expert travel planner. Be concise."),
        HumanMessage(content=prompt)
    ])

    return {
        "itinerary": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }



# =========================
# Final Response Agent
# =========================

def final_agent(state: TravelState):
    final_prompt = f"""Generate final travel response.

Trip: {state['user_query']}

Flights: {state['flight_results'][:600] if state['flight_results'] else 'N/A'}

Hotels: {state['hotel_results'][:600] if state['hotel_results'] else 'N/A'}

Itinerary: {state['itinerary'][:1000] if state['itinerary'] else 'N/A'}

Format with: Trip Summary, Flights, Hotels, Daily Schedule, Budget, Tips."""

    response = invoke_with_retry(llm, [
        SystemMessage(content="Professional travel assistant. Be clear and concise."),
        HumanMessage(content=final_prompt)
    ])

    return {
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


# =========================
# Build Graph
# =========================

graph = StateGraph(TravelState)

graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("final_agent", final_agent)

graph.add_edge(START, "flight_agent")
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "itinerary_agent")
graph.add_edge("itinerary_agent", "final_agent")
graph.add_edge("final_agent", END)


# =========================
# PostgreSQL Checkpointer
# =========================
DATABASE_URL = get_database_url()

_conn = psycopg.connect(
    DATABASE_URL,
    autocommit=True,
    row_factory=dict_row
)

checkpointer = PostgresSaver(_conn)
checkpointer.setup()

travel_graph = graph.compile(checkpointer=checkpointer)



# =========================
# Function for FastAPI
# =========================

def run_travel_agent(user_input: str, thread_id: str | None = None):
    if not thread_id:
        thread_id = f"user_{uuid.uuid4().hex}"

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    result = travel_graph.invoke(
        {
            "messages": [
                HumanMessage(content=user_input)
            ],
            "user_query": user_input,
            "flight_results": "",
            "hotel_results": "",
            "itinerary": "",
            "llm_calls": 0
        },
        config=config
    )

    final_answer = result["messages"][-1].content

    return {
        "thread_id": thread_id,
        "answer": final_answer,
        "flight_results": result.get("flight_results", ""),
        "hotel_results": result.get("hotel_results", ""),
        "itinerary": result.get("itinerary", ""),
        "llm_calls": result.get("llm_calls", 0),
    }