"""
Advanced Email & Export Routes - CRM IGV
Points 9, 11 de la mission:
- Emails avancés (pièces jointes + tracking)
- Exports globaux CSV
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body, UploadFile, File
from fastapi.responses import StreamingResponse
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import logging
import csv
import io
import uuid
import base64

from auth_middleware import get_current_user, require_admin, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crm", tags=["emails-exports"])


# ==========================================
# POINT 9: EMAILS AVANCÉS
# ==========================================

@router.post("/emails/send")
async def send_email_advanced(
    email_data: Dict = Body(...),
    user: Dict = Depends(get_current_user)
):
    """
    Send email with advanced features:
    - Attachments (base64)
    - Tracking pixel
    - Open/click tracking
    
    email_data: {
        "to": "recipient@example.com",
        "subject": "Subject",
        "body": "HTML body",
        "lead_id": "optional",
        "contact_id": "optional",
        "attachments": [{"name": "file.pdf", "content": "base64...", "mime_type": "application/pdf"}],
        "track_opens": true,
        "track_clicks": true
    }
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        to_email = email_data.get("to")
        subject = email_data.get("subject", "")
        body = email_data.get("body", "")
        attachments = email_data.get("attachments", [])
        track_opens = email_data.get("track_opens", True)
        track_clicks = email_data.get("track_clicks", True)
        
        if not to_email:
            raise HTTPException(status_code=400, detail="Recipient email required")
        
        # Generate tracking ID
        tracking_id = str(uuid.uuid4())
        
        # Insert tracking pixel if enabled
        if track_opens:
            tracking_pixel = f'<img src="https://igv-cms-backend.onrender.com/api/crm/emails/track/{tracking_id}/open" width="1" height="1" style="display:none" />'
            body = body + tracking_pixel
        
        # Replace links with tracked versions if enabled
        if track_clicks:
            # Simple link tracking - in production use proper HTML parsing
            import re
            def replace_link(match):
                original_url = match.group(1)
                tracked_url = f"https://igv-cms-backend.onrender.com/api/crm/emails/track/{tracking_id}/click?url={original_url}"
                return f'href="{tracked_url}"'
            body = re.sub(r'href="([^"]+)"', replace_link, body)
        
        # Store email record
        email_record = {
            "tracking_id": tracking_id,
            "to": to_email,
            "from": user.get("email"),
            "subject": subject,
            "body": body,
            "lead_id": email_data.get("lead_id"),
            "contact_id": email_data.get("contact_id"),
            "opportunity_id": email_data.get("opportunity_id"),
            "attachments": [{"name": a.get("name"), "size": len(a.get("content", ""))} for a in attachments],
            "track_opens": track_opens,
            "track_clicks": track_clicks,
            "status": "sent",
            "sent_at": datetime.now(timezone.utc),
            "sent_by": user.get("email"),
            "opens": [],
            "clicks": [],
            "created_at": datetime.now(timezone.utc)
        }
        
        result = await db.emails.insert_one(email_record)
        email_record['_id'] = str(result.inserted_id)
        
        # In production, actually send the email via SMTP/SendGrid/etc
        # For now, we just store it
        
        # Log activity
        if email_data.get("lead_id"):
            await db.activities.insert_one({
                "type": "email_sent",
                "lead_id": email_data.get("lead_id"),
                "email_id": str(result.inserted_id),
                "description": f"Email envoyé: {subject}",
                "created_by": user.get("email"),
                "created_at": datetime.now(timezone.utc)
            })
        
        return {
            "success": True,
            "email_id": str(result.inserted_id),
            "tracking_id": tracking_id,
            "status": "sent"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/emails/track/{tracking_id}/open")
async def track_email_open(tracking_id: str):
    """
    Track email open via pixel
    Returns 1x1 transparent GIF
    """
    db = get_db()
    if db is None:
        # Return pixel anyway
        pass
    else:
        try:
            await db.emails.update_one(
                {"tracking_id": tracking_id},
                {
                    "$push": {
                        "opens": {
                            "timestamp": datetime.now(timezone.utc),
                            "ip": "unknown"  # Would get from request in production
                        }
                    },
                    "$set": {"first_opened_at": datetime.now(timezone.utc)},
                    "$inc": {"open_count": 1}
                }
            )
        except Exception as e:
            logger.error(f"Error tracking open: {e}")
    
    # Return 1x1 transparent GIF
    gif = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
    return StreamingResponse(io.BytesIO(gif), media_type="image/gif")


@router.get("/emails/track/{tracking_id}/click")
async def track_email_click(
    tracking_id: str,
    url: str = Query(...)
):
    """
    Track email link click and redirect
    """
    db = get_db()
    if db is not None:
        try:
            await db.emails.update_one(
                {"tracking_id": tracking_id},
                {
                    "$push": {
                        "clicks": {
                            "url": url,
                            "timestamp": datetime.now(timezone.utc)
                        }
                    },
                    "$inc": {"click_count": 1}
                }
            )
        except Exception as e:
            logger.error(f"Error tracking click: {e}")
    
    # Redirect to original URL
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=url)


