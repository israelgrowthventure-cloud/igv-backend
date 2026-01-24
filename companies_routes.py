"""
Companies Routes - CRM IGV
Gestion des entreprises/sociétés (B2B)
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, List, Optional
from datetime import datetime, timezone
from bson import ObjectId
import logging

from auth_middleware import get_current_user, require_admin, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crm/companies", tags=["companies"])


# ==========================================
# COMPANIES CRUD
# ==========================================

@router.get("")
async def list_companies(
    search: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    skip: int = Query(0),
    user: Dict = Depends(get_current_user)
):
    """
    Liste des entreprises
    - Admin: toutes les entreprises
    - Commercial: entreprises liées à ses contacts/leads
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        query = {}
        
        # Filtres
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"domain": {"$regex": search, "$options": "i"}},
                {"industry": {"$regex": search, "$options": "i"}}
            ]
        if industry:
            query["industry"] = industry
        
        # RBAC: Commercial voit seulement ses entreprises liées
        is_admin = user.get("role") == "admin"
        if not is_admin:
            # Récupérer les company_ids des contacts/leads assignés au commercial
            user_email = user.get("email")
            
            # Contacts assignés
            contacts = await current_db.contacts.find(
                {"assigned_to": user_email},
                {"company_id": 1}
            ).to_list(1000)
            
            # Leads assignés
            leads = await current_db.leads.find(
                {"assigned_to": user_email},
                {"company_id": 1}
            ).to_list(1000)
            
            company_ids = set()
            for c in contacts:
                if c.get("company_id"):
                    company_ids.add(c["company_id"])
            for l in leads:
                if l.get("company_id"):
                    company_ids.add(l["company_id"])
            
            if company_ids:
                query["_id"] = {"$in": [ObjectId(cid) for cid in company_ids if ObjectId.is_valid(cid)]}
            else:
                return {"companies": [], "total": 0, "skip": skip, "limit": limit}
        
        total = await current_db.companies.count_documents(query)
        companies = await current_db.companies.find(query).sort("name", 1).skip(skip).limit(limit).to_list(limit)
        
        formatted = []
        for company in companies:
            # Compter contacts et leads liés
            contact_count = await current_db.contacts.count_documents({"company_id": str(company["_id"])})
            lead_count = await current_db.leads.count_documents({"company_id": str(company["_id"])})
            opp_count = await current_db.opportunities.count_documents({"company_id": str(company["_id"])})
            
            formatted.append({
                "id": str(company["_id"]),
                "company_id": str(company["_id"]),
                "name": company.get("name", ""),
                "domain": company.get("domain", ""),
                "industry": company.get("industry", ""),
                "size": company.get("size", ""),
                "country": company.get("country", ""),
                "city": company.get("city", ""),
                "address": company.get("address", ""),
                "phone": company.get("phone", ""),
                "website": company.get("website", ""),
                "description": company.get("description", ""),
                "contact_count": contact_count,
                "lead_count": lead_count,
                "opportunity_count": opp_count,
                "created_at": company.get("created_at", "").isoformat() if isinstance(company.get("created_at"), datetime) else str(company.get("created_at", "")),
                "updated_at": company.get("updated_at", "").isoformat() if isinstance(company.get("updated_at"), datetime) else str(company.get("updated_at", ""))
            })
        
        return {"companies": formatted, "total": total, "skip": skip, "limit": limit}
    
    except Exception as e:
        logger.error(f"Error listing companies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{company_id}")
