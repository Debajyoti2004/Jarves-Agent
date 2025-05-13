import os
import json
from typing import List, Optional, Dict
from pydantic import BaseModel, Field, AliasChoices
from dotenv import load_dotenv
from langchain_cohere import ChatCohere
from langchain.prompts import ChatPromptTemplate
import pprint

load_dotenv()

class ProductDetail(BaseModel):
    title: Optional[str] = Field(
        default=None,
        description="Title or name of the product. Capture the full descriptive title as much as possible."
    )
    price: Optional[str] = Field(
        default=None,
        description="Price of the product as shown. If a discounted price is available (e.g., '₹969 (MRP ₹2,699)'), extract the selling price ('₹969')."
    )
    rating: Optional[str] = Field(
        default=None,
        description="Rating value of the product (e.g., extract '4.2' from '4.2 out of 5 stars' or '3.9' from '3.9-star rating').",
        validation_alias=AliasChoices('rating_value', 'rating')
    )
    review_count: Optional[str] = Field(
        default=None,
        description="Total number of reviews as a string (e.g., extract '9919' from '9919 reviewers' or '41' from '41 reviews').",
        validation_alias=AliasChoices('rating_count', 'review_count', 'review', 'reviews')
    )
    url: Optional[str] = Field(
        default=None,
        description="URL to the product page, if explicitly available in the text."
    )
    brand: Optional[str] = Field(
        default=None,
        description="Brand of the product. Infer from the product title or description if not explicitly stated (e.g., 'inphic', 'amazon basics')."
    )
    asin: Optional[str] = Field(
        default=None,
        description="ASIN (Amazon Standard Identification Number) of the product, if explicitly available in the text."
    )
    is_prime: Optional[bool] = Field(
        default=None,
        description="Whether the product is Prime eligible (true if 'Prime eligible' or similar is mentioned, false if explicitly not Prime, null or omit if not mentioned)."
    )

class ProductList(BaseModel):
    products: List[ProductDetail] = Field(
        default_factory=list,
        description="A list of ALL extracted product details. Each item in this list MUST be a 'ProductDetail' object corresponding to a distinct product found in the input text."
    )

COHERE_API_KEY = os.getenv("COHERE_API_KEY")
if not COHERE_API_KEY:
    raise ValueError("COHERE_API_KEY environment variable not set. Please ensure it's in your .env file or environment.")

llm = ChatCohere(
    model="command-r-plus", 
    temperature=0.0, 
    cohere_api_key=COHERE_API_KEY
    )
structured_llm = llm.with_structured_output(
    ProductList,
    method="tool_calling"
)

SYSTEM_PROMPT = """You are an expert extraction engine. Your primary goal is to accurately invoke the 'ProductList' tool using information extracted from the provided text.
The 'ProductList' tool has one required argument: 'products'. This 'products' argument MUST be a list, where each item in the list is a 'ProductDetail' object.

The input text may contain descriptions of multiple distinct products. For each distinct product you identify in the text:
1.  Create one 'ProductDetail' object.
2.  Meticulously fill in the fields of this 'ProductDetail' object (title, price, rating, review_count, url, brand, asin, is_prime) based *only* on the information present in the text for that specific product.
    -   'title': The full descriptive name or title of the product.
    -   'price': The current selling price. For "₹969 (MRP ₹2,699)", extract "₹969".
    -   'rating': The numerical star rating. For "4.2 out of 5 stars", extract "4.2". For "3.9-star rating", extract "3.9".
    -   'review_count': The total number of reviews. For "9919 reviewers", extract "9919". For "41 reviews", extract "41".
    -   'url': The direct URL to the product page, if explicitly mentioned.
    -   'brand': The brand name. Infer from the title if possible (e.g., "inphic", "amazon basics", "Portronics").
    -   'asin': The Amazon Standard Identification Number (ASIN), if explicitly mentioned.
    -   'is_prime': A boolean value: true if the text states "Prime eligible" or similar. False if explicitly "not Prime". Null or omit if not mentioned.
3.  Strictly adhere to the field descriptions within the 'ProductDetail' schema. If information for a field is genuinely missing for a product in the text, that field should be omitted (or set to null) for that product's 'ProductDetail' object. Do NOT invent or hallucinate information.

After processing ALL distinct products found in the text and creating their corresponding 'ProductDetail' objects, you MUST call the 'ProductList' tool.
The 'products' argument of your 'ProductList' tool call will be the list containing ALL the 'ProductDetail' objects you have created.

Conceptual example of the expected tool invocation (what your internal call should look like):
tool_name: ProductList
tool_arguments: {{
  "products": [
    {{
      "title": "Example Product Alpha",
      "price": "₹100",
      "rating": "4.5",
      "review_count": "150",
      "brand": "AlphaBrand",
      "is_prime": true
    }},
    {{
      "title": "Example Product Beta",
      "price": "₹250",
      "rating": "4.0",
      "review_count": "30",
      "brand": "BetaBrand",
      "url": "http://example.com/productB"
    }}
    // ... and so on for every product extracted from the text.
  ]
}}

If, after careful analysis, absolutely no products can be extracted from the text that fit the 'ProductDetail' schema, then and only then should you call 'ProductList' with an empty 'products' list (i.e., tool_arguments: {{ "products": [] }}).
Your primary task is to correctly populate this 'products' list for the 'ProductList' tool based on the input text.
"""

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("human", "Please extract product details from this text:\n\n{raw_data}"),
    ]
)

def structure_products_with_cohere(
    raw_product_data_text: Optional[str], 
    max_input_chars: int = 100000
    ) -> Optional[List[Dict]]:
    if not raw_product_data_text or not isinstance(raw_product_data_text, str):
        print("❌ Invalid input: raw_product_data_text must be a non-empty string.")
        return None

    truncated_data = raw_product_data_text[:max_input_chars]
    chain = prompt | structured_llm

    print("ℹ️ Invoking LLM for structuring...")
    response_obj = None
    try:
        response_obj = chain.invoke({"raw_data": truncated_data})
    except Exception as e:
        print(f"❌ Error during LLM invocation or Pydantic validation: {e}")
        return None

    if isinstance(response_obj, ProductList):
        return [product.model_dump(exclude_unset=True, by_alias=False) for product in response_obj.products]
    else:
        print(f"❌ LLM response was not a ProductList instance as expected. Actual type: {type(response_obj)}")
        if response_obj:
             print(f"   Content of unexpected response: {response_obj!r}")
        return None

