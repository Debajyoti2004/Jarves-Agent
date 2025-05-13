import os
import json
from typing import List, Optional, Any, Dict, Union
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from langchain_cohere.chat_models import ChatCohere
from langchain.prompts import ChatPromptTemplate
import pprint

load_dotenv()

class FlightLegDetail(BaseModel):
    departure_datetime: Optional[str] = Field(None, description="Departure date and time (YYYY-MM-DD HH:MM)")
    arrival_datetime: Optional[str] = Field(None, description="Arrival date and time (YYYY-MM-DD HH:MM)")
    origin_airport: Optional[str] = Field(None, description="Origin airport code (e.g., JFK)")
    destination_airport: Optional[str] = Field(None, description="Destination airport code (e.g., LHR)")
    airline: Optional[str] = Field(None, description="Operating airline name")
    duration: Optional[str] = Field(None, description="Flight duration (e.g., 8h 15m)")
    num_stops: Optional[int] = Field(None, description="Number of stops (e.g., 0 for non-stop, 1 for one stop).", ge=0)
    stop_details: Optional[str] = Field(None, description="Details of stops if num_stops > 0 (e.g., 'AMS (2h layover)' or 'CDG (1h 30m)'). Use null or omit if non-stop.")

class FlightExtractionResult(BaseModel):
    outbound_flight: Optional[FlightLegDetail] = Field(None, description="Details of the outbound flight leg")
    return_flight: Optional[FlightLegDetail] = Field(None, description="Details of the return flight leg (if applicable, for round trips)")
    total_price: Optional[str] = Field(None, description="Total price for the itinerary (e.g., '$1200', '€950')")
    currency: Optional[str] = Field(None, description="Currency code (e.g., USD, EUR)")
    details_url: Optional[str] = Field(None, description="URL of the search result or booking page for this itinerary")

class FlightItineraryList(BaseModel):
    itineraries: List[FlightExtractionResult] = Field(
        default_factory=list,
        description="A list of ALL extracted flight itineraries. Each item MUST be a 'FlightExtractionResult' object."
    )

COHERE_API_KEY = os.getenv("COHERE_API_KEY")
if not COHERE_API_KEY:
    raise ValueError("COHERE_API_KEY environment variable not set.")

llm_base = ChatCohere(
    cohere_api_key=COHERE_API_KEY,
    model="command-r-plus",
    temperature=0.0
)

structured_llm = llm_base.with_structured_output(
    FlightItineraryList,
    method="tool_calling"
)

SYSTEM_PROMPT = """You are an expert flight itinerary extraction engine.
Your primary goal is to accurately invoke the 'FlightItineraryList' tool using information extracted from the provided text.
The 'FlightItineraryList' tool has one required argument: 'itineraries'. This 'itineraries' argument MUST be a list, where each item in the list is a 'FlightExtractionResult' object.

The input text may describe multiple distinct flight options or itineraries. For each distinct itinerary you identify:
1.  Create one 'FlightExtractionResult' object.
2.  Within this 'FlightExtractionResult', create 'FlightLegDetail' objects for 'outbound_flight' and, if applicable, 'return_flight'.
3.  Meticulously fill in the fields of these objects (e.g., departure_datetime, arrival_datetime, origin_airport, destination_airport, airline, duration, num_stops, stop_details, total_price, currency, details_url) based *only* on the information present in the text for that specific itinerary.
    -   'departure_datetime'/'arrival_datetime': Use "YYYY-MM-DD HH:MM" format.
    -   'num_stops': If "Non-stop" or "Direct", use 0.
    -   'stop_details': Provide if num_stops > 0. Otherwise, omit or use null.
    -   'total_price': Include the currency symbol if present in the text, e.g., "$1150".
    -   'currency': Extract the currency code, e.g., "USD", "EUR".
4.  Strictly adhere to the field descriptions within the schemas. If information for a field is genuinely missing for an itinerary or leg in the text, that field should be omitted (or set to null) for that object. Do NOT invent or hallucinate information.

After processing ALL distinct itineraries found in the text, you MUST call the 'FlightItineraryList' tool.
The 'itineraries' argument of your 'FlightItineraryList' tool call will be the list containing ALL the 'FlightExtractionResult' objects you have created.

Conceptual example of the expected tool invocation:
tool_name: FlightItineraryList
tool_arguments: {{
  "itineraries": [
    {{
      "outbound_flight": {{
        "departure_datetime": "2025-07-10 19:45",
        "arrival_datetime": "2025-07-11 08:30",
        "origin_airport": "JFK",
        "destination_airport": "LHR",
        "airline": "British Airways",
        "duration": "7h 45m",
        "num_stops": 0
      }},
      "return_flight": {{
        "departure_datetime": "2025-07-20 11:00",
        "arrival_datetime": "2025-07-20 14:15",
        "origin_airport": "LHR",
        "destination_airport": "JFK",
        "airline": "British Airways",
        "duration": "8h 15m",
        "num_stops": 0
      }},
      "total_price": "$1150",
      "currency": "USD",
      "details_url": "https://example.com/booking/ba1"
    }}
  ]
}}

If absolutely no flight itineraries can be extracted, call 'FlightItineraryList' with an empty 'itineraries' list (tool_arguments: {{ "itineraries": [] }}).
Your primary task is to correctly populate this 'itineraries' list for the 'FlightItineraryList' tool based on the input text.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "{input}")
])

def structure_flight_list_with_cohere(
    raw_flight_list_input: Union[List[Dict[str, Any]], str],
    max_input_chars: int = 100000
) -> Optional[List[Dict[str, Any]]]:
    try:
        input_str = json.dumps(raw_flight_list_input, indent=2) if isinstance(raw_flight_list_input, list) else str(raw_flight_list_input)
        input_str = input_str[:max_input_chars]

        print("ℹ️ Invoking LLM for flight structuring...")
        chain = prompt | structured_llm
        response_obj = chain.invoke({"input": input_str})

        if isinstance(response_obj, FlightItineraryList):
            return [itinerary.model_dump(exclude_unset=True, by_alias=False) for itinerary in response_obj.itineraries]
        else:
            print(f"❌ LLM response was not a FlightItineraryList instance as expected. Actual type: {type(response_obj)}")
            if response_obj:
                print(f"   Content of unexpected response: {response_obj!r}")
            return None
    except Exception as e:
        print(f"An unexpected error occurred during flight structuring: {e}")
        return None