async def get_company(company_id: str, user: Dict = Depends(get_current_user)):
    """Détail d'une entreprise avec contacts, leads et opportunités liés"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        company = await current_db.companies.find_one({"_id": ObjectId(company_id)})
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Contacts liés
        contacts = await current_db.contacts.find({"company_id": company_id}).to_list(100)
        formatted_contacts = []
        for c in contacts:
            formatted_contacts.append({
                "id": str(c["_id"]),
                "contact_id": str(c["_id"]),
                "name": c.get("name", ""),
                "email": c.get("email", ""),
                "phone": c.get("phone", ""),
                "position": c.get("position", "")
            })
        
        # Leads liés
        leads = await current_db.leads.find({"company_id": company_id}).to_list(100)
        formatted_leads = []
        for l in leads:
            formatted_leads.append({
                "id": str(l["_id"]),
                "lead_id": l.get("lead_id", str(l["_id"])),
                "email": l.get("email", ""),
                "brand_name": l.get("brand_name", ""),
                "status": l.get("status", ""),
                "source": l.get("source", "")
            })
        
        # Opportunités liées
        opportunities = await current_db.opportunities.find({"company_id": company_id}).to_list(100)
        formatted_opps = []
        for o in opportunities:
            formatted_opps.append({
                "id": str(o["_id"]),
                "name": o.get("name", ""),
                "value": o.get("value", 0),
                "stage": o.get("stage", ""),
                "probability": o.get("probability", 0)
            })
        
        # Notes de l'entreprise
        notes = await current_db.company_notes.find({"company_id": company_id}).sort("created_at", -1).to_list(50)
        formatted_notes = []
        for n in notes:
            formatted_notes.append({
                "id": str(n["_id"]),
                "note_text": n.get("note_text", ""),
                "created_by": n.get("created_by", ""),
                "created_at": n.get("created_at", "").isoformat() if isinstance(n.get("created_at"), datetime) else str(n.get("created_at", ""))
            })
        
        return {
            "id": str(company["_id"]),
            "company_id": str(company["_id"]),
            "name": company.get("name", ""),
            "domain": company.get("domain", ""),
            "industry": company.get("industry", ""),
            "size": company.get("size", ""),
            "country": company.get("country", ""),
            "city": company.get("city", ""),
            "address": company.get("address", ""),
            "phone": company.get("phone", ""),
            "website": company.get("website", ""),
            "description": company.get("description", ""),
            "contacts": formatted_contacts,
            "leads": formatted_leads,
            "opportunities": formatted_opps,
            "notes": formatted_notes,
            "contact_count": len(formatted_contacts),
            "lead_count": len(formatted_leads),
            "opportunity_count": len(formatted_opps),
            "created_at": company.get("created_at", "").isoformat() if isinstance(company.get("created_at"), datetime) else "",
            "updated_at": company.get("updated_at", "").isoformat() if isinstance(company.get("updated_at"), datetime) else ""
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting company {company_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_company(company_data: Dict, user: Dict = Depends(get_current_user)):
    """Créer une entreprise (Admin ou Commercial)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        name = company_data.get("name", "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Company name is required")
        
        # Vérifier doublon par nom ou domain
        domain = company_data.get("domain", "").strip().lower()
        existing = None
        if domain:
            existing = await current_db.companies.find_one({"domain": domain})
        if not existing:
            existing = await current_db.companies.find_one({"name": {"$regex": f"^{name}$", "$options": "i"}})
        
        if existing:
            raise HTTPException(status_code=409, detail="Company with this name or domain already exists")
        
        new_company = {
            "name": name,
            "domain": domain,
            "industry": company_data.get("industry", ""),
            "size": company_data.get("size", ""),
            "country": company_data.get("country", ""),
            "city": company_data.get("city", ""),
            "address": company_data.get("address", ""),
            "phone": company_data.get("phone", ""),
            "website": company_data.get("website", ""),
            "description": company_data.get("description", ""),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "created_by": user.get("email", "unknown")
        }
        
        result = await current_db.companies.insert_one(new_company)
        new_company["_id"] = result.inserted_id
        new_company["id"] = str(result.inserted_id)
        new_company["company_id"] = str(result.inserted_id)
        
        # Audit log
        await current_db.audit_logs.insert_one({
            "action": "company_created",
            "entity_type": "company",
            "entity_id": str(result.inserted_id),
            "user_email": user.get("email"),
            "details": {"name": name},
            "created_at": datetime.now(timezone.utc)
        })
        
        return {"message": "Company created", "company": new_company}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating company: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{company_id}")
