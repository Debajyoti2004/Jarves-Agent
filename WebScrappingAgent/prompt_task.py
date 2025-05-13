import math
import json
from typing import Dict, Any

def get_amazon_extraction_task(search_url: str, user_preferences: Dict[str, Any]) -> str:
    pref_parts = []
    specified_criteria_keys = []
    currency_symbol = user_preferences.get("currency_symbol", "$")

    if 'price_max' in user_preferences:
        criteria_text = f"a price ideally not exceeding {currency_symbol}{user_preferences['price_max']}"
        pref_parts.append(criteria_text)
        specified_criteria_keys.append('price_max')
    if 'rating_min' in user_preferences:
        criteria_text = f"a customer rating of at least {user_preferences['rating_min']} stars"
        pref_parts.append(criteria_text)
        specified_criteria_keys.append('rating_min')
    if user_preferences.get('prime_eligible'):
        criteria_text = "eligible for Prime shipping"
        pref_parts.append(criteria_text)
        specified_criteria_keys.append('prime_eligible')
    if 'brand' in user_preferences:
        brand_val = user_preferences['brand']
        criteria_text = None
        if isinstance(brand_val, list):
            brands_str = " or ".join([f"'{b}'" for b in brand_val])
            criteria_text = f"from the brand(s) {brands_str}"
        elif isinstance(brand_val, str):
            criteria_text = f"from the brand '{brand_val}'"
        if criteria_text:
            pref_parts.append(criteria_text)
            specified_criteria_keys.append('brand')
    if 'keywords_must_include' in user_preferences and user_preferences['keywords_must_include']:
        keywords_str = ", ".join([f"'{k}'" for k in user_preferences['keywords_must_include']])
        criteria_text = f"whose title or details include the keywords: {keywords_str}"
        pref_parts.append(criteria_text)
        specified_criteria_keys.append('keywords_must_include')

    preference_description = " and ".join(pref_parts) if pref_parts else "any suitable product"
    preference_count = len(specified_criteria_keys)
    match_threshold_desc = f"at least half (around 50% or more)" if preference_count > 1 else "all"
    max_results_to_describe = user_preferences.get('max_results', 5)


    prompt = f"""
Objective: Analyze the Amazon search results page ({search_url}). For each product listing visible, describe its key details as you see them. Focus on products that seem to align with the user's general interest, but describe several listings.

User Preferences Summary (for your general awareness, not strict filtering for this description task): The user is generally interested in products with {preference_description}.

Detailed Instructions:
1. You are currently viewing an Amazon search results page: {search_url}.
2. Systematically examine each primary product listing card displayed in the main search results area.
3. For each product listing card (up to about {max_results_to_describe} listings, or more if few are on the page):
    a. State the product's title or name as clearly as possible.
    b. Beneath the title, write a short paragraph describing all the information you can clearly see on the card. This includes:
        - The displayed price (e.g., "Price is $29.99").
        - Customer rating if visible (e.g., "Rating appears to be 4.5 out of 5 stars from 1234 reviews").
        - Prime eligibility (e.g., "It shows a Prime badge" or "No Prime badge visible").
        - Brand if clearly visible (e.g., "The brand seems to be ExampleBrand").
        - Any other prominent details or badges visible on the card (e.g., "It has a 'Best Seller' badge" or "Sponsored listing noted").
    c. Do NOT click into the product detail page for this task. Describe only what is visible on the search results card.
4. After describing one product card, move to the next, repeating step 3.
5. If there are multiple pages of results, you can describe a few products from the first page. Pagination is not required for this descriptive task unless very few products are on the first page.
6. Final Output:
    - Your response should be a single block of text.
    - For each product, start with a clear identifier like "Product Card 1: [Product Title]" or "Observed Product: [Product Title]".
    - Follow with the descriptive paragraph for that product.
    - Separate descriptions of different products with a blank line or a clear separator.
    - Do not use any special function calls like 'final_result'. Just provide the descriptive text.

Example of how to describe one product:

Product Card 1: Super Bright LED Desk Lamp
This lamp is listed at $25.99. It has a customer rating of 4.7 out of 5 stars based on over 1500 reviews and shows a Prime eligibility badge. The brand appears to be 'LampCo'. There's also a small 'Energy Efficient' icon visible.

Product Card 2: Ergonomic Office Chair
The price shown for this chair is $189.00. I can see a rating of 4.2 stars from 850 reviews. It does not appear to be Prime eligible from the card. The brand is 'ComfySeating'.

(and so on for other products)
"""
    return prompt

