from typing import Literal

from pydantic import BaseModel, Field


class RegionRecommendation(BaseModel):
    region: str
    title: str
    reason: str
    policyCount: int = Field(ge=0)
    endingSoonCount: int = Field(ge=0)
    estimatedValueKrw: int = Field(ge=0)
    score: int = Field(ge=0, le=100)
    styleMatchedCount: int = Field(ge=0)



class TravelAreaRecommendation(BaseModel):
    travelAreaId: str
    travelAreaName: str
    sido: str
    includedCities: list[str]
    summary: str
    tags: list[str]
    reason: str
    policyCount: int = Field(ge=0)
    localPolicyCount: int = Field(ge=0)
    nationwidePolicyCount: int = Field(ge=0)
    endingSoonCount: int = Field(ge=0)
    estimatedValueKrw: int = Field(ge=0)
    score: int = Field(ge=0, le=100)


class TravelAreaRecommendationResponse(BaseModel):
    mode: Literal["sido", "search", "nationwide"]
    sido: str | None = None
    query: str | None = None
    items: list[TravelAreaRecommendation]
    emptyReason: Literal["unsupported_sido", "no_match"] | None = None
