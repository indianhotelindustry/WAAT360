import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.models.entities import Company, Organization, TallyCompany

router = APIRouter(prefix="/api/v1", tags=["Companies & Mapping"])


# =========================================================================
# SCHEMAS
# =========================================================================


class CompanyCreateRequest(BaseModel):
    legal_name: str
    organization_slug: Optional[str] = "default-org"
    trade_name: Optional[str] = None
    pan: Optional[str] = None
    gstin: Optional[str] = None
    currency: str = "INR"


class CompanyResponse(BaseModel):
    id: str
    organization_id: str
    legal_name: str
    trade_name: Optional[str] = None
    pan: Optional[str] = None
    gstin: Optional[str] = None
    mapped_tally_company_id: Optional[str] = None
    mapped_tally_company_name: Optional[str] = None
    financial_year: Optional[str] = None


class TallyCompanyResponse(BaseModel):
    id: str
    tally_instance_id: str
    company_id: Optional[str] = None
    tally_guid: str
    company_name: str
    financial_year: Optional[str] = None
    books_from: Optional[str] = None
    status: str
    last_seen_at: Optional[str] = None


# =========================================================================
# ENDPOINTS
# =========================================================================


@router.get("/companies", response_model=List[CompanyResponse])
def list_companies(db: Session = Depends(get_db)):
    """List all WAAST360 Companies and their mapped Tally Company."""
    try:
        companies = db.scalars(select(Company).where(Company.is_deleted == False)).all()  # noqa: E712
        results = []
        for c in companies:
            mapped_tc = c.tally_companies[0] if c.tally_companies else None
            results.append(
                CompanyResponse(
                    id=str(c.id),
                    organization_id=str(c.organization_id),
                    legal_name=c.legal_name,
                    trade_name=c.trade_name,
                    pan=c.pan,
                    gstin=c.gstin,
                    mapped_tally_company_id=str(mapped_tc.id) if mapped_tc else None,
                    mapped_tally_company_name=mapped_tc.company_name if mapped_tc else None,
                    financial_year=mapped_tc.financial_year if mapped_tc and mapped_tc.financial_year else "2024-2025",
                )
            )
        return results
    except Exception:
        return []


@router.post("/companies", response_model=CompanyResponse)
def create_company(payload: CompanyCreateRequest, db: Session = Depends(get_db)):
    """Create a WAAST360 Company."""
    # Ensure default organization exists
    org = db.scalar(select(Organization).where(Organization.slug == payload.organization_slug))
    if not org:
        org = Organization(
            legal_name="Default Organization", slug=payload.organization_slug or "default-org"
        )
        db.add(org)
        db.flush()

    company = Company(
        organization_id=org.id,
        legal_name=payload.legal_name,
        trade_name=payload.trade_name,
        pan=payload.pan,
        gstin=payload.gstin,
        currency=payload.currency,
    )
    db.add(company)
    db.commit()
    db.refresh(company)

    return CompanyResponse(
        id=str(company.id),
        organization_id=str(company.organization_id),
        legal_name=company.legal_name,
        trade_name=company.trade_name,
        pan=company.pan,
        gstin=company.gstin,
    )


@router.get("/tally-companies", response_model=List[TallyCompanyResponse])
def list_tally_companies(db: Session = Depends(get_db)):
    """List all discovered Tally Companies and their WAAST360 mapping status."""
    try:
        tally_comps = db.scalars(select(TallyCompany)).all()
        return [
            TallyCompanyResponse(
                id=str(tc.id),
                tally_instance_id=str(tc.tally_instance_id),
                company_id=str(tc.company_id) if tc.company_id else None,
                tally_guid=tc.tally_guid,
                company_name=tc.company_name,
                financial_year=tc.financial_year,
                books_from=tc.books_from.isoformat() if tc.books_from else None,
                status=tc.status,
                last_seen_at=tc.last_seen_at.isoformat() if tc.last_seen_at else None,
            )
            for tc in tally_comps
        ]
    except Exception:
        return []


@router.post("/companies/{company_id}/map-tally/{tally_company_id}")
def map_tally_company(
    company_id: str,
    tally_company_id: str,
    db: Session = Depends(get_db),
):
    """
    Explicitly map a discovered Tally Company to a WAAST360 Company.
    Preserves: WAAST360 Company != Tally Instance != Tally Company.
    """
    comp_uuid = uuid.UUID(company_id)
    tc_uuid = uuid.UUID(tally_company_id)

    company = db.scalar(select(Company).where(Company.id == comp_uuid, Company.is_deleted == False))  # noqa: E712
    if not company:
        raise HTTPException(status_code=404, detail="WAAST360 Company not found")

    tally_comp = db.scalar(select(TallyCompany).where(TallyCompany.id == tc_uuid))
    if not tally_comp:
        raise HTTPException(status_code=404, detail="Tally Company not found")

    # Associate
    tally_comp.company_id = company.id
    tally_comp.status = "MAPPED"
    db.commit()

    return {
        "status": "mapped",
        "company_id": str(company.id),
        "company_name": company.legal_name,
        "tally_company_id": str(tally_comp.id),
        "tally_company_name": tally_comp.company_name,
        "tally_guid": tally_comp.tally_guid,
    }


@router.post("/tally-companies/{tally_company_id}/create-and-map")
def create_and_map_company(
    tally_company_id: str,
    db: Session = Depends(get_db),
):
    """
    Convenience endpoint: Automatically create a new WAAST360 Company using
    the discovered Tally Company's identity, and map them together immediately.
    """
    tc_uuid = uuid.UUID(tally_company_id)
    tally_comp = db.scalar(select(TallyCompany).where(TallyCompany.id == tc_uuid))
    if not tally_comp:
        raise HTTPException(status_code=404, detail="Tally Company not found")

    # Get instance org
    instance = tally_comp.tally_instance
    org_id = instance.organization_id if instance else None
    if not org_id:
        org = db.scalar(select(Organization).where(Organization.slug == "default-org"))
        if not org:
            org = Organization(legal_name="Default Organization", slug="default-org")
            db.add(org)
            db.flush()
        org_id = org.id

    new_company = Company(
        organization_id=org_id,
        legal_name=tally_comp.company_name,
        trade_name=tally_comp.company_name,
        currency="INR",
    )
    db.add(new_company)
    db.flush()

    tally_comp.company_id = new_company.id
    tally_comp.status = "MAPPED"
    db.commit()

    return {
        "status": "created_and_mapped",
        "company_id": str(new_company.id),
        "company_name": new_company.legal_name,
        "tally_company_id": str(tally_comp.id),
        "tally_company_name": tally_comp.company_name,
        "tally_guid": tally_comp.tally_guid,
    }
