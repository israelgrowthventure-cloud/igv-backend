"""
Quality Routes - CRM IGV
Détection de doublons, fusion, qualité des données
Point 2 de la mission
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from typing import Dict, List, Optional
from datetime import datetime, timezone
from bson import ObjectId
import logging
import re
from difflib import SequenceMatcher

from auth_middleware import get_current_user, require_admin, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crm/quality", tags=["quality"])


# ==========================================
# DUPLICATE DETECTION
# ==========================================

def normalize_string(s: str) -> str:
    """Normalize string for comparison"""
    if not s:
        return ""
    # Remove accents, lowercase, strip whitespace
    s = s.lower().strip()
    # Remove common suffixes
    s = re.sub(r'\s+(ltd|inc|corp|sarl|sas|sa|llc|gmbh)\.?$', '', s, flags=re.IGNORECASE)
    # Remove punctuation
    s = re.sub(r'[^\w\s]', '', s)
    # Normalize whitespace
    s = re.sub(r'\s+', ' ', s)
    return s


def similarity_score(s1: str, s2: str) -> float:
    """Calculate similarity between two strings (0-1)"""
    if not s1 or not s2:
        return 0.0
    n1 = normalize_string(s1)
    n2 = normalize_string(s2)
    if n1 == n2:
        return 1.0
    return SequenceMatcher(None, n1, n2).ratio()


def normalize_phone(phone: str) -> str:
    """Normalize phone number for comparison"""
    if not phone:
        return ""
    # Remove all non-digits
    return re.sub(r'\D', '', phone)


def normalize_email(email: str) -> str:
    """Normalize email for comparison"""
    if not email:
        return ""
    return email.lower().strip()


def extract_domain(email: str) -> str:
    """Extract domain from email"""
    if not email or '@' not in email:
        return ""
    return email.split('@')[1].lower()


@router.get("/duplicates/leads")
async def detect_lead_duplicates(
    threshold: float = Query(0.8, ge=0.5, le=1.0, description="Similarity threshold"),
    limit: int = Query(100, le=500),
    user: Dict = Depends(require_admin)
):
    """
    Detect potential duplicate leads
    Uses email, phone, and name similarity
    Admin only
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        leads = await db.leads.find({}).to_list(length=limit * 2)
        
        duplicates = []
        seen_pairs = set()
        
        for i, lead1 in enumerate(leads):
            for lead2 in leads[i+1:]:
                lead1_id = str(lead1.get('_id', lead1.get('lead_id')))
                lead2_id = str(lead2.get('_id', lead2.get('lead_id')))
                
                pair_key = tuple(sorted([lead1_id, lead2_id]))
                if pair_key in seen_pairs:
                    continue
                
                # Check exact email match
                email1 = normalize_email(lead1.get('email', ''))
                email2 = normalize_email(lead2.get('email', ''))
                email_match = email1 and email2 and email1 == email2
                
                # Check phone match
                phone1 = normalize_phone(lead1.get('phone', ''))
                phone2 = normalize_phone(lead2.get('phone', ''))
                phone_match = phone1 and phone2 and phone1 == phone2
                
                # Check name similarity
                name1 = lead1.get('name', '') or lead1.get('brand_name', '')
                name2 = lead2.get('name', '') or lead2.get('brand_name', '')
                name_similarity = similarity_score(name1, name2)
                
                # Determine if duplicate
                is_duplicate = False
                confidence = 0.0
                reasons = []
                
                if email_match:
                    is_duplicate = True
                    confidence = max(confidence, 0.95)
                    reasons.append("email_exact")
                
                if phone_match:
                    is_duplicate = True
                    confidence = max(confidence, 0.90)
                    reasons.append("phone_exact")
                
                if name_similarity >= threshold:
                    is_duplicate = True
                    confidence = max(confidence, name_similarity)
                    reasons.append(f"name_similar_{int(name_similarity*100)}%")
                
                if is_duplicate and confidence >= threshold:
                    seen_pairs.add(pair_key)
                    duplicates.append({
                        "lead1": {
                            "id": lead1_id,
                            "name": lead1.get('name', '') or lead1.get('brand_name', ''),
                            "email": lead1.get('email', ''),
                            "phone": lead1.get('phone', ''),
                            "created_at": str(lead1.get('created_at', ''))
                        },
                        "lead2": {
                            "id": lead2_id,
                            "name": lead2.get('name', '') or lead2.get('brand_name', ''),
                            "email": lead2.get('email', ''),
                            "phone": lead2.get('phone', ''),
                            "created_at": str(lead2.get('created_at', ''))
                        },
                        "confidence": round(confidence, 2),
                        "reasons": reasons
                    })
        
        # Sort by confidence
        duplicates.sort(key=lambda x: x['confidence'], reverse=True)
        
        return {
            "duplicates": duplicates[:limit],
            "total": len(duplicates),
            "threshold": threshold
        }
        
    except Exception as e:
        logger.error(f"Error detecting lead duplicates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/duplicates/contacts")
