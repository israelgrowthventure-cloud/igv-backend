"""
Invoice Models - Complete Invoicing System
Production-ready schemas for invoices + payments
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class InvoiceStatus(str, Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    PAID = "PAID"
    PARTIAL = "PARTIAL"
    OVERDUE = "OVERDUE"
    CANCELED = "CANCELED"


class PaymentStatus(str, Enum):
    INITIATED = "INITIATED"
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    CANCELED = "CANCELED"


class InvoiceItem(BaseModel):
    """Line item in invoice"""
    description: str
    quantity: float = 1.0
    unit_price: float
    discount_percent: float = 0.0
    tax_rate: float = 18.0  # TVA Israel = 18%
    
    @property
    def subtotal(self) -> float:
        """Calculate subtotal before tax"""
        base = self.quantity * self.unit_price
        if self.discount_percent > 0:
            base = base * (1 - self.discount_percent / 100)
        return round(base, 2)
    
    @property
    def tax_amount(self) -> float:
        """Calculate tax amount"""
        return round(self.subtotal * (self.tax_rate / 100), 2)
    
    @property
    def total(self) -> float:
        """Calculate total including tax"""
        return round(self.subtotal + self.tax_amount, 2)


class Invoice(BaseModel):
    """Complete Invoice"""
    
    # Invoice Info
    invoice_number: str  # Format: INV-2025-00001
    invoice_date: datetime = Field(default_factory=datetime.utcnow)
    due_date: Optional[datetime] = None
    
    # Client Info
    client_email: EmailStr
    client_name: str
    client_company: Optional[str] = None
    client_address: Optional[str] = None
    client_city: Optional[str] = None
    client_country: Optional[str] = None
    client_tax_id: Optional[str] = None  # VAT number
    
    # Relations
    contact_id: Optional[str] = None
    lead_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    
    # Items
    items: List[InvoiceItem] = []
    
    # Amounts
    subtotal: float = 0.0
    tax_rate: float = 18.0  # Israel VAT
    tax_amount: float = 0.0
    discount_amount: float = 0.0
    total_amount: float = 0.0
    
    # Currency
    currency: str = "USD"
    
    # Status
    status: InvoiceStatus = InvoiceStatus.DRAFT
    
    # Payment
    paid_amount: float = 0.0
    payment_method: Optional[str] = None  # "credit_card", "bank_transfer", "monetico"
    payment_date: Optional[datetime] = None
    payment_id: Optional[str] = None
    
    # Files
    pdf_url: Optional[str] = None
    pdf_generated_at: Optional[datetime] = None
    
    # Notes
    notes: Optional[str] = None
    internal_notes: Optional[str] = None
    
    # Language
    language: str = "fr"
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    
    # Email tracking
    email_sent: bool = False
    email_sent_at: Optional[datetime] = None
    email_error: Optional[str] = None


class Payment(BaseModel):
    """Payment record (including Monetico)"""
    
    # Payment Info
    payment_id: str  # Internal ID
    payment_provider: str = "monetico"  # monetico, stripe, manual
    provider_transaction_id: Optional[str] = None
    
    # Amount
    amount: float
    currency: str = "USD"
    
    # Relations
    invoice_id: Optional[str] = None
    contact_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    
    # Status
    status: PaymentStatus = PaymentStatus.INITIATED
    
    # Monetico specific
    monetico_reference: Optional[str] = None
    monetico_mac: Optional[str] = None
    monetico_context: Optional[Dict[str, Any]] = None
    
    # Return URLs
    return_url: Optional[str] = None
    notify_url: Optional[str] = None
    
    # Payment details
    payment_method: Optional[str] = None  # CB, VISA, MASTERCARD
    card_last4: Optional[str] = None
    cardholder_name: Optional[str] = None
    
    # Client info
    client_email: Optional[EmailStr] = None
    client_name: Optional[str] = None
    
    # Error handling
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    # Timestamps
    initiated_at: datetime = Field(default_factory=datetime.utcnow)
    paid_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    refunded_at: Optional[datetime] = None
    
    # Metadata
    metadata: Optional[Dict[str, Any]] = None
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class EmailEvent(BaseModel):
    """Email sending event (tracking)"""
    
    email_type: str  # "invoice", "mini_analysis", "notification", "marketing"
    to_email: EmailStr
    cc: Optional[List[EmailStr]] = None
    bcc: Optional[List[EmailStr]] = None
    
    # Content
    subject: str
    template_name: Optional[str] = None
    language: str = "fr"
    
    # Attachments
    attachments: Optional[List[str]] = []  # URLs or filenames
    
    # Status
    status: Literal["sent", "failed", "pending"] = "pending"
    provider: str = "smtp"  # smtp, sendgrid, ses
    provider_message_id: Optional[str] = None
    provider_response: Optional[str] = None
    
    # Error
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    # Relations
    invoice_id: Optional[str] = None
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    
    # Retry
    retry_count: int = 0
    max_retries: int = 3
    next_retry_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