@router.get("/emails/{email_id}/stats")
async def get_email_stats(
    email_id: str,
    user: Dict = Depends(get_current_user)
):
    """Get tracking stats for an email"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        email = await db.emails.find_one({"_id": ObjectId(email_id)})
        if not email:
            email = await db.emails.find_one({"tracking_id": email_id})
        
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
        
        return {
            "email_id": str(email["_id"]),
            "tracking_id": email.get("tracking_id"),
            "to": email.get("to"),
            "subject": email.get("subject"),
            "sent_at": str(email.get("sent_at")),
            "open_count": email.get("open_count", len(email.get("opens", []))),
            "click_count": email.get("click_count", len(email.get("clicks", []))),
            "first_opened_at": str(email.get("first_opened_at")) if email.get("first_opened_at") else None,
            "opens": email.get("opens", []),
            "clicks": email.get("clicks", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting email stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/emails/drafts")
async def list_email_drafts(
    limit: int = Query(50, le=200),
    user: Dict = Depends(get_current_user)
):
    """List email drafts for current user"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        query = {
            "status": "draft",
            "created_by": user.get("email")
        }
        
        drafts = await db.emails.find(query).sort("updated_at", -1).to_list(length=limit)
        
        for draft in drafts:
            draft['_id'] = str(draft['_id'])
        
        return {"drafts": drafts, "total": len(drafts)}
        
    except Exception as e:
        logger.error(f"Error listing drafts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/emails/drafts")