async def update_company(company_id: str, company_data: Dict, user: Dict = Depends(get_current_user)):
    """Modifier une entreprise"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        company = await current_db.companies.find_one({"_id": ObjectId(company_id)})
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Champs modifiables
        update_fields = {}
        for field in ["name", "domain", "industry", "size", "country", "city", "address", "phone", "website", "description"]:
            if field in company_data:
                update_fields[field] = company_data[field]
        
        update_fields["updated_at"] = datetime.now(timezone.utc)
        
        await current_db.companies.update_one(
            {"_id": ObjectId(company_id)},
            {"$set": update_fields}
        )
        
        # Audit log
        await current_db.audit_logs.insert_one({
            "action": "company_updated",
            "entity_type": "company",
            "entity_id": company_id,
            "user_email": user.get("email"),
            "details": update_fields,
            "created_at": datetime.now(timezone.utc)
        })
        
        return {"message": "Company updated", "company_id": company_id}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating company {company_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{company_id}")
async def delete_company(company_id: str, user: Dict = Depends(require_admin)):
    """Supprimer une entreprise (Admin only)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        company = await current_db.companies.find_one({"_id": ObjectId(company_id)})
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Retirer le lien des contacts et leads
        await current_db.contacts.update_many(
            {"company_id": company_id},
            {"$unset": {"company_id": ""}}
        )
        await current_db.leads.update_many(
            {"company_id": company_id},
            {"$unset": {"company_id": ""}}
        )
        
        await current_db.companies.delete_one({"_id": ObjectId(company_id)})
        
        # Audit log
        await current_db.audit_logs.insert_one({
            "action": "company_deleted",
            "entity_type": "company",
            "entity_id": company_id,
            "user_email": user.get("email"),
            "details": {"name": company.get("name")},
            "created_at": datetime.now(timezone.utc)
        })
        
        return {"message": "Company deleted", "company_id": company_id}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting company {company_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{company_id}/notes")
async def add_company_note(company_id: str, note_data: Dict, user: Dict = Depends(get_current_user)):
    """Ajouter une note à une entreprise"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        company = await current_db.companies.find_one({"_id": ObjectId(company_id)})
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        note_text = note_data.get("note_text", "").strip()
        if not note_text:
            raise HTTPException(status_code=400, detail="Note text is required")
        
        new_note = {
            "company_id": company_id,
            "note_text": note_text,
            "created_by": user.get("email", "unknown"),
            "created_at": datetime.now(timezone.utc)
        }
        
        result = await current_db.company_notes.insert_one(new_note)
        new_note["_id"] = str(result.inserted_id)
        new_note["id"] = str(result.inserted_id)
        new_note["created_at"] = new_note["created_at"].isoformat()
        
        return {"message": "Note added", "note": new_note}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding company note: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{company_id}/notes")
async def get_company_notes(company_id: str, user: Dict = Depends(get_current_user)):
    """Récupérer les notes d'une entreprise"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        notes = await current_db.company_notes.find({"company_id": company_id}).sort("created_at", -1).to_list(100)
        
        formatted = []
        for n in notes:
            formatted.append({
                "id": str(n["_id"]),
                "note_text": n.get("note_text", ""),
                "created_by": n.get("created_by", ""),
                "created_at": n.get("created_at", "").isoformat() if isinstance(n.get("created_at"), datetime) else str(n.get("created_at", ""))
            })
        
        return {"notes": formatted, "count": len(formatted)}
    
    except Exception as e:
        logger.error(f"Error getting company notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# LINK CONTACT TO COMPANY
# ==========================================

@router.post("/{company_id}/link-contact/{contact_id}")
async def link_contact_to_company(company_id: str, contact_id: str, user: Dict = Depends(get_current_user)):
    """Lier un contact à une entreprise"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        company = await current_db.companies.find_one({"_id": ObjectId(company_id)})
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        contact = await current_db.contacts.find_one({"_id": ObjectId(contact_id)})
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        await current_db.contacts.update_one(
            {"_id": ObjectId(contact_id)},
            {"$set": {"company_id": company_id, "company_name": company.get("name", "")}}
        )
        
        return {"message": "Contact linked to company", "contact_id": contact_id, "company_id": company_id}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error linking contact to company: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{company_id}/link-lead/{lead_id}")
async def link_lead_to_company(company_id: str, lead_id: str, user: Dict = Depends(get_current_user)):
    """Lier un lead à une entreprise"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        company = await current_db.companies.find_one({"_id": ObjectId(company_id)})
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        await current_db.leads.update_one(
            {"_id": ObjectId(lead_id)},
            {"$set": {"company_id": company_id, "company_name": company.get("name", "")}}
        )
        
        return {"message": "Lead linked to company", "lead_id": lead_id, "company_id": company_id}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error linking lead to company: {e}")
        raise HTTPException(status_code=500, detail=str(e))
