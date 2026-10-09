import json
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from ott_agent.database import get_db
from ott_agent.services.agent_service import ViewerAgentService
from ott_agent.services.viewer_service import ViewerService
from ott_agent.services.evidence_service import EvidenceService
from ott_agent.services.plan_service import PlanService
from ott_agent.services.decision_service import DecisionService
from ott_agent.models import Decision, Plan, Goal, ViewerFact

router = APIRouter(tags=["Agent & Audit"])


class TriggerRequest(BaseModel):
    viewer_id: str
    trigger_event_id: Optional[str] = None


@router.post("/agent/trigger", status_code=status.HTTP_200_OK)
def process_agent_trigger(req: TriggerRequest, db: Session = Depends(get_db)):
    """Process an app-open trigger for a viewer and generate a decision."""
    agent = ViewerAgentService(db)
    result = agent.process_app_open_trigger(
        viewer_id=req.viewer_id,
        trigger_event_id=req.trigger_event_id
    )
    return result


@router.get("/viewers/{viewer_id}/goal-plan")
def get_viewer_goal_plan(viewer_id: str, db: Session = Depends(get_db)):
    """Read current goal and active plan for a viewer."""
    v_svc = ViewerService(db)
    p_svc = PlanService(db)

    viewer = v_svc.get_by_viewer_id(viewer_id)
    if not viewer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Viewer '{viewer_id}' not found"
        )

    active_plan = p_svc.get_active_plan(viewer.id)
    if not active_plan:
        return {
            "viewer_id": viewer_id,
            "has_active_plan": False,
            "goal": None,
            "plan": None
        }

    goal = db.execute(select(Goal).where(Goal.id == active_plan.goal_id)).scalar_one_or_none()

    return {
        "viewer_id": viewer_id,
        "has_active_plan": True,
        "goal": {
            "goal_id": goal.id if goal else None,
            "goal_code": goal.goal_code if goal else None,
            "version": goal.version if goal else 1,
            "description": goal.description if goal else None
        },
        "plan": {
            "plan_id": active_plan.id,
            "plan_status": active_plan.plan_status,
            "steps": json.loads(active_plan.steps_json) if active_plan.steps_json else [],
            "created_at": active_plan.created_at.isoformat()
        }
    }


@router.get("/viewers/{viewer_id}/evidence")
def get_viewer_evidence(viewer_id: str, db: Session = Depends(get_db)):
    """View evidence provenance, freshness, and conflict explanations for a viewer."""
    v_svc = ViewerService(db)
    ev_svc = EvidenceService(db)

    viewer = v_svc.get_by_viewer_id(viewer_id)
    if not viewer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Viewer '{viewer_id}' not found"
        )

    dialect_val, dialect_src, dialect_conflict, dialect_hist = ev_svc.resolve_effective_fact(viewer.id, "dialect_preference")
    sub_val, sub_src, sub_conflict, sub_hist = ev_svc.resolve_effective_fact(viewer.id, "subscription_status")

    all_facts = db.execute(select(ViewerFact).where(ViewerFact.viewer_id == viewer.id)).scalars().all()

    return {
        "viewer_id": viewer_id,
        "effective_facts": {
            "dialect_preference": {
                "value": dialect_val,
                "source": dialect_src,
                "has_conflict": dialect_conflict,
                "history": dialect_hist
            },
            "subscription_status": {
                "value": sub_val,
                "source": sub_src,
                "has_conflict": sub_conflict,
                "history": sub_hist
            }
        },
        "total_facts_recorded": len(all_facts)
    }


@router.get("/decisions/{decision_id}/audit")
def get_decision_audit(decision_id: str, db: Session = Depends(get_db)):
    """Inspect full machine-readable audit record for a decision."""
    d_svc = DecisionService(db)
    decision = d_svc.get_decision(decision_id)
    if not decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision '{decision_id}' not found"
        )

    agent = ViewerAgentService(db)
    viewer_ext_id = decision.viewer.viewer_id if decision.viewer else decision.viewer_id
    return agent._build_audit_payload(decision, viewer_ext_id)
