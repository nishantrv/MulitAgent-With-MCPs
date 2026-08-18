from tavily_tool import tavily_search
from flight_tool import search_flights
# res = tavily_search("Best travel destinations in Europe")
# print(res)

res = search_flights("Plan a 7 days trip to Italy with a budget of $2000, including flights, accommodation, and activities.")
print(res)