import json
from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ott_agent.database import get_db
from ott_agent.schemas.viewer import ViewerProfileResponse, ViewerStateSchema
from ott_agent.schemas.decision import DecisionSchema
from ott_agent.services.viewer_service import ViewerService
from ott_agent.services.decision_service import DecisionService

router = APIRouter(prefix="/viewers", tags=["Viewers"])


@router.get("/{viewer_id}", response_model=ViewerProfileResponse)
def get_viewer_profile(viewer_id: str, db: Session = Depends(get_db)):
    """Fetch viewer profile by viewer_id."""
    v_service = ViewerService(db)
    viewer = v_service.get_by_viewer_id(viewer_id)
    if not viewer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Viewer '{viewer_id}' not found"
        )
    latest_state = v_service.get_latest_state(viewer.id)

    state_schema = None
    if latest_state:
        state_schema = ViewerStateSchema(
            dialect_preference=latest_state.dialect_preference,
            language_variant=latest_state.language_variant,
            engagement_score=latest_state.engagement_score,
            state_snapshot=json.loads(latest_state.state_snapshot_json) if latest_state.state_snapshot_json else {},
            updated_at=latest_state.updated_at
        )

    return ViewerProfileResponse(
        id=viewer.id,
        viewer_id=viewer.viewer_id,
        external_id=viewer.external_id,
        profile_version=viewer.profile_version,
        created_at=viewer.created_at,
        updated_at=viewer.updated_at,
        current_state=state_schema
    )


@router.get("/{viewer_id}/state", response_model=ViewerStateSchema)
def get_viewer_state(viewer_id: str, db: Session = Depends(get_db)):
    """Fetch current viewer state snapshot."""
    v_service = ViewerService(db)
    viewer = v_service.get_by_viewer_id(viewer_id)
    if not viewer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Viewer '{viewer_id}' not found"
        )
    latest_state = v_service.get_latest_state(viewer.id)
    if not latest_state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No state recorded for viewer '{viewer_id}'"
        )

    return ViewerStateSchema(
        dialect_preference=latest_state.dialect_preference,
        language_variant=latest_state.language_variant,
        engagement_score=latest_state.engagement_score,
        state_snapshot=json.loads(latest_state.state_snapshot_json) if latest_state.state_snapshot_json else {},
        updated_at=latest_state.updated_at
    )


@router.get("/{viewer_id}/decisions", response_model=List[DecisionSchema])
def get_viewer_decisions(viewer_id: str, db: Session = Depends(get_db)):
    """Fetch decision history for viewer."""
    v_service = ViewerService(db)
    d_service = DecisionService(db)

    viewer = v_service.get_by_viewer_id(viewer_id)
    if not viewer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Viewer '{viewer_id}' not found"
        )

    decisions = d_service.get_decisions_for_viewer(viewer.id)
    result = []
    for d in decisions:
        result.append(
            DecisionSchema(
                id=d.id,
                viewer_id=viewer.viewer_id,
                plan_id=d.plan_id,
                decision_type=d.decision_type,
                recommended_action=d.recommended_action,
                rationale=d.rationale,
                evidence_refs=json.loads(d.evidence_refs_json) if d.evidence_refs_json else [],
                created_at=d.created_at
            )
        )
    return result
