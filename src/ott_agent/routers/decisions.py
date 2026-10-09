import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ott_agent.database import get_db
from ott_agent.schemas.decision import DecisionSchema
from ott_agent.services.decision_service import DecisionService

router = APIRouter(prefix="/decisions", tags=["Decisions"])


@router.get("/{decision_id}", response_model=DecisionSchema)
def get_decision_detail(decision_id: str, db: Session = Depends(get_db)):
    """Fetch decision detail by decision_id."""
    d_service = DecisionService(db)
    decision = d_service.get_decision(decision_id)
    if not decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision '{decision_id}' not found"
        )

    return DecisionSchema(
        id=decision.id,
        viewer_id=decision.viewer.viewer_id if decision.viewer else decision.viewer_id,
        plan_id=decision.plan_id,
        decision_type=decision.decision_type,
        recommended_action=decision.recommended_action,
        rationale=decision.rationale,
        evidence_refs=json.loads(decision.evidence_refs_json) if decision.evidence_refs_json else [],
        created_at=decision.created_at
    )
