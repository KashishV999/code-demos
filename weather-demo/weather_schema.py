

from pydantic import BaseModel, Field


class WeatherSchema(BaseModel):
    location: str = Field(..., description="The location of the place")
    date: str = Field(..., description="The date on which the weather data need to be checked it need to in YYYY-MM-DD format example : 2026-08-29 , any other format is invalid")

