"""
Pydantic models for data validation and type safety.
These models work with pymongo while providing schema validation.
"""
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict
from bson import ObjectId


class AssignmentCreate(BaseModel):
    """Model for creating a new assignment"""
    title: str = Field(..., min_length=1, max_length=200, description="Assignment title")
    course: Optional[str] = Field(None, max_length=120, description="Course name")
    notes: Optional[str] = Field(None, description="Additional notes")
    due_date: date = Field(..., description="Assignment due date")
    priority: int = Field(default=2, ge=1, le=3, description="Priority level (1-3)")
    estimated_time: Optional[int] = Field(None, ge=1, description="Estimated completion time in minutes")
    completed: bool = Field(default=False, description="Completion status")
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    @field_validator('title')
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        # Ensure title is not just whitespace
        if not v or not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()
    
    @field_validator('course', 'notes')
    @classmethod
    def optional_string_strip(cls, v: Optional[str]) -> Optional[str]:
        # Strip whitespace from optional strings
        if v:
            return v.strip()
        return v


class AssignmentUpdate(BaseModel):
    """Model for updating an existing assignment"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    course: Optional[str] = Field(None, max_length=120)
    notes: Optional[str] = Field(None)
    due_date: Optional[date] = None
    priority: Optional[int] = Field(None, ge=1, le=3)
    estimated_time: Optional[int] = Field(None, ge=1)
    completed: Optional[bool] = None
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    @field_validator('title')
    @classmethod
    def title_not_empty(cls, v: Optional[str]) -> Optional[str]:
        # Ensure title is not just whitespace if provided
        if v is not None and (not v or not v.strip()):
            raise ValueError('Title cannot be empty')
        return v.strip() if v else None


class Assignment(BaseModel):
    """Model representing a complete assignment from the database"""
    id: str = Field(..., description="MongoDB ObjectId as string")
    title: str
    course: Optional[str] = None
    notes: Optional[str] = None
    due_date: str = Field(..., description="Due date in YYYY-MM-DD format")
    priority: int = Field(default=2, ge=1, le=3)
    estimated_time: Optional[int] = None
    completed: bool = Field(default=False)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


def assignment_to_dict(assignment: AssignmentCreate) -> dict:
    """
    Convert a Pydantic AssignmentCreate model to a dictionary for MongoDB insertion.
    
    Args:
        assignment: The AssignmentCreate model
        
    Returns:
        Dictionary ready for MongoDB insertion
    """
    now = datetime.utcnow()
    due_datetime = datetime.combine(assignment.due_date, datetime.min.time())
    
    return {
        "title": assignment.title,
        "course": assignment.course or "",
        "notes": assignment.notes or "",
        "due_date": due_datetime,
        "priority": assignment.priority,
        "estimated_time": assignment.estimated_time,
        "completed": assignment.completed,
        "created_at": now,
        "updated_at": now
    }


def assignment_update_to_dict(assignment: AssignmentUpdate) -> dict:
    """
    Convert a Pydantic AssignmentUpdate model to a dictionary for MongoDB update.
    Only includes fields that were actually set.
    
    Args:
        assignment: The AssignmentUpdate model
        
    Returns:
        Dictionary with only the fields to update
    """
    update_dict = {}
    
    if assignment.title is not None:
        update_dict["title"] = assignment.title
    if assignment.course is not None:
        update_dict["course"] = assignment.course
    if assignment.notes is not None:
        update_dict["notes"] = assignment.notes
    if assignment.due_date is not None:
        update_dict["due_date"] = datetime.combine(assignment.due_date, datetime.min.time())
    if assignment.priority is not None:
        update_dict["priority"] = assignment.priority
    if assignment.estimated_time is not None:
        update_dict["estimated_time"] = assignment.estimated_time
    if assignment.completed is not None:
        update_dict["completed"] = assignment.completed
    
    update_dict["updated_at"] = datetime.utcnow()
    
    return update_dict


def serialize_assignment(doc: dict) -> dict:
    """
    Serialize a MongoDB document to a dictionary suitable for templates.
    
    Args:
        doc: MongoDB document
        
    Returns:
        Dictionary with serialized fields
    """
    return {
        "id": str(doc["_id"]),
        "title": doc.get("title", ""),
        "course": doc.get("course", ""),
        "notes": doc.get("notes", ""),
        "due_date": (
            doc.get("due_date").strftime("%Y-%m-%d") 
            if isinstance(doc.get("due_date"), (datetime, date)) 
            else doc.get("due_date", "")
        ),
        "priority": doc.get("priority", 2),
        "estimated_time": doc.get("estimated_time"),
        "completed": bool(doc.get("completed", False)),
        "created_at": (
            doc.get("created_at").isoformat() 
            if isinstance(doc.get("created_at"), datetime) 
            else None
        ),
        "updated_at": (
            doc.get("updated_at").isoformat() 
            if isinstance(doc.get("updated_at"), datetime) 
            else None
        ),
    }