def get_hotel_extraction_task(search_url: str, user_preferences: Dict[str, Any]) -> str:
    pref_parts = []
    currency_symbol = user_preferences.get('currency_symbol', '₹')

    if 'price_max' in user_preferences:
        pref_parts.append(f"a price per night ideally not exceeding around {currency_symbol}{user_preferences['price_max']}")
    if 'rating_min' in user_preferences:
        pref_parts.append(f"a guest rating of at least {user_preferences['rating_min']} stars")
    if 'amenities' in user_preferences and user_preferences['amenities']:
        amenities_str = ", ".join(user_preferences['amenities'])
        pref_parts.append(f"amenities including: {amenities_str}")
    if 'property_type' in user_preferences:
        pref_parts.append(f"property type matching '{user_preferences['property_type']}'")
    if 'guests' in user_preferences:
         pref_parts.append(f"suitable for {user_preferences['guests']} guest(s)")
    if 'dates' in user_preferences:
        pref_parts.append(f"for the dates: {user_preferences['dates']}")

    preference_description = " and ".join(pref_parts) if pref_parts else "any suitable option"
    max_results_to_describe = user_preferences.get('max_results', 3)


    prompt = f"""
Objective: Analyze the Google Travel hotel search results page ({search_url}). For each hotel listing visible, describe its key details as you see them on the card.

User Preferences Summary (for your general awareness): The user is generally interested in hotels with {preference_description}.

Detailed Instructions:
1. Navigate to and carefully examine the Google Travel search results page: {search_url}. Apply date/guest filters if they are part of the URL or if easily applicable without deep interaction.
2. Systematically examine each primary hotel listing card displayed.
3. For each hotel listing card (up to about {max_results_to_describe} listings):
    a. State the hotel's name as clearly as possible.
    b. Beneath the name, write a short paragraph describing all the information you can clearly see on the card. This includes:
        - The displayed price per night (e.g., "The price shown is ₹8,500 per night").
        - Guest rating if visible (e.g., "It has a guest rating of 4.2 from 1,200 reviews" or "Rating: 8.5/10").
        - Key amenities or features highlighted on the card (e.g., "Highlights include 'Free WiFi', 'Pool', and 'Free breakfast'").
        - Any special offers or tags (e.g., "Shows a 'Deal' tag" or "Listed as 'Great value'").
        - The general location or neighborhood if mentioned on the card.
    c. Do NOT click into the hotel's detail page for this task. Describe only what is visible on the search results card.
4. After describing one hotel card, move to the next, repeating step 3.
5. If there are multiple pages of results, you can describe a few hotels from the first page.
6. Final Output:
    - Your response should be a single block of text.
    - For each hotel, start with "Hotel Listing: [Hotel Name]".
    - Follow with the descriptive paragraph for that hotel.
    - Separate descriptions of different hotels with a blank line.
    - Do not use any special function calls like 'final_result'. Just provide the descriptive text.

Example of how to describe one hotel:

Hotel Listing: Grand Plaza Hotel
The card shows a price of $150 per night. It has a guest rating of 4.5 stars from over 2,000 reviews. Key amenities listed are 'Pool', 'Gym', and 'Restaurant'. It's located in the 'Downtown Core'.

Hotel Listing: Seaside Inn
This inn is priced at $95 per night. The rating is 4.0 based on 500 reviews. 'Free parking' and 'Pet-friendly' are highlighted on the card.
"""
    return prompt


