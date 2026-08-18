# from tavily_tool import tavily_search
# from flight_tool import search_flights
from backend import run_travel_agent
# res = tavily_search("Best travel destinations in Europe")
# print(res)

# res = search_flights("Plan a 7 days trip to Italy with a budget of $2000, including flights, accommodation, and activities.")
# print(res)

user_input = input("Enter travel request:")

res = run_travel_agent(
    user_input = user_input,
    thread_id = "test_user"
)
print("\nFinal Response \n")
print(res["answer"])