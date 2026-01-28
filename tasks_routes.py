"""
Tasks CRM Routes - Module Tâches complet
Created: 28 Janvier 2026
CRUD + export CSV pour les tâches CRM
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import os
import logging
import csv
from io import StringIO
from fastapi.responses import StreamingResponse

# Import centralized auth middleware
from auth_middleware import (
    get_current_user,
    require_admin,
    require_role,
    log_audit_event,
    get_db
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ==========================================
# PYDANTIC MODELS
# ==========================================

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: str = "medium"  # low, medium, high, urgent
    status: str = "pending"  # pending, in_progress, completed, cancelled
    assigned_to: Optional[str] = None
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    tags: Optional[List[str]] = []


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    tags: Optional[List[str]] = None


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def serialize_task(task: dict) -> dict:
    """Serialize task for JSON response"""
    if task.get("_id"):
        task["id"] = str(task.pop("_id"))
    for key in ["created_at", "updated_at", "due_date", "completed_at"]:
        if task.get(key) and isinstance(task[key], datetime):
            task[key] = task[key].isoformat()
    return task


# ==========================================
# TASK ENDPOINTS
# ==========================================

@router.get("")
@router.get("/")
async def list_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[str] = None,
    lead_id: Optional[str] = None,
    limit: int = Query(100, le=500),
    skip: int = 0,
    user: Dict = Depends(get_current_user)
):
    """List all tasks with optional filters"""
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    query = {}
    
    if status:
        query["status"] = status
    if priority:
        query["priority"] = priority
    if assigned_to:
        query["assigned_to"] = assigned_to
    if lead_id:
        query["lead_id"] = lead_id
    
    # Non-admin users can only see their own tasks
    if user.get("role") not in ["admin", "manager"]:
        query["$or"] = [
            {"assigned_to": user["email"]},
            {"created_by": user["email"]}
        ]
    
    tasks = await db.tasks.find(query).sort("due_date", 1).skip(skip).limit(limit).to_list(limit)
    total = await db.tasks.count_documents(query)
    
    return {
        "tasks": [serialize_task(t) for t in tasks],
        "total": total,
        "limit": limit,
        "skip": skip
    }


@router.post("")
@router.post("/")
async def create_task(
    task: TaskCreate,
    user: Dict = Depends(get_current_user)
):
    """Create a new task"""
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    task_doc = task.model_dump()
    task_doc["created_at"] = datetime.now(timezone.utc)
    task_doc["updated_at"] = datetime.now(timezone.utc)
    task_doc["created_by"] = user["email"]
    
    result = await db.tasks.insert_one(task_doc)
    task_doc["id"] = str(result.inserted_id)
    
    # Log audit event
    await log_audit_event(db, "task_created", user["email"], {
        "task_id": task_doc["id"],
        "title": task_doc["title"]
    })
    
    return serialize_task(task_doc)


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    user: Dict = Depends(get_current_user)
):
    """Get a specific task by ID"""
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        task = await db.tasks.find_one({"_id": ObjectId(task_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID format")
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return serialize_task(task)


@router.put("/{task_id}")
@router.patch("/{task_id}")
async def update_task(
    task_id: str,
    update: TaskUpdate,
    user: Dict = Depends(get_current_user)
):
    """Update a task"""
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        existing = await db.tasks.find_one({"_id": ObjectId(task_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID format")
    
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Build update document
    update_doc = {k: v for k, v in update.model_dump().items() if v is not None}
    update_doc["updated_at"] = datetime.now(timezone.utc)
    
    # Track completion
    if update.status == "completed" and existing.get("status") != "completed":
        update_doc["completed_at"] = datetime.now(timezone.utc)
        update_doc["completed_by"] = user["email"]
    
    await db.tasks.update_one(
        {"_id": ObjectId(task_id)},
        {"$set": update_doc}
    )
    
    # Log audit event
    await log_audit_event(db, "task_updated", user["email"], {
        "task_id": task_id,
        "changes": list(update_doc.keys())
    })
    
    updated_task = await db.tasks.find_one({"_id": ObjectId(task_id)})
    return serialize_task(updated_task)


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    user: Dict = Depends(require_role(["admin", "manager"]))
):
    """Delete a task (admin/manager only)"""
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        result = await db.tasks.delete_one({"_id": ObjectId(task_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID format")
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Log audit event
    await log_audit_event(db, "task_deleted", user["email"], {
        "task_id": task_id
    })
    
    return {"message": "Task deleted successfully", "id": task_id}


@router.post("/{task_id}/complete")
async def complete_task(
    task_id: str,
    user: Dict = Depends(get_current_user)
):
    """Mark a task as completed"""
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        result = await db.tasks.update_one(
            {"_id": ObjectId(task_id)},
            {
                "$set": {
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc),
                    "completed_by": user["email"],
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID format")
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"message": "Task marked as completed", "id": task_id}


@router.get("/export/csv")
async def export_tasks_csv(
    status: Optional[str] = None,
    user: Dict = Depends(require_role(["admin", "manager"]))
):
    """Export tasks to CSV"""
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    query = {}
    if status:
        query["status"] = status
    
    tasks = await db.tasks.find(query).sort("created_at", -1).to_list(5000)
    
    # Create CSV in memory
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "id", "title", "description", "status", "priority",
        "assigned_to", "due_date", "created_at", "completed_at"
    ])
    writer.writeheader()
    
    for task in tasks:
        writer.writerow({
            "id": str(task.get("_id", "")),
            "title": task.get("title", ""),
            "description": task.get("description", ""),
            "status": task.get("status", ""),
            "priority": task.get("priority", ""),
            "assigned_to": task.get("assigned_to", ""),
            "due_date": task.get("due_date", ""),
            "created_at": task.get("created_at", ""),
            "completed_at": task.get("completed_at", "")
        })
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=tasks_export_{datetime.now().strftime('%Y%m%d')}.csv"
        }
    )


@router.get("/stats/summary")
async def get_tasks_stats(
    user: Dict = Depends(get_current_user)
):
    """Get task statistics summary"""
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    total = await db.tasks.count_documents({})
    pending = await db.tasks.count_documents({"status": "pending"})
    in_progress = await db.tasks.count_documents({"status": "in_progress"})
    completed = await db.tasks.count_documents({"status": "completed"})
    
    # Overdue tasks
    now = datetime.now(timezone.utc)
    overdue = await db.tasks.count_documents({
        "status": {"$nin": ["completed", "cancelled"]},
        "due_date": {"$lt": now}
    })
    
    # Due today
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    due_today = await db.tasks.count_documents({
        "status": {"$nin": ["completed", "cancelled"]},
        "due_date": {"$gte": today_start, "$lt": today_end}
    })
    
    return {
        "total": total,
        "pending": pending,
        "in_progress": in_progress,
        "completed": completed,
        "overdue": overdue,
        "due_today": due_today,
        "completion_rate": round((completed / total * 100) if total > 0 else 0, 1)
    }