def get_flight_extraction_task(search_url: str, user_preferences: Dict[str, Any]) -> str:
    pref_parts = []
    if 'price_max' in user_preferences:
        pref_parts.append(f"price <= {user_preferences.get('currency_symbol', '$')}{user_preferences['price_max']}")
    if 'stops_max' in user_preferences:
        pref_parts.append(f"max stops per leg <= {user_preferences['stops_max']}")
    if 'airline_preference' in user_preferences:
        pref_parts.append(f"airline is {user_preferences['airline_preference']}")
    if 'departure_time_window' in user_preferences:
         pref_parts.append(f"outbound departure {user_preferences['departure_time_window']}")
    if 'arrival_time_window' in user_preferences:
         pref_parts.append(f"return arrival {user_preferences['arrival_time_window']}")
    if 'duration_max_hours' in user_preferences:
        pref_parts.append(f"max duration/leg <= {user_preferences['duration_max_hours']}h")
    if 'cabin_class' in user_preferences:
        pref_parts.append(f"cabin is {user_preferences['cabin_class']}")
    if 'passengers' in user_preferences:
         pref_parts.append(f"for {user_preferences['passengers']} passenger(s)")

    preference_description = " and ".join(pref_parts) if pref_parts else "any reasonable option"
    max_results_to_describe = user_preferences.get('max_results', 3)

    prompt = f"""
Objective: Analyze the flight search results page ({search_url}). For each distinct flight itinerary option visible, describe its key details as you see them.

User Preferences Summary (for your general awareness): The user is generally interested in flights with {preference_description}.

Detailed Instructions:
1. You are on a flight search results page ({search_url}). Ensure the results match the core origin, destination, and dates if possible from the URL.
2. Systematically examine each primary flight itinerary option presented.
3. For each flight itinerary (up to about {max_results_to_describe} options):
    a. Clearly identify the itinerary, perhaps by the airline(s) and price.
    b. Beneath this identifier, write a paragraph describing the visible details for BOTH the outbound and return legs (if it's a round trip). This includes:
        - Airline(s) involved.
        - Departure and arrival times and airports (e.g., "Departs JFK at 8:00 AM, arrives LAX at 11:30 AM").
        - Number of stops (e.g., "Non-stop" or "1 stop in Chicago").
        - Total duration of the leg if shown (e.g., "Duration: 5h 30m").
        - The total price for the round trip.
        - Any other prominent details like "Separate tickets" or specific aircraft type if visible.
4. After describing one itinerary, move to the next, repeating step 3.
5. If there are many options, focus on the first few distinct ones. Pagination is not strictly required.
6. Final Output:
    - Your response should be a single block of text.
    - For each itinerary, start with "Flight Option: [Airlines] - [Price]" or similar.
    - Follow with the descriptive paragraph for that itinerary.
    - Separate descriptions of different itineraries with a blank line.
    - Do not use any special function calls like 'final_result'. Just provide the descriptive text.

Example of how to describe one flight itinerary:

Flight Option: Delta - $350
The outbound flight on Delta departs from JFK at 7:00 AM and arrives at MIA at 10:00 AM, it's non-stop. The return flight, also on Delta, departs MIA at 6:00 PM and arrives at JFK at 9:00 PM, also non-stop. The total price is $350.

Flight Option: American Airlines - $320 (1 stop)
For the outbound journey, American Airlines departs LGA at 9:30 AM, has 1 stop in CLT, and arrives in MIA at 3:00 PM. The return leg on American Airlines departs MIA at 4:00 PM, also has 1 stop in CLT, and arrives at LGA at 9:30 PM. The price is $320. It notes 'Operated by PSA Airlines' for one segment.
"""
    return prompt