async def save_email_draft(
    draft_data: Dict = Body(...),
    user: Dict = Depends(get_current_user)
):
    """Save email as draft"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        draft = {
            "to": draft_data.get("to", ""),
            "subject": draft_data.get("subject", ""),
            "body": draft_data.get("body", ""),
            "lead_id": draft_data.get("lead_id"),
            "contact_id": draft_data.get("contact_id"),
            "status": "draft",
            "created_by": user.get("email"),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        result = await db.emails.insert_one(draft)
        draft['_id'] = str(result.inserted_id)
        
        return {"success": True, "draft": draft}
        
    except Exception as e:
        logger.error(f"Error saving draft: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/emails/drafts/{draft_id}")
async def update_email_draft(
    draft_id: str,
    draft_data: Dict = Body(...),
    user: Dict = Depends(get_current_user)
):
    """Update email draft"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        update = {
            "to": draft_data.get("to"),
            "subject": draft_data.get("subject"),
            "body": draft_data.get("body"),
            "updated_at": datetime.now(timezone.utc)
        }
        update = {k: v for k, v in update.items() if v is not None}
        
        result = await db.emails.update_one(
            {"_id": ObjectId(draft_id), "status": "draft", "created_by": user.get("email")},
            {"$set": update}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Draft not found")
        
        return {"success": True, "updated": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating draft: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/emails/drafts/{draft_id}")
async def delete_email_draft(
    draft_id: str,
    user: Dict = Depends(get_current_user)
):
    """Delete email draft"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        result = await db.emails.delete_one({
            "_id": ObjectId(draft_id),
            "status": "draft",
            "created_by": user.get("email")
        })
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Draft not found")
        
        return {"success": True, "deleted": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting draft: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# POINT 11: EXPORTS GLOBAUX CSV
# ==========================================

@router.get("/export/leads")
async def export_leads_csv(
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user: Dict = Depends(get_current_user)
):
    """Export leads to CSV"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        query = {}
        
        if status:
            query["status"] = status
        
        if date_from:
            query["created_at"] = {"$gte": datetime.fromisoformat(date_from.replace("Z", "+00:00"))}
        if date_to:
            if "created_at" in query:
                query["created_at"]["$lte"] = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
            else:
                query["created_at"] = {"$lte": datetime.fromisoformat(date_to.replace("Z", "+00:00"))}
        
        # RBAC
        if user.get("role") == "commercial":
            query["owner_email"] = user.get("email")
        
        leads = await db.leads.find(query).to_list(length=10000)
        
        # Build CSV
        output = io.StringIO()
        fieldnames = [
            'id', 'name', 'email', 'phone', 'brand_name', 'sector', 
            'status', 'stage', 'priority', 'source', 'owner_email',
            'target_city', 'budget_estimated', 'created_at', 'updated_at'
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for lead in leads:
            row = {
                'id': str(lead.get('_id', lead.get('lead_id'))),
                'name': lead.get('name', ''),
                'email': lead.get('email', ''),
                'phone': lead.get('phone', ''),
                'brand_name': lead.get('brand_name', ''),
                'sector': lead.get('sector', ''),
                'status': lead.get('status', ''),
                'stage': lead.get('stage', ''),
                'priority': lead.get('priority', ''),
                'source': lead.get('source', ''),
                'owner_email': lead.get('owner_email', ''),
                'target_city': lead.get('target_city', ''),
                'budget_estimated': lead.get('budget_estimated', ''),
                'created_at': str(lead.get('created_at', '')),
                'updated_at': str(lead.get('updated_at', ''))
            }
            writer.writerow(row)
        
        output.seek(0)
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=leads_export_{datetime.now().strftime('%Y%m%d')}.csv"}
        )
        
    except Exception as e:
        logger.error(f"Error exporting leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/contacts")
async def export_contacts_csv(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user: Dict = Depends(get_current_user)
):
    """Export contacts to CSV"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        query = {}
        
        if date_from:
            query["created_at"] = {"$gte": datetime.fromisoformat(date_from.replace("Z", "+00:00"))}
        
        contacts = await db.contacts.find(query).to_list(length=10000)
        
        output = io.StringIO()
        fieldnames = [
            'id', 'name', 'email', 'phone', 'position', 'company',
            'language', 'source', 'created_at'
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for contact in contacts:
            row = {
                'id': str(contact.get('_id', contact.get('contact_id'))),
                'name': contact.get('name', ''),
                'email': contact.get('email', ''),
                'phone': contact.get('phone', ''),
                'position': contact.get('position', ''),
                'company': contact.get('company', ''),
                'language': contact.get('language', ''),
                'source': contact.get('source', ''),
                'created_at': str(contact.get('created_at', ''))
            }
            writer.writerow(row)
        
        output.seek(0)
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=contacts_export_{datetime.now().strftime('%Y%m%d')}.csv"}
        )
        
    except Exception as e:
        logger.error(f"Error exporting contacts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/companies")
async def export_companies_csv(
    industry: Optional[str] = Query(None),
    user: Dict = Depends(get_current_user)
):
    """Export companies to CSV"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        query = {}
        if industry:
            query["industry"] = industry
        
        companies = await db.companies.find(query).to_list(length=10000)
        
        output = io.StringIO()
        fieldnames = [
            'id', 'name', 'domain', 'industry', 'size', 'phone', 'email',
            'website', 'address', 'city', 'country', 'created_at'
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for company in companies:
            row = {
                'id': str(company.get('_id')),
                'name': company.get('name', ''),
                'domain': company.get('domain', ''),
                'industry': company.get('industry', ''),
                'size': company.get('size', ''),
                'phone': company.get('phone', ''),
                'email': company.get('email', ''),
                'website': company.get('website', ''),
                'address': company.get('address', ''),
                'city': company.get('city', ''),
                'country': company.get('country', ''),
                'created_at': str(company.get('created_at', ''))
            }
            writer.writerow(row)
        
        output.seek(0)
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=companies_export_{datetime.now().strftime('%Y%m%d')}.csv"}
        )
        
    except Exception as e:
        logger.error(f"Error exporting companies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/opportunities")
async def export_opportunities_csv(
    stage: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    user: Dict = Depends(get_current_user)
):
    """Export opportunities to CSV"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        query = {}
        if stage:
            query["stage"] = stage
        if date_from:
            query["created_at"] = {"$gte": datetime.fromisoformat(date_from.replace("Z", "+00:00"))}
        
        opps = await db.opportunities.find(query).to_list(length=10000)
        
        output = io.StringIO()
        fieldnames = [
            'id', 'name', 'contact_id', 'value', 'stage', 'probability',
            'expected_close_date', 'created_at', 'closed_at'
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for opp in opps:
            row = {
                'id': str(opp.get('_id', opp.get('opportunity_id'))),
                'name': opp.get('name', ''),
                'contact_id': str(opp.get('contact_id', '')),
                'value': opp.get('value', 0),
                'stage': opp.get('stage', ''),
                'probability': opp.get('probability', 0),
                'expected_close_date': str(opp.get('expected_close_date', '')),
                'created_at': str(opp.get('created_at', '')),
                'closed_at': str(opp.get('closed_at', '')) if opp.get('closed_at') else ''
            }
            writer.writerow(row)
        
        output.seek(0)
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=opportunities_export_{datetime.now().strftime('%Y%m%d')}.csv"}
        )
        
    except Exception as e:
        logger.error(f"Error exporting opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/activities")
async def export_activities_csv(
    type: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user: Dict = Depends(get_current_user)
):
    """Export activities to CSV"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        query = {}
        if type:
            query["type"] = type
        if date_from:
            query["created_at"] = {"$gte": datetime.fromisoformat(date_from.replace("Z", "+00:00"))}
        
        activities = await db.activities.find(query).sort("created_at", -1).to_list(length=10000)
        
        output = io.StringIO()
        fieldnames = [
            'id', 'type', 'description', 'lead_id', 'contact_id', 
            'opportunity_id', 'created_by', 'created_at'
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for activity in activities:
            row = {
                'id': str(activity.get('_id')),
                'type': activity.get('type', ''),
                'description': activity.get('description', ''),
                'lead_id': str(activity.get('lead_id', '')),
                'contact_id': str(activity.get('contact_id', '')),
                'opportunity_id': str(activity.get('opportunity_id', '')),
                'created_by': activity.get('created_by', ''),
                'created_at': str(activity.get('created_at', ''))
            }
            writer.writerow(row)
        
        output.seek(0)
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=activities_export_{datetime.now().strftime('%Y%m%d')}.csv"}
        )
        
    except Exception as e:
        logger.error(f"Error exporting activities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/all")
async def export_all_data(user: Dict = Depends(require_admin)):
    """
    Export all CRM data as a ZIP archive containing multiple CSVs
    Admin only - for backup purposes
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        import zipfile
        
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Export each collection
            collections = ['leads', 'contacts', 'companies', 'opportunities', 'activities', 'emails']
            
            for collection_name in collections:
                collection = db[collection_name]
                docs = await collection.find({}).to_list(length=50000)
                
                if docs:
                    output = io.StringIO()
                    # Get all unique keys
                    all_keys = set()
                    for doc in docs:
                        all_keys.update(doc.keys())
                    all_keys.discard('_id')
                    fieldnames = ['_id'] + sorted(list(all_keys))
                    
                    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
                    writer.writeheader()
                    
                    for doc in docs:
                        doc['_id'] = str(doc['_id'])
                        # Convert nested objects to strings
                        for key, value in doc.items():
                            if isinstance(value, (dict, list)):
                                doc[key] = str(value)
                            elif isinstance(value, datetime):
                                doc[key] = value.isoformat()
                        writer.writerow(doc)
                    
                    zip_file.writestr(f"{collection_name}.csv", output.getvalue())
        
        zip_buffer.seek(0)
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=crm_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"}
        )
        
    except Exception as e:
        logger.error(f"Error exporting all data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# MM-08: EMAIL TEMPLATES CRUD
# ==========================================

@router.get("/emails/templates")
async def get_email_templates(
    category: Optional[str] = None,
    user: Dict = Depends(get_current_user)
):
    """Get all email templates"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        query = {}
        if category:
            query["category"] = category
        templates = await db.email_templates.find(query).sort("created_at", -1).to_list(200)
        for t in templates:
            t["_id"] = str(t["_id"])
            t["id"] = t["_id"]
        return {"success": True, "data": templates, "total": len(templates)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/emails/templates")
async def create_email_template(
    data: Dict = Body(...),
    user: Dict = Depends(get_current_user)
):
    """Create a new email template"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        template = {
            "name": data.get("name", ""),
            "subject": data.get("subject", ""),
            "body": data.get("body", ""),
            "category": data.get("category", "general"),
            "language": data.get("language", "fr"),
            "variables": data.get("variables", []),
            "created_at": datetime.now(timezone.utc),
            "created_by": user["email"],
            "updated_at": datetime.now(timezone.utc)
        }
        result = await db.email_templates.insert_one(template)
        return {"success": True, "template_id": str(result.inserted_id), "message": "Template created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/emails/templates/{template_id}")
async def update_email_template(
    template_id: str,
    data: Dict = Body(...),
    user: Dict = Depends(get_current_user)
):
    """Update an email template"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        allowed = ["name", "subject", "body", "category", "language", "variables"]
        update_fields = {k: v for k, v in data.items() if k in allowed}
        update_fields["updated_at"] = datetime.now(timezone.utc)
        update_fields["updated_by"] = user["email"]
        result = await db.email_templates.update_one(
            {"_id": ObjectId(template_id)},
            {"$set": update_fields}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Template not found")
        return {"success": True, "message": "Template updated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/emails/templates/{template_id}")
async def delete_email_template(
    template_id: str,
    user: Dict = Depends(get_current_user)
):
    """Delete an email template"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        result = await db.email_templates.delete_one({"_id": ObjectId(template_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Template not found")
        return {"success": True, "message": "Template deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

