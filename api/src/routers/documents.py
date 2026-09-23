import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.ai.factory import get_ai_provider
from src.ai.models import ExtractedInvoiceData
from src.core.database import get_db
from src.models.entities import (
    Company,
    Document,
    DocumentExtraction,
    DocumentVersion,
    ExtractionField,
)

router = APIRouter(prefix="/api/v1/documents", tags=["Document Ingestion & AI Extraction"])

# Storage directory for uploaded documents
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================================
# SCHEMAS
# =========================================================================


class DocumentResponse(BaseModel):
    id: str
    organization_id: str
    company_id: str
    document_number: Optional[str] = None
    file_name: str
    file_type: str
    file_size_bytes: int
    sha256_checksum: str
    status: str
    is_duplicate: bool = False
    created_at: str


class DocumentExtractionResponse(BaseModel):
    document_id: str
    extraction_id: str
    ai_provider: str
    model_name: str
    confidence_score: Optional[float] = None
    status: str
    extracted_data: ExtractedInvoiceData


# =========================================================================
# ENDPOINTS
# =========================================================================


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    company_id: str = Form(...),
    organization_slug: str = Form("default-org"),
    db: Session = Depends(get_db),
):
    """
    Phase 3B: Ingest invoice documents into WAAST360.
    Computes cryptographic SHA256 checksum, checks for duplicate submissions,
    and establishes Document & DocumentVersion entities in PostgreSQL.
    """
    comp_uuid = uuid.UUID(company_id)
    company = db.scalar(
        select(Company).where(Company.id == comp_uuid, Company.is_deleted.is_(False))
    )
    if not company:
        raise HTTPException(status_code=404, detail="WAAST360 Company not found")

    # Read content & compute hash
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    sha256_hash = hashlib.sha256(file_bytes).hexdigest()

    # Check for duplicate submission
    existing_doc = db.scalar(
        select(Document).where(
            Document.company_id == comp_uuid,
            Document.sha256_checksum == sha256_hash,
            Document.is_deleted.is_(False),
        )
    )
    is_duplicate = existing_doc is not None

    # Persist file to local storage
    file_ext = Path(file.filename or "invoice").suffix or ".bin"
    saved_filename = f"{uuid.uuid4().hex}{file_ext}"
    saved_path = UPLOAD_DIR / saved_filename
    with open(saved_path, "wb") as f:
        f.write(file_bytes)

    # Create Document record with initial stage RECEIVED
    doc_number = f"DOC-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{sha256_hash[:6].upper()}"
    new_doc = Document(
        organization_id=company.organization_id,
        company_id=company.id,
        document_number=doc_number,
        file_name=file.filename or "uploaded_invoice",
        file_type=file.content_type or "application/octet-stream",
        file_size_bytes=len(file_bytes),
        storage_path=str(saved_path),
        sha256_checksum=sha256_hash,
        status="DUPLICATE_FLAGGED" if is_duplicate else "RECEIVED",
    )
    db.add(new_doc)
    db.flush()

    # Create DocumentVersion 1
    version = DocumentVersion(
        document_id=new_doc.id,
        version_number=1,
        storage_path=str(saved_path),
        sha256_checksum=sha256_hash,
    )
    db.add(version)
    db.commit()
    db.refresh(new_doc)

    return DocumentResponse(
        id=str(new_doc.id),
        organization_id=str(new_doc.organization_id),
        company_id=str(new_doc.company_id),
        document_number=new_doc.document_number,
        file_name=new_doc.file_name,
        file_type=new_doc.file_type,
        file_size_bytes=new_doc.file_size_bytes,
        sha256_checksum=new_doc.sha256_checksum,
        status=new_doc.status,
        is_duplicate=is_duplicate,
        created_at=new_doc.created_at.isoformat(),
    )


