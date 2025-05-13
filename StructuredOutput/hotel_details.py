import os
import json
from typing import List, Optional, Any, Dict, Union
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from langchain_cohere.chat_models import ChatCohere
from langchain.prompts import ChatPromptTemplate
import pprint

load_dotenv()

class HotelDetail(BaseModel):
    name: Optional[str] = Field(default=None, description="The name of the hotel.")
    price: Optional[str] = Field(default=None, description="The final verified price per night (e.g., '₹15000', '$250').")
    rating: Optional[str] = Field(default=None, description="The guest rating, including review count if available (e.g., '4.8 (8,400 reviews)', '4.6').")
    amenities: Optional[List[str]] = Field(default_factory=list, description="List of amenities available at the hotel (e.g., ['free WiFi', 'pool', 'spa']).")
    detail_url: Optional[str] = Field(default=None, description="The direct URL to the hotel's detail page.")

class HotelList(BaseModel):
    hotels: List[HotelDetail] = Field(
        default_factory=list,
        description="A list of ALL extracted hotel details. Each item MUST be a 'HotelDetail' object."
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
    HotelList,
    method="tool_calling"
)

SYSTEM_PROMPT = """You are an expert hotel data extraction engine.
Your primary goal is to accurately invoke the 'HotelList' tool using information extracted from the provided text.
The 'HotelList' tool has one required argument: 'hotels'. This 'hotels' argument MUST be a list, where each item in the list is a 'HotelDetail' object.

The input text may describe multiple distinct hotels. For each distinct hotel you identify:
1.  Create one 'HotelDetail' object.
2.  Meticulously fill in the fields of this 'HotelDetail' object (name, price, rating, amenities, detail_url) based *only* on the information present in the text for that specific hotel.
    -   'name': The full name of the hotel.
    -   'price': The price per night, including currency symbol if available (e.g., "₹25,000", "$150/night").
    -   'rating': The customer rating, including review count if mentioned (e.g., "4.8 (8,400 reviews)").
    -   'amenities': A list of strings representing the amenities (e.g., ["free WiFi", "pool", "spa"]).
    -   'detail_url': The direct URL to the hotel's details or booking page.
3.  Strictly adhere to the field descriptions within the 'HotelDetail' schema. If information for a field is genuinely missing for a hotel in the text, that field should be omitted (or set to null/empty list for amenities) for that 'HotelDetail' object. Do NOT invent or hallucinate information.

After processing ALL distinct hotels found in the text, you MUST call the 'HotelList' tool.
The 'hotels' argument of your 'HotelList' tool call will be the list containing ALL the 'HotelDetail' objects you have created.

Conceptual example of the expected tool invocation:
tool_name: HotelList
tool_arguments: {{
  "hotels": [
    {{
      "name": "Grand City Hotel",
      "price": "$200",
      "rating": "4.5 (1200 reviews)",
      "amenities": ["WiFi", "Pool", "Gym"],
      "detail_url": "https://example.com/grandcity"
    }},
    {{
      "name": "Cozy Inn",
      "price": "€80 per night",
      "rating": "4.2",
      "amenities": ["Breakfast included", "Parking"],
      "detail_url": "https://example.com/cozyinn"
    }}
  ]
}}

If absolutely no hotels can be extracted, call 'HotelList' with an empty 'hotels' list (tool_arguments: {{ "hotels": [] }}).
Your primary task is to correctly populate this 'hotels' list for the 'HotelList' tool based on the input text.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "{input}")
])

def structure_hotels_with_cohere(
    raw_hotel_data_input: Union[List[Dict[str, Any]], str],
    max_input_chars: int = 100000
) -> Optional[List[Dict[str, Any]]]:
    try:
        input_str = json.dumps(raw_hotel_data_input, indent=2) if isinstance(raw_hotel_data_input, list) else str(raw_hotel_data_input)
        input_str = input_str[:max_input_chars]

        print("ℹ️ Invoking LLM for hotel structuring...")
        chain = prompt | structured_llm 
        response_obj = chain.invoke({"input": input_str})

        if isinstance(response_obj, HotelList):
            return [hotel.model_dump(exclude_unset=True, by_alias=False) for hotel in response_obj.hotels]
        else:
            print(f"❌ LLM response was not a HotelList instance as expected. Actual type: {type(response_obj)}")
            if response_obj:
                print(f"   Content of unexpected response: {response_obj!r}")
            return None
    except Exception as e:
        print(f"An unexpected error occurred during hotel structuring: {e}")
        return None
