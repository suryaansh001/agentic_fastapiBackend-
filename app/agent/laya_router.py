"""Laya classification endpoints (routing + lead scoring).

These expose the classifier directly so the routing decisions can be
inspected and tuned without running a full agent turn.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.agent.laya import LayaClassificationError, get_laya_classifier
from app.dependencies.auth import get_current_user, CurrentUser

router = APIRouter(prefix="/api/agents/laya", tags=["laya"])


class ClassifyRequest(BaseModel):
    message: str
    context: Optional[dict] = None


class ClassifyLeadRequest(BaseModel):
    state: dict


@router.post("/classify")
async def classify(
    request: ClassifyRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    classifier = get_laya_classifier()
    if not classifier.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Laya is not configured",
        )
    try:
        result = await classifier.classify_agent_route(
            request.message, request.context
        )
    except LayaClassificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        )
    return {
        "choice": result.choice,
        "route": result.route,
        "mode": result.mode,
        "operation": result.operation,
        "chart_type": result.chart_type,
        "confidence": result.confidence,
        "probabilities": result.probabilities,
        "provider": result.provider,
    }


@router.post("/classify-lead")
async def classify_lead(
    request: ClassifyLeadRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    classifier = get_laya_classifier()
    if not classifier.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Laya is not configured",
        )
    try:
        result = await classifier.classify_lead(request.state)
    except LayaClassificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        )
    return {
        "score": result.score,
        "status": result.status,
        "qualifies": result.qualifies,
        "confidence": result.confidence,
        "provider": result.provider,
    }
