from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PurchaseRecommendationRequest(BaseModel):
    product_id: int
    country: str = Field(default="ES", min_length=2, max_length=2)
    language: str = Field(default="es", min_length=2, max_length=2)


class ReviewInput(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    external_id: Optional[str] = Field(default=None, max_length=255)
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    reviewed_at: Optional[datetime] = None


class ReviewBatchRequest(BaseModel):
    product_id: int
    source: str = Field(min_length=1, max_length=80)
    country: Optional[str] = Field(default=None, min_length=2, max_length=2)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    reviews: list[ReviewInput] = Field(min_length=1, max_length=500)


class ProductAnalysisRequest(BaseModel):
    product_id: int
    country: str = Field(default="ES", min_length=2, max_length=2)
    horizon_days: int = Field(default=30, ge=1, le=365)


class MarketIntelligenceRequest(BaseModel):
    term: str = Field(min_length=2, max_length=100)
    country: str = Field(default="ES", min_length=2, max_length=2)


class CommercialContentRequest(BaseModel):
    product_id: int
    channel: str = Field(default="product_page", min_length=2, max_length=40)


class CustomerSupportRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    product_id: Optional[int] = None


class ExecutiveRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    product_id: Optional[int] = None
    agent: Optional[str] = Field(default="auto", max_length=50)


class AutomationStateRequest(BaseModel):
    is_active: bool