async def detect_contact_duplicates(
    threshold: float = Query(0.8, ge=0.5, le=1.0),
    limit: int = Query(100, le=500),
    user: Dict = Depends(require_admin)
):
    """Detect potential duplicate contacts"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        contacts = await db.contacts.find({}).to_list(length=limit * 2)
        
        duplicates = []
        seen_pairs = set()
        
        for i, c1 in enumerate(contacts):
            for c2 in contacts[i+1:]:
                c1_id = str(c1.get('_id', c1.get('contact_id')))
                c2_id = str(c2.get('_id', c2.get('contact_id')))
                
                pair_key = tuple(sorted([c1_id, c2_id]))
                if pair_key in seen_pairs:
                    continue
                
                email1 = normalize_email(c1.get('email', ''))
                email2 = normalize_email(c2.get('email', ''))
                email_match = email1 and email2 and email1 == email2
                
                phone1 = normalize_phone(c1.get('phone', ''))
                phone2 = normalize_phone(c2.get('phone', ''))
                phone_match = phone1 and phone2 and phone1 == phone2
                
                name_similarity = similarity_score(c1.get('name', ''), c2.get('name', ''))
                
                is_duplicate = False
                confidence = 0.0
                reasons = []
                
                if email_match:
                    is_duplicate = True
                    confidence = max(confidence, 0.95)
                    reasons.append("email_exact")
                
                if phone_match:
                    is_duplicate = True
                    confidence = max(confidence, 0.90)
                    reasons.append("phone_exact")
                
                if name_similarity >= threshold:
                    is_duplicate = True
                    confidence = max(confidence, name_similarity)
                    reasons.append(f"name_similar_{int(name_similarity*100)}%")
                
                if is_duplicate and confidence >= threshold:
                    seen_pairs.add(pair_key)
                    duplicates.append({
                        "contact1": {
                            "id": c1_id,
                            "name": c1.get('name', ''),
                            "email": c1.get('email', ''),
                            "phone": c1.get('phone', '')
                        },
                        "contact2": {
                            "id": c2_id,
                            "name": c2.get('name', ''),
                            "email": c2.get('email', ''),
                            "phone": c2.get('phone', '')
                        },
                        "confidence": round(confidence, 2),
                        "reasons": reasons
                    })
        
        duplicates.sort(key=lambda x: x['confidence'], reverse=True)
        
        return {
            "duplicates": duplicates[:limit],
            "total": len(duplicates)
        }
        
    except Exception as e:
        logger.error(f"Error detecting contact duplicates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/merge/leads")
async def merge_leads(
    keep_id: str = Body(..., description="ID of lead to keep"),
    merge_id: str = Body(..., description="ID of lead to merge into keep_id"),
    user: Dict = Depends(require_admin)
):
    """
    Merge two leads - keeps one, archives the other
    Merges notes, activities, and fills empty fields
    Admin only
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # Get both leads
        try:
            keep_lead = await db.leads.find_one({"_id": ObjectId(keep_id)})
        except:
            keep_lead = await db.leads.find_one({"lead_id": int(keep_id)})
        
        try:
            merge_lead = await db.leads.find_one({"_id": ObjectId(merge_id)})
        except:
            merge_lead = await db.leads.find_one({"lead_id": int(merge_id)})
        
        if not keep_lead:
            raise HTTPException(status_code=404, detail="Lead to keep not found")
        if not merge_lead:
            raise HTTPException(status_code=404, detail="Lead to merge not found")
        
        # Merge data - fill empty fields in keep_lead with merge_lead values
        fields_to_merge = ['phone', 'name', 'sector', 'budget_estimated', 'target_city', 
                          'timeline', 'expansion_type', 'format', 'focus_notes']
        
        update_data = {}
        for field in fields_to_merge:
            if not keep_lead.get(field) and merge_lead.get(field):
                update_data[field] = merge_lead[field]
        
        # Merge notes
        keep_notes = keep_lead.get('notes', []) or []
        merge_notes = merge_lead.get('notes', []) or []
        if merge_notes:
            merged_notes = keep_notes + [
                {**note, "merged_from": merge_id} for note in merge_notes
            ]
            update_data['notes'] = merged_notes
        
        # Merge tags
        keep_tags = set(keep_lead.get('tags', []) or [])
        merge_tags = set(merge_lead.get('tags', []) or [])
        if merge_tags:
            update_data['tags'] = list(keep_tags | merge_tags)
        
        # Update kept lead
        update_data['updated_at'] = datetime.now(timezone.utc)
        update_data['merged_ids'] = (keep_lead.get('merged_ids', []) or []) + [merge_id]
        
        await db.leads.update_one(
            {"_id": keep_lead["_id"]},
            {"$set": update_data}
        )
        
        # Archive merged lead (soft delete)
        await db.leads.update_one(
            {"_id": merge_lead["_id"]},
            {"$set": {
                "status": "merged",
                "merged_into": keep_id,
                "merged_at": datetime.now(timezone.utc),
                "merged_by": user.get('email')
            }}
        )
        
        # Log audit
        await db.audit_logs.insert_one({
            "action": "merge_leads",
            "entity_type": "lead",
            "entity_id": keep_id,
            "merged_id": merge_id,
            "user_email": user.get('email'),
            "timestamp": datetime.now(timezone.utc),
            "details": f"Merged lead {merge_id} into {keep_id}"
        })
        
        return {
            "success": True,
            "kept_id": keep_id,
            "merged_id": merge_id,
            "fields_updated": list(update_data.keys())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error merging leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/merge/contacts")
async def merge_contacts(
    keep_id: str = Body(...),
    merge_id: str = Body(...),
    user: Dict = Depends(require_admin)
):
    """Merge two contacts"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        try:
            keep_contact = await db.contacts.find_one({"_id": ObjectId(keep_id)})
        except:
            keep_contact = await db.contacts.find_one({"contact_id": int(keep_id)})
        
        try:
            merge_contact = await db.contacts.find_one({"_id": ObjectId(merge_id)})
        except:
            merge_contact = await db.contacts.find_one({"contact_id": int(merge_id)})
        
        if not keep_contact:
            raise HTTPException(status_code=404, detail="Contact to keep not found")
        if not merge_contact:
            raise HTTPException(status_code=404, detail="Contact to merge not found")
        
        # Merge data
        fields_to_merge = ['phone', 'position', 'company', 'address', 'city', 'country']
        update_data = {}
        
        for field in fields_to_merge:
            if not keep_contact.get(field) and merge_contact.get(field):
                update_data[field] = merge_contact[field]
        
        # Merge notes
        keep_notes = keep_contact.get('notes', []) or []
        merge_notes = merge_contact.get('notes', []) or []
        if merge_notes:
            update_data['notes'] = keep_notes + merge_notes
        
        update_data['updated_at'] = datetime.now(timezone.utc)
        update_data['merged_ids'] = (keep_contact.get('merged_ids', []) or []) + [merge_id]
        
        await db.contacts.update_one(
            {"_id": keep_contact["_id"]},
            {"$set": update_data}
        )
        
        # Update opportunities to point to kept contact
        await db.opportunities.update_many(
            {"contact_id": merge_id},
            {"$set": {"contact_id": keep_id}}
        )
        
        # Archive merged contact
        await db.contacts.update_one(
            {"_id": merge_contact["_id"]},
            {"$set": {
                "status": "merged",
                "merged_into": keep_id,
                "merged_at": datetime.now(timezone.utc)
            }}
        )
        
        # Audit log
        await db.audit_logs.insert_one({
            "action": "merge_contacts",
            "entity_type": "contact",
            "entity_id": keep_id,
            "merged_id": merge_id,
            "user_email": user.get('email'),
            "timestamp": datetime.now(timezone.utc)
        })
        
        return {
            "success": True,
            "kept_id": keep_id,
            "merged_id": merge_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error merging contacts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_quality_stats(user: Dict = Depends(require_admin)):
    """Get data quality statistics"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # Lead stats
        total_leads = await db.leads.count_documents({})
        leads_no_email = await db.leads.count_documents({"$or": [{"email": None}, {"email": ""}]})
        leads_no_phone = await db.leads.count_documents({"$or": [{"phone": None}, {"phone": ""}]})
        leads_no_name = await db.leads.count_documents({
            "$and": [
                {"$or": [{"name": None}, {"name": ""}]},
                {"$or": [{"brand_name": None}, {"brand_name": ""}]}
            ]
        })
        
        # Contact stats
        total_contacts = await db.contacts.count_documents({})
        contacts_no_email = await db.contacts.count_documents({"$or": [{"email": None}, {"email": ""}]})
        contacts_no_phone = await db.contacts.count_documents({"$or": [{"phone": None}, {"phone": ""}]})
        
        # Calculate completeness scores
        lead_completeness = 0
        if total_leads > 0:
            complete_leads = total_leads - max(leads_no_email, leads_no_phone, leads_no_name)
            lead_completeness = round((complete_leads / total_leads) * 100, 1)
        
        contact_completeness = 0
        if total_contacts > 0:
            complete_contacts = total_contacts - max(contacts_no_email, contacts_no_phone)
            contact_completeness = round((complete_contacts / total_contacts) * 100, 1)
        
        return {
            "leads": {
                "total": total_leads,
                "missing_email": leads_no_email,
                "missing_phone": leads_no_phone,
                "missing_name": leads_no_name,
                "completeness_score": lead_completeness
            },
            "contacts": {
                "total": total_contacts,
                "missing_email": contacts_no_email,
                "missing_phone": contacts_no_phone,
                "completeness_score": contact_completeness
            },
            "overall_score": round((lead_completeness + contact_completeness) / 2, 1)
        }
        
    except Exception as e:
        logger.error(f"Error getting quality stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
