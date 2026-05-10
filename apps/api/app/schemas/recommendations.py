# Defines API response models for BookFiend personalized recommendations.

from pydantic import BaseModel


class RecommendationItem(
    BaseModel
):
    title: str
    author: str
    genres: list[str]
    score: float
    similarity_score: float
    reasons: list[str]


class RecommendationResponse(
    BaseModel
):
    profile_book_count: int
    candidate_count: int
    recommendations: list[
        RecommendationItem
    ]