@router.post("/{document_id}/extract", response_model=DocumentExtractionResponse)
def extract_document(
    document_id: str,
    db: Session = Depends(get_db),
):
    """
    Phase 3C: Run provider-agnostic AI extraction on ingested document.
    Defaults to GeminiProvider (or deterministic fallback if key not configured).
    Saves DocumentExtraction and granular ExtractionField entities in PostgreSQL.
    """
    doc_uuid = uuid.UUID(document_id)
    doc = db.scalar(select(Document).where(Document.id == doc_uuid, Document.is_deleted.is_(False)))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    version = doc.versions[0] if doc.versions else None
    if not version:
        raise HTTPException(status_code=400, detail="Document has no valid version")

    # Read bytes from storage path
    file_path = Path(version.storage_path)
    if not file_path.exists():
        raise HTTPException(status_code=500, detail="Stored document file missing from disk")

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    # Instantiate Provider
    provider = get_ai_provider("gemini")
    start_time = datetime.now(timezone.utc)
    extracted = provider.extract_invoice(
        file_bytes=file_bytes,
        filename=doc.file_name,
        mime_type=doc.file_type,
    )
    elapsed_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

    # Persist DocumentExtraction
    extraction = DocumentExtraction(
        document_version_id=version.id,
        ai_provider=provider.provider_name,
        model_name=provider.model_name,
        raw_response_json=extracted.model_dump(),
        confidence_score=extracted.confidence,
        processing_time_ms=elapsed_ms,
    )
    db.add(extraction)
    db.flush()

    # Persist granular ExtractionField records
    field_mappings = [
        ("vendor_name", extracted.vendor_name, extracted.vendor_name),
        ("vendor_gstin", extracted.vendor_gstin or "", extracted.vendor_gstin or ""),
        ("invoice_number", extracted.invoice_number, extracted.invoice_number),
        ("invoice_date", extracted.invoice_date, extracted.invoice_date),
        ("taxable_amount", str(extracted.taxable_amount), str(extracted.taxable_amount)),
        ("cgst_amount", str(extracted.cgst_amount), str(extracted.cgst_amount)),
        ("sgst_amount", str(extracted.sgst_amount), str(extracted.sgst_amount)),
        ("igst_amount", str(extracted.igst_amount), str(extracted.igst_amount)),
        ("total_amount", str(extracted.total_amount), str(extracted.total_amount)),
    ]

    for field_name, val, _ in field_mappings:
        db.add(
            ExtractionField(
                document_extraction_id=extraction.id,
                field_name=field_name,
                field_value_text=val,
                confidence_score=extracted.confidence,
            )
        )

    # Update document status to EXTRACTED
    doc.status = "EXTRACTED"
    db.commit()

    return DocumentExtractionResponse(
        document_id=str(doc.id),
        extraction_id=str(extraction.id),
        ai_provider=extraction.ai_provider,
        model_name=extraction.model_name,
        confidence_score=float(extraction.confidence_score)
        if extraction.confidence_score
        else None,
        status="EXTRACTED",
        extracted_data=extracted,
    )


@router.get("/{document_id}/extraction", response_model=Optional[DocumentExtractionResponse])
def get_document_extraction(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve persisted AI extraction for a document across browser reloads."""
    try:
        doc_uuid = uuid.UUID(document_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    doc = db.scalar(select(Document).where(Document.id == doc_uuid, Document.is_deleted.is_(False)))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    version = doc.versions[0] if doc.versions else None
    if not version or not version.extractions:
        return None

    extraction = version.extractions[0]
    if not extraction.raw_response_json:
        return None

    try:
        extracted = ExtractedInvoiceData.model_validate(extraction.raw_response_json)
    except Exception:
        return None

    return DocumentExtractionResponse(
        document_id=str(doc.id),
        extraction_id=str(extraction.id),
        ai_provider=extraction.ai_provider,
        model_name=extraction.model_name,
        confidence_score=float(extraction.confidence_score)
        if extraction.confidence_score
        else None,
        status=doc.status,
        extracted_data=extracted,
    )


@router.get("", response_model=List[DocumentResponse])
def list_documents(
    company_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List documents for a company with current processing stage."""
    query = (
        select(Document).where(Document.is_deleted.is_(False)).order_by(Document.created_at.desc())
    )
    if company_id:
        query = query.where(Document.company_id == uuid.UUID(company_id))

    docs = db.scalars(query).all()
    return [
        DocumentResponse(
            id=str(d.id),
            organization_id=str(d.organization_id),
            company_id=str(d.company_id),
            document_number=d.document_number,
            file_name=d.file_name,
            file_type=d.file_type,
            file_size_bytes=d.file_size_bytes,
            sha256_checksum=d.sha256_checksum,
            status=d.status,
            is_duplicate=d.status == "DUPLICATE_FLAGGED",
            created_at=d.created_at.isoformat(),
        )
        for d in docs
    ]
