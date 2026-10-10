> [!IMPORTANT]
> **This repository has moved.** TripMate AI now lives in one repo, [`nishantrv/TripMate-AI`](https://github.com/nishantrv/TripMate-AI), with each version on its own branch.
> This repo is **v2**, now on the [`v2-mcp`](https://github.com/nishantrv/TripMate-AI/tree/v2-mcp) branch. This copy is archived and read-only.

<div align="center">

# ✈️ TripMate AI: MCP Edition

### A multi-agent travel planner whose agents use their tools through the Model Context Protocol

*Describe a trip in one sentence and get flights, hotels, live weather and a day-by-day itinerary.<br/>
Each data source is an MCP server: one remote, one launched through `uvx`, and one built for this project.*

<br/>

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1.2-1C3C3C)
![MCP](https://img.shields.io/badge/MCP-3%20servers-7C3AED)
![FastMCP](https://img.shields.io/badge/FastMCP-custom%20server-7C3AED)
![Groq](https://img.shields.io/badge/Groq-gpt--oss--20b-F55036)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-checkpointer-4169E1?logo=postgresql&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)

</div>

---

## 💡 Why this project

Planning a trip means jumping between flight sites, hotel searches, weather apps and a notes file. TripMate AI does it with **five specialised agents** in a LangGraph pipeline.

The interesting part is **how the agents reach the outside world**. Instead of hard-coding API clients, every external capability is an **MCP server** loaded through `langchain-mcp-adapters`. You can add, swap or remove a data source in config, without editing agent code.

> 🔁 **This is v2.** [`Multi-Agent-With-LangGraphs-LangSmith`](https://github.com/nishantrv/Multi-Agent-With-LangGraphs-LangSmith) is v1, which uses hand-written Python tools. Comparing the two shows the move from bespoke tool code to the MCP standard.

---

## 🧭 Architecture

```mermaid
flowchart LR
    U([👤 Traveller]) --> API[FastAPI<br/>POST /api/travel]
    API --> G

    subgraph G[LangGraph StateGraph · PostgresSaver checkpointer]
        direction LR
        F[✈️ Flight agent] --> H[🏨 Hotel agent] --> W[🌦️ Weather agent] --> I[🗺️ Itinerary agent] --> Z[📝 Final agent]
    end

    F -. list_airports / list_airlines .-> AV[(AviationStack MCP<br/>stdio · uvx)]
    H -. tavily_search .-> TV[(Tavily MCP<br/>remote · streamable HTTP)]
    W -. get_current_weather / get_forecast .-> WX[(Custom Weather MCP<br/>stdio · FastMCP + OpenWeather)]

    Z --> API --> U
```

| Agent | What it does |
|---|---|
| ✈️ **Flight** | Pulls airports and airlines from the AviationStack MCP and asks the LLM for likely routes, carriers, duration, fare range and booking advice |
| 🏨 **Hotel** | Runs a Tavily web search over MCP for accommodation that matches the request |
| 🌦️ **Weather** | Uses the LLM to extract the destination, then calls the **custom FastMCP server** for current conditions and a 5-step forecast |
| 🗺️ **Itinerary** | Combines flights, hotels and weather into a practical, budget-aware plan |
| 📝 **Final** | Writes the answer in seven sections: summary, flights, hotels, weather, day-by-day plan, budget and recommendations |

---

## 🔌 Three MCP transports in one app

| Server | Transport | How it runs |
|---|---|---|
| **Tavily** | `streamable_http` | Hosted remote MCP at `mcp.tavily.com` |
| **AviationStack** | `stdio` | Third-party package launched on demand with `uvx aviationstack-mcp` |
| **Weather** | `stdio` | **Built for this project.** `custom_weather_mcp_server.py` is a `FastMCP` server that wraps OpenWeather. It starts with the same Python interpreter as the app. |

Design details in `mcp_client.py`:
- **Each server is loaded lazily and separately.** If AviationStack is down, hotel search still works.
- **Tool handles are cached** after the first load, so each request doesn't reconnect.
- **Error messages are specific.** A missing tool error lists the tools that *are* available, which makes debugging fast.

---

## 🧠 Conversation memory

The graph is compiled with LangGraph's **`PostgresSaver`**, so each `thread_id` keeps its state across requests and server restarts. The API returns the `thread_id` so the client can continue the same conversation. SSL is enforced automatically (`sslmode=require`), which suits managed Postgres such as Render.

---

## 🚀 Quickstart

```bash
git clone https://github.com/nishantrv/MulitAgent-With-MCPs.git
cd MulitAgent-With-MCPs
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install uv                                         # provides `uvx` for the AviationStack MCP server
```

Create a `.env` file:

```ini
GROQ_API_KEY=...
TAVILY_API_KEY=...
AVIATIONSTACK_API_KEY=...
OPENWEATHER_API_KEY=...
DATABASE_URL=postgresql://user:password@host:5432/travel_db
```

```bash
python app.py                 # → http://127.0.0.1:8000
python test.py                # check which MCP servers connect and list their tools
```

**With Docker:**

```bash
docker build -t tripmate-mcp .
docker run --env-file .env -p 8000:8000 tripmate-mcp
```

### API

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/` | Web UI |
| `POST` | `/api/travel` | `{"message": "...", "thread_id": "optional"}` returns answer, flights, hotels, itinerary, `llm_calls` and `thread_id` |
| `GET` | `/health` | Liveness check |

```bash
curl -X POST http://127.0.0.1:8000/api/travel \
  -H "Content-Type: application/json" \
  -d '{"message":"Plan a 4-day trip from Dublin to Tokyo in October on a $2000 budget"}'
```

---

## 🗂️ Project layout

```
app.py                        FastAPI app + UI routes
backend.py                    LangGraph state, five agents, Postgres checkpointer
mcp_client.py                 MultiServerMCPClient: Tavily · AviationStack · Weather
custom_weather_mcp_server.py  FastMCP server wrapping OpenWeather
templates/ · static/          Web UI (HTML / CSS / JS)
test.py · mcp_client_test.py  MCP connectivity checks
Dockerfile
```

---

## 🧰 Tech stack

**LangGraph** · **LangChain** · **langchain-mcp-adapters** · **MCP / FastMCP** · **Groq** (`openai/gpt-oss-20b`) · **PostgreSQL** (`langgraph-checkpoint-postgres`) · **FastAPI** · **Jinja2** · **Tavily** · **AviationStack** · **OpenWeather** · **Docker**

---

<div align="center">

Built by **[Nishant](https://github.com/nishantrv)**. If this was useful, a ⭐ is appreciated.

</div>
