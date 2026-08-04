from google.genai import types
from geopy.geocoders import Nominatim
import requests
from agents import function_tool
from weather_schema import WeatherSchema

# Simple function to get the weather forecast for a given location and date
geolocator = Nominatim(user_agent="weather-app") 

@function_tool 
def get_weather_forecast(weather_schema: WeatherSchema):
    
    location = geolocator.geocode(weather_schema.location)
    if location:
        try:
            response = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={location.latitude}&longitude={location.longitude}&hourly=temperature_2m&start_date={weather_schema.date}&end_date={weather_schema.date}")
            data = response.json()
            return {time: temp for time, temp in zip(data["hourly"]["time"], data["hourly"]["temperature_2m"])}
        except Exception as e:
            return {"error": str(e)}
    else:
        return {"error": "Location not found"}
    
    
# def main():
#     test_cases = [
#         ("Toronto", "August 2 2026"),
#         # ("350 5th Ave, New York, NY", "2026-08-04"),
#         # ("Nonexistent Place Xyz123", "2026-08-04"),  # should hit the "not found" branch
#     ]

#     for location, date in test_cases:
#         print(f"\n--- Testing: location={location!r}, date={date!r} ---")
#         result = get_weather_forecast(location, date)
#         if "error" in result:
#             print("Error:", result["error"])
#         else:
#             # just show first 3 hourly entries so output isn't huge
#             preview = dict(list(result.items())[:3])
#             print(f"Got {len(result)} hourly readings. Sample:", preview)


# if __name__ == "__main__":
#     main()
    
    