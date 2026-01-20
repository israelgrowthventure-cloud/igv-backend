"""
CRM Data Models - Complete IGV CRM System
Production-ready schemas for MongoDB collections
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


# ==========================================
# ENUMS & CONSTANTS
# ==========================================

class LeadStatus(str, Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    PENDING_QUOTA = "PENDING_QUOTA"
    CONVERTED = "CONVERTED"
    LOST = "LOST"


class LeadStage(str, Enum):
    ANALYSIS_REQUESTED = "analysis_requested"
    ANALYSIS_SENT = "analysis_sent"
    CALL_SCHEDULED = "call_scheduled"
    QUALIFICATION = "qualification"
    PROPOSAL_SENT = "proposal_sent"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"


class ExpansionType(str, Enum):
    FRANCHISE = "franchise"
    BRANCH = "branch"
    MASTER_FRANCHISE = "master_franchise"
    DIRECT = "direct"
    OTHER = "other"


class Sector(str, Enum):
    RETAIL = "retail"
    FOOD = "food"
    SERVICES = "services"
    TECH = "tech"
    HOSPITALITY = "hospitality"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    OTHER = "other"


class Format(str, Enum):
    FLAGSHIP = "flagship"
    CORNER = "corner"
    POPUP = "pop_up"
    BOUTIQUE = "boutique"
    RESTAURANT = "restaurant"
    KIOSK = "kiosk"
    OTHER = "other"


class Priority(str, Enum):
    A = "A"  # High priority
    B = "B"  # Medium priority
    C = "C"  # Low priority


class UserRole(str, Enum):
    ADMIN = "admin"
    SALES = "sales"
    VIEWER = "viewer"


class ActivityType(str, Enum):
    NOTE = "note"
    CALL = "call"
    EMAIL = "email"
    MEETING = "meeting"
    STATUS_CHANGE = "status_change"
    STAGE_CHANGE = "stage_change"
    CONVERSION = "conversion"
    EXPORT = "export"
    ANALYSIS_REQUESTED = "analysis_requested"
    ANALYSIS_SENT = "analysis_sent"


class ConsentType(str, Enum):
    ANALYTICS = "analytics"
    MARKETING = "marketing"
    FUNCTIONAL = "functional"


# ==========================================
# LEAD MODEL
# ==========================================

class Lead(BaseModel):
    """Complete Lead model with IGV-specific fields"""
    
    # Basic Info
    email: EmailStr
    brand_name: str
    name: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    position: Optional[str] = None
    
    # Status & Stage
    status: LeadStatus = LeadStatus.NEW
    stage: LeadStage = LeadStage.ANALYSIS_REQUESTED
    priority: Priority = Priority.B
    
    # IGV-Specific Fields
    expansion_type: Optional[ExpansionType] = None
    sector: Optional[Sector] = None
    format: Optional[Format] = None
    budget_estimated: Optional[float] = None
    target_city: Optional[str] = None
    timeline: Optional[str] = None  # "0-3m", "3-6m", "6-12m", "12m+"
    decision_makers: Optional[List[Dict[str, str]]] = []  # [{name, role}]
    kosher_status: Optional[bool] = None
    focus_notes: Optional[str] = None
    
    # Tracking
    language: str = "fr"
    owner_id: Optional[str] = None
    owner_email: Optional[str] = None
    tags: List[str] = []
    score: Optional[int] = None
    
    # Attribution
    source: Optional[str] = None  # "website", "newsletter", "referral"
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_term: Optional[str] = None
    utm_content: Optional[str] = None
    referrer: Optional[str] = None
    landing_page: Optional[str] = None
    
    # Technical
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity_at: Optional[datetime] = None
    last_contacted_at: Optional[datetime] = None
    
    # Meta
    request_count: int = 0
    activity_count: int = 0
    converted_to_contact_id: Optional[str] = None
    converted_to_opportunity_id: Optional[str] = None


# ==========================================
# OPPORTUNITY MODEL (Pipeline)
# ==========================================

class Opportunity(BaseModel):
    """Sales Opportunity in Pipeline"""
    
    name: str  # Deal name
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    company_id: Optional[str] = None
    
    # Pipeline
    stage: LeadStage = LeadStage.QUALIFICATION
    value: Optional[float] = None  # Deal value in USD
    probability: int = 50  # 0-100%
    expected_close_date: Optional[datetime] = None
    
    # IGV Fields
    expansion_type: Optional[ExpansionType] = None
    sector: Optional[Sector] = None
    format: Optional[Format] = None
    target_city: Optional[str] = None
    
    # Ownership
    owner_id: Optional[str] = None
    owner_email: Optional[str] = None
    
    # Next Steps
    next_step: Optional[str] = None
    next_action_date: Optional[datetime] = None
    
    # Status
    is_closed: bool = False
    is_won: bool = False
    lost_reason: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None


# ==========================================
# CONTACT MODEL
# ==========================================

class Contact(BaseModel):
    """Business Contact"""
    
    email: EmailStr
    name: str
    phone: Optional[str] = None
    position: Optional[str] = None
    company_id: Optional[str] = None
    
    # Social
    linkedin: Optional[str] = None
    twitter: Optional[str] = None
    
    # Preferences
    language: str = "fr"
    timezone: Optional[str] = None
    
    # Relations
    lead_ids: List[str] = []
    opportunity_ids: List[str] = []
    
    # Tags & Notes
    tags: List[str] = []
    notes: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_contacted_at: Optional[datetime] = None


# ==========================================
# COMPANY MODEL
# ==========================================

class Company(BaseModel):
    """Company/Organization"""
    
    name: str
    domain: Optional[str] = None
    industry: Optional[Sector] = None
    size: Optional[str] = None  # "1-10", "11-50", "51-200", "201-500", "500+"
    
    # Address
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    
    # Social
    website: Optional[str] = None
    linkedin: Optional[str] = None
    
    # Relations
    contact_ids: List[str] = []
    opportunity_ids: List[str] = []
    
    # Notes
    notes: Optional[str] = None
    tags: List[str] = []
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ==========================================
# TASK MODEL
# ==========================================

class Task(BaseModel):
    """Task/Todo"""
    
    title: str
    description: Optional[str] = None
    
    # Assignment
    assigned_to_id: Optional[str] = None
    assigned_to_email: Optional[str] = None
    created_by_id: Optional[str] = None
    created_by_email: Optional[str] = None
    
    # Relations
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    
    # Status
    is_completed: bool = False
    priority: Priority = Priority.B
    
    # Timing
    due_date: Optional[datetime] = None
    reminder_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ==========================================
# ACTIVITY MODEL
# ==========================================

class Activity(BaseModel):
    """Activity Log Entry"""
    
    type: ActivityType
    subject: str
    description: Optional[str] = None
    
    # Relations
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    task_id: Optional[str] = None
    
    # User
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = {}
    
    # Timestamp
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ==========================================
# VISITOR TRACKING (GDPR-Compliant)
# ==========================================

class Visitor(BaseModel):
    """Anonymous visitor tracking (GDPR-compliant)"""
    
    # Anonymous ID (hashed IP + user agent)
    visitor_id: str
    ip_hash: str  # Hashed IP for privacy
    
    # Session
    session_id: str
    sessions_count: int = 1
    
    # Consent
    consent_analytics: bool = False
    consent_marketing: bool = False
    
    # Attribution
    first_source: Optional[str] = None
    first_utm_source: Optional[str] = None
    first_utm_medium: Optional[str] = None
    first_utm_campaign: Optional[str] = None
    first_referrer: Optional[str] = None
    first_landing_page: Optional[str] = None
    
    last_source: Optional[str] = None
    last_utm_source: Optional[str] = None
    last_utm_medium: Optional[str] = None
    last_utm_campaign: Optional[str] = None
    last_referrer: Optional[str] = None
    last_page: Optional[str] = None
    
    # Pages
    pages_viewed: List[str] = []
    page_count: int = 0
    
    # Device
    device_type: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    language: Optional[str] = None
    
    # Conversion
    converted_to_lead_id: Optional[str] = None
    converted_at: Optional[datetime] = None
    
    # Timestamps
    first_seen_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)


# ==========================================
# NEWSLETTER SUBSCRIBER (GDPR-Compliant)
# ==========================================

class NewsletterSubscriber(BaseModel):
    """Newsletter subscriber with explicit consent"""
    
    email: EmailStr
    
    # Consent (REQUIRED)
    consent_marketing: bool = True
    consent_date: datetime = Field(default_factory=datetime.utcnow)
    consent_ip: Optional[str] = None
    
    # Preferences
    language: str = "fr"
    tags: List[str] = []
    
    # Status
    is_active: bool = True
    is_verified: bool = False
    unsubscribed_at: Optional[datetime] = None
    unsubscribe_reason: Optional[str] = None
    
    # Attribution
    source: Optional[str] = None
    utm_source: Optional[str] = None
    utm_campaign: Optional[str] = None
    
    # Relations
    lead_id: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ==========================================
# USER MODEL (CRM Users)
# ==========================================

class CRMUser(BaseModel):
    """CRM System User (unlimited)"""
    
    email: EmailStr
    name: str
    role: UserRole = UserRole.VIEWER
    
    # Password (hashed)
    password_hash: str
    
    # Status
    is_active: bool = True
    is_verified: bool = True
    
    # Preferences
    language: str = "fr"
    timezone: Optional[str] = None
    
    # Security
    last_login_at: Optional[datetime] = None
    last_login_ip: Optional[str] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[str] = None


# ==========================================
# AUDIT LOG
# ==========================================

class AuditLog(BaseModel):
    """Complete audit trail"""
    
    # User
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    
    # Action
    action: str  # "create", "update", "delete", "login", "export"
    entity_type: str  # "lead", "contact", "opportunity", "user", etc.
    entity_id: Optional[str] = None
    
    # Changes
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    changes: Optional[Dict[str, Any]] = None
    
    # Context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    # Timestamp
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ==========================================
# PENDING ANALYSIS (Quota Queue)
# ==========================================

class PendingAnalysis(BaseModel):
    """Queued analysis requests when quota exceeded"""
    
    lead_id: str
    email: EmailStr
    brand_name: str
    sector: Optional[str] = None
    language: str = "fr"
    
    # Status
    status: str = "pending"  # pending, processing, completed, failed
    attempts: int = 0
    last_attempt_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    # Result
    analysis_result: Optional[Dict[str, Any]] = None
    processed_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ==========================================
# SETTINGS
# ==========================================

class CRMSettings(BaseModel):
    """Global CRM settings"""
    
    # Pipeline
    pipeline_stages: List[Dict[str, str]] = [
        {"key": "analysis_requested", "label_fr": "Analyse demandée", "label_en": "Analysis requested", "label_he": "ניתוח התבקש"},
        {"key": "analysis_sent", "label_fr": "Analyse envoyée", "label_en": "Analysis sent", "label_he": "ניתוח נשלח"},
        {"key": "call_scheduled", "label_fr": "Appel planifié", "label_en": "Call scheduled", "label_he": "שיחה מתוזמנת"},
        {"key": "qualification", "label_fr": "Qualification", "label_en": "Qualification", "label_he": "הסמכה"},
        {"key": "proposal_sent", "label_fr": "Proposition envoyée", "label_en": "Proposal sent", "label_he": "הצעה נשלחה"},
        {"key": "negotiation", "label_fr": "Négociation", "label_en": "Negotiation", "label_he": "משא ומתן"},
        {"key": "won", "label_fr": "Signé / Lancement", "label_en": "Signed / Launch", "label_he": "חתום / השקה"},
        {"key": "lost", "label_fr": "Perdu / Sans suite", "label_en": "Lost / No follow-up", "label_he": "אבד / ללא מעקב"}
    ]
    
    # Tags
    available_tags: List[str] = ["hot", "cold", "follow-up", "qualified", "unqualified"]
    
    # Email templates
    email_templates: Dict[str, Dict[str, str]] = {}
    
    # Features
    features: Dict[str, bool] = {
        "monetico_enabled": False,
        "gemini_queue_enabled": True
    }
    
    # Updated
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by_email: Optional[str] = None
