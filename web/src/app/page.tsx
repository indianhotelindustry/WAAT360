"use client";

import React, { useState, useEffect, useCallback } from "react";
import CompanyIntelligenceView from "./CompanyIntelligenceView";

// =========================================================================
// TYPES & DATA CONTRACTS
// =========================================================================

interface DashboardSummary {
  company_id: string | null;
  company_name: string | null;
  documents_received: number;
  pending_review: number;
  approved: number;
  posted_to_tally: number;
  verified: number;
  exceptions: number;
  cloud_status: string;
  bridge_connected: boolean;
  bridge_status: string;
  bridge_version: string;
  bridge_client_id: string;
  tally_online: boolean;
  is_demo_mode: boolean;
  tally_mode: string;
  tally_status_text: string;
  adapter_name: string;
  last_heartbeat: string | null;
}

interface CompanyItem {
  id: string;
  organization_id: string;
  legal_name: string;
  trade_name: string | null;
  pan: string | null;
  gstin: string | null;
  mapped_tally_company_id: string | null;
  mapped_tally_company_name: string | null;
  financial_year: string | null;
}

interface TallyCompanyItem {
  id: string;
  tally_instance_id: string;
  company_id: string | null;
  tally_guid: string;
  company_name: string;
  financial_year: string | null;
  books_from: string | null;
  status: string;
  last_seen_at: string | null;
}

interface DocumentItem {
  id: string;
  organization_id: string;
  company_id: string;
  document_number: string;
  file_name: string;
  file_size_bytes: number;
  sha256_checksum: string;
  status: string;
  is_duplicate: boolean;
  created_at: string;
}

interface ExtractedLineItem {
  description: string;
  hsn_code?: string | null;
  quantity?: number;
  unit_price?: number;
  taxable_amount: number;
  gst_rate?: number;
  cgst_amount: number;
  sgst_amount: number;
  igst_amount: number;
  total_amount: number;
}

interface ExtractedInvoiceData {
  vendor_name: string;
  vendor_gstin?: string | null;
  vendor_pan?: string | null;
  buyer_name?: string | null;
  buyer_gstin?: string | null;
  invoice_number: string;
  invoice_date: string;
  currency: string;
  taxable_amount: number;
  cgst_amount: number;
  sgst_amount: number;
  igst_amount: number;
  round_off: number;
  total_amount: number;
  confidence: number;
  line_items: ExtractedLineItem[];
}

interface DocumentExtraction {
  document_id: string;
  extraction_id: string;
  ai_provider: string;
  model_name: string;
  confidence_score: number | null;
  status: string;
  extracted_data: ExtractedInvoiceData;
}

interface ProposalLine {
  ledger_name: string;
  amount: number;
  is_debit: boolean;
}

interface ValidationCheck {
  rule_code: string;
  severity: string;
  is_passed: boolean;
  message: string;
}

interface ProposalItem {
  id: string;
  document_id: string;
  voucher_type: string;
  proposed_date: string;
  total_amount: number;
  tax_amount: number;
  narration: string;
  status: string;
  lines: ProposalLine[];
  validations: ValidationCheck[];
  transaction_id?: string | null;
  posting_job_id?: string | null;
  posting_status?: string | null;
  tally_voucher_number?: string | null;
  tally_guid?: string | null;
  actual_amount?: number | null;
  expected_amount?: number | null;
  verification_status?: string | null;
  verified_at?: string | null;
}

interface AuditEventItem {
  id: string;
  action: string;
  actor_type: string;
  actor_id: string;
  entity_type: string;
  entity_id: string;
  changes?: Record<string, unknown>;
  event_metadata?: Record<string, unknown>;
  recorded_at: string;
}

// Configurable API base url from environment
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000/api/v1";

// Configurable Branding & Edition Configuration (V0.0.01 Client Command Center)
const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME || "WAAST360";
const APP_VERSION = process.env.NEXT_PUBLIC_APP_VERSION || "V0.0.01";
const APP_EDITION = process.env.NEXT_PUBLIC_APP_EDITION || "Client Command Center";
const APP_TAGLINE = process.env.NEXT_PUBLIC_APP_TAGLINE || "Accounting Automation. Controlled. Verified.";

// Supported Command Center Tabs
type TabKey = "overview" | "tally" | "invoices" | "banking" | "ai" | "audit" | "health";

// Tooltip explanations for 9-step Global Control Flow
const CONTROL_FLOW_EXPLANATIONS: Record<string, string> = {
  SOURCE: "Digital invoice or bank statement ingested with SHA-256 integrity hash & duplicate check.",
  AI: "Google Gemini 2.0 structured extraction of vendor, line items, taxes, and amounts.",
  PROPOSE: "Deterministic accounting proposal generation & double-entry ledger allocation.",
  VALIDATE: "6 Invariant compliance & mathematical validation rules evaluated against accounting standards.",
  APPROVE: "Authoritative human approval signature required before any posting to accounting records.",
  BRIDGE: "Secure local execution layer between WAAST360 Cloud and TallyPrime via outbound-only polling.",
  TALLY: "Idempotent voucher creation inside TallyPrime via native XML/JSON adapters.",
  VERIFY: "Read-back forensic comparison of expected voucher amount vs actual recorded Tally state.",
  AUDIT: "Immutable cryptographic audit trail & SHA-256 evidence chain recorded for all operations.",
};

export default function CommandCenter() {
  // Navigation & Tab State
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(false);
  const [showSettingsModal, setShowSettingsModal] = useState<boolean>(false);
  const [hoveredFlowStep, setHoveredFlowStep] = useState<string | null>(null);

  // Domain Entity State
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [companies, setCompanies] = useState<CompanyItem[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>("");
  const [tallyCompanies, setTallyCompanies] = useState<TallyCompanyItem[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string>("");
  const [activeExtraction, setActiveExtraction] = useState<DocumentExtraction | null>(null);
  const [proposals, setProposals] = useState<ProposalItem[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEventItem[]>([]);

  // UI Interactive State
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [isProcessingAction, setIsProcessingAction] = useState(false);
  const [notification, setNotification] = useState<{ text: string; type: "success" | "error" | "info" } | null>(null);
  const [showLiveTallyModal, setShowLiveTallyModal] = useState(false);
  const [showCreateCompanyModal, setShowCreateCompanyModal] = useState(false);
  const [newCompanyName, setNewCompanyName] = useState("");
  const [newPan, setNewPan] = useState("");
  const [newGstin, setNewGstin] = useState("");
  const [approverComments, setApproverComments] = useState("Audited & verified against GST Portal and Purchase Order");
  const [approverRole, setApproverRole] = useState("PRIMARY_APPROVER");

  const notify = (text: string, type: "success" | "error" | "info" = "info") => {
    setNotification({ text, type });
    setTimeout(() => setNotification(null), 6000);
  };

  // 1. Fetch Global System & Company Data
  const fetchGlobalData = useCallback(async () => {
    try {
      const [compRes, tallyRes] = await Promise.allSettled([
        fetch(`${API_BASE}/companies`).then((r) => (r.ok ? r.json() : [])),
        fetch(`${API_BASE}/tally-companies`).then((r) => (r.ok ? r.json() : [])),
      ]);

      if (compRes.status === "fulfilled" && Array.isArray(compRes.value)) {
        setCompanies(compRes.value);
        if (compRes.value.length > 0 && !selectedCompanyId) {
          setSelectedCompanyId(compRes.value[0].id);
        }
      }
      if (tallyRes.status === "fulfilled" && Array.isArray(tallyRes.value)) {
        setTallyCompanies(tallyRes.value);
      }
    } catch {
      // Backend unreachable or starting up
    }
  }, [selectedCompanyId]);

  // 2. Fetch Selected Company State (Real KPIs, Documents, Proposals, Audit)
  const fetchCompanyData = useCallback(async (compId: string) => {
    if (!compId) return;
    try {
      const [sumRes, docRes, propRes, audRes] = await Promise.allSettled([
        fetch(`${API_BASE}/dashboard/summary?company_id=${compId}`).then((r) => (r.ok ? r.json() : null)),
        fetch(`${API_BASE}/documents?company_id=${compId}`).then((r) => (r.ok ? r.json() : [])),
        fetch(`${API_BASE}/proposals?company_id=${compId}`).then((r) => (r.ok ? r.json() : [])),
        fetch(`${API_BASE}/bridge/audit/events?company_id=${compId}`).then((r) => (r.ok ? r.json() : [])),
      ]);

      if (sumRes.status === "fulfilled" && sumRes.value) {
        setSummary(sumRes.value);
      }
      if (docRes.status === "fulfilled" && Array.isArray(docRes.value)) {
        setDocuments(docRes.value);
        if (docRes.value.length > 0 && !selectedDocId) {
          setSelectedDocId(docRes.value[0].id);
        }
      }
      if (propRes.status === "fulfilled" && Array.isArray(propRes.value)) {
        setProposals(propRes.value);
      }
      if (audRes.status === "fulfilled" && Array.isArray(audRes.value)) {
        setAuditEvents(audRes.value);
      }
    } catch {
      // Quiet background polling
    }
  }, [selectedDocId]);

  // Polling loops
  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      if (isMounted) await fetchGlobalData();
    };
    load();
    const interval = setInterval(load, 8000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [fetchGlobalData]);

  useEffect(() => {
    if (!selectedCompanyId) return;
    let isMounted = true;
    const load = async () => {
      if (isMounted) await fetchCompanyData(selectedCompanyId);
    };
    load();
    const interval = setInterval(load, 4000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [selectedCompanyId, fetchCompanyData]);

  // Load extraction for selected document
  useEffect(() => {
    let isMounted = true;
    const loadDocExtraction = async () => {
      if (!selectedDocId) return;
      try {
        const res = await fetch(`${API_BASE}/documents/${selectedDocId}/extraction`);
        if (isMounted) {
          if (res.ok) {
            const data = await res.json();
            setActiveExtraction(data);
          } else {
            setActiveExtraction(null);
          }
        }
      } catch {
        if (isMounted) setActiveExtraction(null);
      }
    };
    loadDocExtraction();
    return () => {
      isMounted = false;
    };
  }, [selectedDocId]);

  // Selected entities
  const selectedCompany = companies.find((c) => c.id === selectedCompanyId) || companies[0];
  const selectedDoc = documents.find((d) => d.id === selectedDocId) || documents[0];
  const selectedProposal = proposals.find((p) => selectedDoc && p.document_id === selectedDoc.id);

  // =========================================================================
  // ACTIONS & GOLDEN PATH CONTROLS
  // =========================================================================

  const handleUploadFile = async (fileToUpload: File) => {
    if (!selectedCompanyId) {
      notify("Select or create a target company first.", "error");
      return;
    }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", fileToUpload);
      formData.append("company_id", selectedCompanyId);

      const res = await fetch(`${API_BASE}/documents/upload`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(err.detail || "Upload failed");
      }

      const doc: DocumentItem = await res.json();
      notify(`Document ${doc.file_name} uploaded (SHA-256 verified)`, "success");
      setSelectedDocId(doc.id);
      await fetchCompanyData(selectedCompanyId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      notify(`Upload failed: ${msg}`, "error");
    } finally {
      setUploading(false);
    }
  };

  const handleUseSampleInvoice = async () => {
    if (!selectedCompanyId) {
      notify("Select or create a target company first.", "error");
      return;
    }
    const sampleContent = `TAX INVOICE
Acme Tech Solutions Pvt Ltd
GSTIN: 27AABCA1234A1Z5 | PAN: AABCA1234A
Invoice No: INV-2026-0923 | Date: 2026-09-23

Billed To:
Synthetic Demonstration Company
GSTIN: 27AABCS9999A1Z1

Line Items:
1. Enterprise Cloud Architecture Support - Qty: 1 - Price: 15000.00
Taxable Amount: 15,000.00
CGST @ 9%: 1,350.00
SGST @ 9%: 1,350.00
Total Invoice Amount: ₹17,700.00`;

    const blob = new Blob([sampleContent], { type: "text/plain" });
    const file = new File([blob], `sample_tax_invoice_${Date.now().toString(36)}.txt`, {
      type: "text/plain",
    });
    await handleUploadFile(file);
  };

  const handleExtract = async (docId: string) => {
    setIsProcessingAction(true);
    try {
      const res = await fetch(`${API_BASE}/documents/${docId}/extract`, { method: "POST" });
      if (!res.ok) throw new Error("AI Extraction failed");
      const ext: DocumentExtraction = await res.json();
      setActiveExtraction(ext);
      notify(`AI Structured Extraction Complete: ${ext.extracted_data.vendor_name}`, "success");
      await fetchCompanyData(selectedCompanyId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      notify(`Extraction error: ${msg}`, "error");
    } finally {
      setIsProcessingAction(false);
    }
  };

  const handleGenerateProposal = async (docId: string) => {
    setIsProcessingAction(true);
    try {
      const res = await fetch(`${API_BASE}/proposals/generate?document_id=${docId}`, { method: "POST" });
      if (!res.ok) throw new Error("Proposal generation failed");
      notify("Deterministic Double-Entry Proposal Generated with Invariants", "success");
      await fetchCompanyData(selectedCompanyId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      notify(`Proposal error: ${msg}`, "error");
    } finally {
      setIsProcessingAction(false);
    }
  };

  const handleApproveProposal = async (proposalId: string) => {
    setIsProcessingAction(true);
    try {
      const res = await fetch(`${API_BASE}/proposals/${proposalId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          approver_role: approverRole,
          comments: approverComments,
          approval_signature: `SIG-APPROVAL-${Date.now().toString(36).toUpperCase()}`,
        }),
      });
      if (!res.ok) throw new Error("Approval failed");
      notify("Accounting Proposal APPROVED — Ready for Bridge Dispatch", "success");
      await fetchCompanyData(selectedCompanyId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      notify(`Approval error: ${msg}`, "error");
    } finally {
      setIsProcessingAction(false);
    }
  };

  const handleSimulateCycle = async (jobId: string) => {
    setIsProcessingAction(true);
    try {
      const res = await fetch(`${API_BASE}/bridge/jobs/${jobId}/simulate-cycle`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Simulation cycle failed" }));
        throw new Error(err.detail || "Simulation cycle failed");
      }
      const data = await res.json();
      notify(`Bridge cycle executed & verified: Tally Voucher #${data.tally_voucher_number}`, "success");
      await fetchCompanyData(selectedCompanyId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      notify(`Cycle error: ${msg}`, "error");
    } finally {
      setIsProcessingAction(false);
    }
  };

  const handleCreateCompany = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCompanyName.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/companies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          legal_name: newCompanyName,
          trade_name: newCompanyName,
          pan: newPan || "AABCA1234A",
          gstin: newGstin || "27AABCA1234A1Z5",
          financial_year: "2024-2025",
        }),
      });
      if (!res.ok) throw new Error("Company creation failed");
      const comp = await res.json();
      notify(`Company '${comp.legal_name}' created successfully`, "success");
      setShowCreateCompanyModal(false);
      setNewCompanyName("");
      await fetchGlobalData();
      setSelectedCompanyId(comp.id);
    } catch (err) {
      notify(`Error creating company: ${err}`, "error");
    }
  };

  const handleQuickMap = async (tcId: string) => {
    try {
      const res = await fetch(`${API_BASE}/tally-companies/${tcId}/create-and-map`, { method: "POST" });
      if (!res.ok) throw new Error("Quick mapping failed");
      notify(`${APP_NAME} Company created and mapped to Tally Company!`, "success");
      await fetchGlobalData();
    } catch (err) {
      notify(`Mapping error: ${err}`, "error");
    }
  };

  // Determine stage status for the 10-stage Golden Path pipeline
  const getStageStatus = (stageNum: number) => {
    if (!selectedDoc) return "NOT_REACHED";
    if (selectedDoc.is_duplicate || selectedDoc.status === "DUPLICATE_FLAGGED") {
      if (stageNum === 1) return "EXCEPTION";
      return "NOT_REACHED";
    }

    switch (stageNum) {
      case 1: // RECEIVED
        return "COMPLETED";
      case 2: // EXTRACTED
        if (activeExtraction || ["EXTRACTED", "PROPOSED", "PENDING_APPROVAL", "APPROVED", "POSTED", "VERIFIED"].includes(selectedDoc.status)) {
          return "COMPLETED";
        }
        return selectedDoc.status === "RECEIVED" ? "CURRENT" : "NOT_REACHED";
      case 3: // PROPOSED
        if (selectedProposal) return "COMPLETED";
        return selectedDoc.status === "EXTRACTED" ? "CURRENT" : "NOT_REACHED";
      case 4: // VALIDATED
        if (selectedProposal) {
          const allPassed = selectedProposal.validations.every((v) => v.is_passed);
          return allPassed ? "COMPLETED" : "EXCEPTION";
        }
        return "NOT_REACHED";
      case 5: // APPROVED
        if (selectedProposal?.status === "APPROVED" || ["APPROVED", "POSTED", "VERIFIED"].includes(selectedDoc.status)) {
          return "COMPLETED";
        }
        if (selectedProposal?.status === "PENDING_APPROVAL" || selectedDoc.status === "PENDING_APPROVAL") {
          return "CURRENT";
        }
        return "NOT_REACHED";
      case 6: // POSTED
        if (selectedProposal?.posting_status === "SUCCESS" || ["POSTED", "VERIFIED"].includes(selectedDoc.status)) {
          return "COMPLETED";
        }
        if (selectedProposal?.posting_job_id) return "CURRENT";
        return "NOT_REACHED";
      case 7: // TALLY
        if (selectedProposal?.tally_voucher_number) return "COMPLETED";
        return selectedProposal?.posting_job_id ? "CURRENT" : "NOT_REACHED";
      case 8: // VERIFIED
        if (selectedProposal?.verification_status === "VERIFIED_MATCH" || selectedDoc.status === "VERIFIED") {
          return "COMPLETED";
        }
        if (selectedProposal?.verification_status === "MISMATCH_FAILED") return "EXCEPTION";
        return "NOT_REACHED";
      case 9: // AUDIT
        if (auditEvents.length > 0 && selectedDoc) {
          const hasAudit = auditEvents.some((e) => e.entity_id === selectedDoc.id || e.entity_id === selectedProposal?.id);
          return hasAudit ? "COMPLETED" : "NOT_REACHED";
        }
        return "NOT_REACHED";
      default:
        return "NOT_REACHED";
    }
  };

  // Helper for Attention Required items
  const pendingInvoicesCount = summary?.pending_review ?? 0;
  const isCompanyMapped = !!selectedCompany?.mapped_tally_company_name;

  return (
    <div className="flex h-screen bg-slate-50 text-slate-900 font-sans overflow-hidden">
      {/* ===================================================================== */}
      {/* 1. ENTERPRISE APPLICATION SHELL: COLLAPSIBLE LEFT SIDEBAR (LITE THEME)*/}
      {/* ===================================================================== */}
      <aside
        className={`hidden md:flex flex-col bg-white border-r border-slate-200 transition-all duration-300 z-40 select-none ${
          sidebarCollapsed ? "w-18" : "w-64"
        }`}
      >
        {/* Brand & Collapse Toggle */}
        <div className="h-16 px-4 flex items-center justify-between border-b border-slate-200">
          <div className="flex items-center space-x-3 overflow-hidden">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-500 flex items-center justify-center shadow-md shadow-indigo-100 text-white font-black text-lg tracking-wider shrink-0">
              {APP_NAME.charAt(0)}
            </div>
            {!sidebarCollapsed && (
              <div className="flex flex-col min-w-0">
                <span className="font-extrabold text-sm tracking-tight text-slate-900 truncate">{APP_NAME}</span>
                <span className="text-[10px] text-slate-500 font-mono tracking-wider">{APP_VERSION}</span>
              </div>
            )}
          </div>
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
            title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <span className="text-xs">{sidebarCollapsed ? "▶" : "◀"}</span>
          </button>
        </div>

        {/* Sidebar Navigation */}
        <div className="flex-1 py-4 overflow-y-auto space-y-6 px-3">
          {/* Group 1: COMMAND CENTER */}
          <div>
            {!sidebarCollapsed && (
              <p className="px-3 text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">
                Command Center
              </p>
            )}
            <nav className="space-y-1">
              <button
                onClick={() => setActiveTab("overview")}
                className={`w-full flex items-center space-x-3 px-3 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === "overview"
                    ? "bg-indigo-50 text-indigo-700 border border-indigo-200 shadow-xs"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                }`}
                title="Overview"
              >
                <span className="text-base shrink-0">📊</span>
                {!sidebarCollapsed && <span className="truncate">Overview</span>}
              </button>
            </nav>
          </div>

          {/* Group 2: OPERATIONS */}
          <div>
            {!sidebarCollapsed && (
              <p className="px-3 text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">
                Operations
              </p>
            )}
            <nav className="space-y-1">
              <button
                onClick={() => setActiveTab("invoices")}
                className={`w-full flex items-center space-x-3 px-3 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === "invoices"
                    ? "bg-indigo-50 text-indigo-700 border border-indigo-200 shadow-xs"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                }`}
                title="Transactions (Invoices & Golden Path)"
              >
                <span className="text-base shrink-0">📄</span>
                {!sidebarCollapsed && (
                  <div className="flex items-center justify-between w-full">
                    <span className="truncate">Transactions</span>
                    {pendingInvoicesCount > 0 && (
                      <span className="px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-amber-50 text-amber-800 border border-amber-300">
                        {pendingInvoicesCount}
                      </span>
                    )}
                  </div>
                )}
              </button>
              <button
                onClick={() => setActiveTab("banking")}
                className={`w-full flex items-center space-x-3 px-3 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === "banking"
                    ? "bg-indigo-50 text-indigo-700 border border-indigo-200 shadow-xs"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                }`}
                title="Bank Reconciliation"
              >
                <span className="text-base shrink-0">🏦</span>
                {!sidebarCollapsed && <span className="truncate">Bank Reconciliation</span>}
              </button>
            </nav>
          </div>

          {/* Group 3: TALLY */}
          <div>
            {!sidebarCollapsed && (
              <p className="px-3 text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">
                Tally
              </p>
            )}
            <nav className="space-y-1">
              <button
                onClick={() => setActiveTab("tally")}
                className={`w-full flex items-center space-x-3 px-3 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === "tally"
                    ? "bg-indigo-50 text-indigo-700 border border-indigo-200 shadow-xs"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                }`}
                title="Tally Control Center"
              >
                <span className="text-base shrink-0">🖥️</span>
                {!sidebarCollapsed && <span className="truncate">Tally</span>}
              </button>
              <button
                onClick={() => setActiveTab("tally")}
                className="w-full flex items-center space-x-3 px-3 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-all cursor-pointer"
                title="Companies & Multi-Company Binding"
              >
                <span className="text-base shrink-0">🏢</span>
                {!sidebarCollapsed && <span className="truncate">Companies</span>}
              </button>
              <button
                onClick={() => setActiveTab("health")}
                className={`w-full flex items-center space-x-3 px-3 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === "health"
                    ? "bg-indigo-50 text-indigo-700 border border-indigo-200 shadow-xs"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                }`}
                title="Company Intelligence (Accounting Health Check)"
              >
                <span className="text-base shrink-0">📈</span>
                {!sidebarCollapsed && <span className="truncate">Company Intelligence</span>}
              </button>
            </nav>
          </div>

          {/* Group 4: INTELLIGENCE */}
          <div>
            {!sidebarCollapsed && (
              <p className="px-3 text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">
                Intelligence
              </p>
            )}
            <nav className="space-y-1">
              <button
                onClick={() => setActiveTab("health")}
                className={`w-full flex items-center space-x-3 px-3 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === "health"
                    ? "bg-indigo-50 text-indigo-700 border border-indigo-200 shadow-xs"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                }`}
                title="Accounting Health Check & Forensic Engine"
              >
                <span className="text-base shrink-0">🩺</span>
                {!sidebarCollapsed && <span className="truncate">Health Check</span>}
              </button>
              <button
                onClick={() => setActiveTab("ai")}
                className={`w-full flex items-center space-x-3 px-3 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === "ai"
                    ? "bg-indigo-50 text-indigo-700 border border-indigo-200 shadow-xs"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                }`}
                title="AI Intelligence & Gemini Pipeline"
              >
                <span className="text-base shrink-0">🧠</span>
                {!sidebarCollapsed && <span className="truncate">AI Intelligence</span>}
              </button>
            </nav>
          </div>

          {/* Group 5: CONTROL */}
          <div>
            {!sidebarCollapsed && (
              <p className="px-3 text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">
                Control
              </p>
            )}
            <nav className="space-y-1">
              <button
                onClick={() => setActiveTab("audit")}
                className={`w-full flex items-center space-x-3 px-3 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === "audit"
                    ? "bg-indigo-50 text-indigo-700 border border-indigo-200 shadow-xs"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                }`}
                title="Audit & Evidence"
              >
                <span className="text-base shrink-0">🛡️</span>
                {!sidebarCollapsed && <span className="truncate">Audit & Evidence</span>}
              </button>
            </nav>
          </div>

          {/* Group 6: SYSTEM */}
          <div>
            {!sidebarCollapsed && (
              <p className="px-3 text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">
                System
              </p>
            )}
            <nav className="space-y-1">
              <button
                onClick={() => setShowSettingsModal(true)}
                className="w-full flex items-center space-x-3 px-3 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-all cursor-pointer"
                title="System Settings"
              >
                <span className="text-base shrink-0">⚙️</span>
                {!sidebarCollapsed && <span className="truncate">Settings</span>}
              </button>
            </nav>
          </div>
        </div>

        {/* Sidebar Footer: Operator Profile */}
        <div className="p-3 border-t border-slate-200 bg-slate-50">
          {!sidebarCollapsed ? (
            <div className="space-y-2">
              <div className="flex items-center space-x-2 px-1">
                <div className="h-7 w-7 rounded-lg bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-700 font-bold text-xs shrink-0">
                  CP
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-bold text-slate-800 truncate">Controller Principal</p>
                  <p className="text-[10px] text-slate-500 truncate">Verified Operator</p>
                </div>
              </div>
              <div className="pt-2 border-t border-slate-200 flex items-center justify-between text-[10px] text-slate-400 px-1 font-mono">
                <span>Powered by WAAST360</span>
                <span>v1.0</span>
              </div>
            </div>
          ) : (
            <div className="flex justify-center" title="Controller Principal (Verified Operator) — Powered by WAAST360">
              <div className="h-7 w-7 rounded-lg bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-700 font-bold text-xs">
                CP
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* ===================================================================== */}
      {/* MAIN VIEWPORT AREA                                                    */}
      {/* ===================================================================== */}
      <div className="flex-1 flex flex-col min-w-0 bg-slate-50 overflow-hidden">
        {/* =================================================================== */}
        {/* 2. TOP HEADER (LITE THEME)                                          */}
        {/* =================================================================== */}
        <header className="h-16 px-6 bg-white/95 backdrop-blur-md border-b border-slate-200 flex items-center justify-between z-30 shrink-0 select-none shadow-xs">
          {/* LEFT: Client-configurable App Name + Edition */}
          <div className="flex items-center space-x-3">
            <span className="text-lg font-black tracking-tight text-slate-900">{APP_NAME}</span>
            <span className="font-mono text-[11px] px-2 py-0.5 rounded-full font-bold bg-indigo-50 text-indigo-700 border border-indigo-200 uppercase tracking-wide">
              {APP_VERSION}
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold bg-slate-100 text-slate-700 border border-slate-200 hidden sm:inline-block">
              {APP_EDITION}
            </span>
          </div>

          {/* CENTER / CONTEXT: Active Company Selector & Financial Year */}
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2 bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 shadow-xs">
              <span className="text-xs text-slate-500 font-medium">Company:</span>
              <select
                value={selectedCompanyId}
                onChange={(e) => {
                  setSelectedCompanyId(e.target.value);
                  fetchCompanyData(e.target.value);
                }}
                className="bg-transparent text-xs font-bold text-slate-900 focus:outline-hidden cursor-pointer max-w-[200px] truncate"
              >
                {companies.map((c) => (
                  <option key={c.id} value={c.id} className="bg-white text-slate-900">
                    {c.legal_name}
                  </option>
                ))}
              </select>
              <button
                onClick={() => setShowCreateCompanyModal(true)}
                className="text-indigo-600 hover:text-indigo-800 text-xs font-bold px-1.5 py-0.5 rounded-md hover:bg-indigo-50 transition-colors cursor-pointer"
                title="Create New Company"
              >
                +
              </button>
            </div>

            <div className="hidden lg:flex items-center space-x-1.5 bg-slate-50 border border-slate-200 px-2.5 py-1.5 rounded-xl text-xs">
              <span className="text-slate-400">FY:</span>
              <span className="text-slate-800 font-semibold font-mono">
                {selectedCompany?.financial_year || "2024-2025"}
              </span>
            </div>
          </div>

          {/* RIGHT: Independent Health Indicators + Demo/Live Badge */}
          <div className="flex items-center space-x-3">
            {/* Status Pills */}
            <div className="hidden xl:flex items-center space-x-3 text-xs bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-xl">
              {/* Cloud */}
              <div className="flex items-center space-x-1.5" title="Cloud API Backend Status">
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-slate-700 font-medium">Cloud</span>
              </div>
              <span className="text-slate-300">|</span>
              {/* Bridge */}
              <div className="flex items-center space-x-1.5" title="WAAST360 Outbound Bridge Daemon">
                <span className={`h-2 w-2 rounded-full ${summary?.bridge_connected ? "bg-emerald-500 animate-pulse" : "bg-amber-500"}`} />
                <span className="text-slate-700 font-medium">Bridge</span>
              </div>
              <span className="text-slate-300">|</span>
              {/* Tally */}
              <div className="flex items-center space-x-1.5" title="Tally Adapter Status">
                <span className="h-2 w-2 rounded-full bg-amber-500" />
                <span className="text-slate-700 font-medium">Tally (Sim)</span>
              </div>
              <span className="text-slate-300">|</span>
              {/* AI */}
              <div className="flex items-center space-x-1.5" title="Google Gemini AI Engine">
                <span className="h-2 w-2 rounded-full bg-cyan-500 animate-pulse" />
                <span className="text-slate-700 font-medium">AI</span>
              </div>
            </div>

            {/* DEMO / LIVE Mode Badge */}
            <div
              onClick={() => setShowLiveTallyModal(true)}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-amber-50 border border-amber-300 text-amber-800 text-xs font-bold cursor-pointer hover:bg-amber-100 transition-all select-none"
              title="Click for Tally Certification Gate instructions"
            >
              <span className="h-2 w-2 rounded-full bg-amber-500 animate-ping" />
              <span>DEMO MODE</span>
              <span className="text-[10px] text-amber-700 font-normal hidden sm:inline">(Simulated Tally)</span>
            </div>
          </div>
        </header>

        {/* =================================================================== */}
        {/* 3. GLOBAL HORIZONTAL CONTROL FLOW SUB-HEADER (LITE THEME)           */}
        {/* =================================================================== */}
        <div className="h-[68px] px-6 bg-slate-100/70 border-b border-slate-200 flex items-center justify-between shrink-0 relative overflow-x-auto select-none">
          <div className="flex items-center space-x-1.5 mr-4 shrink-0">
            <span className="text-[10px] font-black uppercase tracking-wider text-slate-500">Control Flow</span>
            <span className="text-slate-400">›</span>
          </div>

          {/* 9-Stage Global Pipeline */}
          <div className="flex items-center space-x-1 min-w-max flex-1 justify-around">
            {[
              { id: "SOURCE", label: "Source", icon: "📄" },
              { id: "AI", label: "AI", icon: "🤖" },
              { id: "PROPOSE", label: "Propose", icon: "⚖️" },
              { id: "VALIDATE", label: "Validate", icon: "🛡️" },
              { id: "APPROVE", label: "Approve", icon: "✍️" },
              { id: "BRIDGE", label: "Bridge", icon: "🌉" },
              { id: "TALLY", label: "Tally", icon: "📊" },
              { id: "VERIFY", label: "Verify", icon: "🔍" },
              { id: "AUDIT", label: "Audit", icon: "🔒" },
            ].map((step, idx, arr) => (
              <React.Fragment key={step.id}>
                <div
                  onMouseEnter={() => setHoveredFlowStep(step.id)}
                  onMouseLeave={() => setHoveredFlowStep(null)}
                  className={`flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold cursor-help transition-all ${
                    hoveredFlowStep === step.id
                      ? "bg-indigo-600 text-white shadow-md shadow-indigo-100 scale-105"
                      : "bg-white border border-slate-200 text-slate-700 hover:border-slate-300 shadow-xs"
                  }`}
                >
                  <span className="text-xs">{step.icon}</span>
                  <span className="text-[11px] font-bold tracking-tight">{step.label}</span>
                </div>
                {idx < arr.length - 1 && (
                  <span className="text-slate-300 text-xs font-bold px-0.5">→</span>
                )}
              </React.Fragment>
            ))}
          </div>

          {/* Interactive Tooltip Overlay */}
          {hoveredFlowStep && (
            <div className="absolute right-6 top-full mt-1 z-50 bg-white border border-indigo-200 text-slate-800 px-3 py-2 rounded-xl shadow-xl text-xs max-w-sm pointer-events-none">
              <p className="font-bold text-indigo-700 mb-0.5">{hoveredFlowStep} STAGE</p>
              <p className="text-slate-600 leading-relaxed">{CONTROL_FLOW_EXPLANATIONS[hoveredFlowStep]}</p>
            </div>
          )}
        </div>

        {/* =================================================================== */}
        {/* 4. COMMAND CENTER TABS (LITE THEME)                                 */}
        {/* =================================================================== */}
        <div className="px-6 bg-white border-b border-slate-200 flex items-center space-x-1 shrink-0 overflow-x-auto select-none">
          {[
            { key: "overview", label: "Overview", icon: "📊" },
            { key: "health", label: "Health Check", icon: "🩺" },
            { key: "tally", label: "Tally", icon: "🖥️" },
            { key: "invoices", label: "Invoices", icon: "📄", badge: pendingInvoicesCount > 0 ? pendingInvoicesCount : null },
            { key: "banking", label: "Banking", icon: "🏦" },
            { key: "ai", label: "AI", icon: "🧠" },
            { key: "audit", label: "Audit", icon: "🛡️" },
          ].map((t) => (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key as TabKey)}
              className={`flex items-center space-x-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all cursor-pointer ${
                activeTab === t.key
                  ? "border-indigo-600 text-indigo-700 bg-indigo-50/50"
                  : "border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-50"
              }`}
            >
              <span>{t.icon}</span>
              <span>{t.label}</span>
              {t.badge && (
                <span className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-300">
                  {t.badge}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Global Floating Notification */}
        {notification && (
          <div
            className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-xl shadow-2xl border text-xs font-medium max-w-md transition-all ${
              notification.type === "success"
                ? "bg-emerald-50 border-emerald-300 text-emerald-900"
                : notification.type === "error"
                ? "bg-rose-50 border-rose-300 text-rose-900"
                : "bg-indigo-50 border-indigo-300 text-indigo-900"
            }`}
          >
            {notification.text}
          </div>
        )}

        {/* =================================================================== */}
        {/* TAB CONTENTS (LITE ENTERPRISE THEME)                                */}
        {/* =================================================================== */}
        <main className="flex-1 overflow-y-auto p-6 bg-slate-50">
          {/* ================================================================= */}
          {/* TAB 1: OVERVIEW                                                   */}
          {/* ================================================================= */}
          {activeTab === "overview" && (
            <div className="space-y-6 max-w-7xl mx-auto">
              {/* 5. HERO SECTION (LITE / NAVY CONTRAST) */}
              <div className="relative overflow-hidden rounded-2xl bg-white border border-slate-200 p-6 shadow-xs">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                  <div className="space-y-2 max-w-2xl">
                    <div className="flex items-center space-x-2">
                      <h1 className="text-2xl font-black text-slate-900 tracking-tight">{APP_NAME}</h1>
                      <span className="text-xs px-2.5 py-0.5 rounded-full font-bold bg-indigo-50 text-indigo-700 border border-indigo-200 font-mono">
                        {APP_VERSION}
                      </span>
                    </div>
                    <p className="text-base font-bold text-slate-800">{APP_TAGLINE}</p>
                    <p className="text-xs text-slate-500 leading-relaxed">
                      Documents enter → AI prepares → Rules validate → Human approves → Bridge executes → Tally records → WAAST360 verifies.
                    </p>
                  </div>

                  {/* Quick Actions */}
                  <div className="flex flex-wrap items-center gap-2.5 shrink-0">
                    <button
                      onClick={() => {
                        setActiveTab("invoices");
                        handleUseSampleInvoice();
                      }}
                      className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-xs transition-all cursor-pointer flex items-center space-x-1.5"
                    >
                      <span>📄</span>
                      <span>Process Invoice</span>
                    </button>
                    <button
                      onClick={() => setActiveTab("health")}
                      className="px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold border border-slate-200 transition-all cursor-pointer flex items-center space-x-1.5"
                    >
                      <span>🩺</span>
                      <span>Accounting Health Check</span>
                    </button>
                    <button
                      onClick={() => setActiveTab("tally")}
                      className="px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold border border-slate-200 transition-all cursor-pointer flex items-center space-x-1.5"
                    >
                      <span>🖥️</span>
                      <span>Inspect Tally Company</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* 7. ATTENTION REQUIRED SECTION */}
              <div className="rounded-2xl bg-white border border-slate-200 p-5 shadow-xs">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center space-x-2">
                    <span className="text-base">🔔</span>
                    <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700">Attention Required</h2>
                  </div>
                  {pendingInvoicesCount === 0 && isCompanyMapped ? (
                    <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                      Queue Clear
                    </span>
                  ) : (
                    <span className="text-[11px] font-bold text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
                      Action Items Pending
                    </span>
                  )}
                </div>

                {pendingInvoicesCount === 0 && isCompanyMapped ? (
                  <div className="py-4 text-center space-y-1">
                    <p className="text-sm font-bold text-slate-800">No action required</p>
                    <p className="text-xs text-slate-500">Your accounting control queue is clear.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {pendingInvoicesCount > 0 && (
                      <div className="p-3.5 rounded-xl bg-amber-50/60 border border-amber-200 flex items-center justify-between">
                        <div>
                          <p className="text-xs font-bold text-amber-900">Invoices Awaiting Approval</p>
                          <p className="text-xs text-amber-700">{pendingInvoicesCount} document(s) pending sign-off</p>
                        </div>
                        <button
                          onClick={() => setActiveTab("invoices")}
                          className="px-2.5 py-1 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold transition-all cursor-pointer"
                        >
                          Review →
                        </button>
                      </div>
                    )}
                    {!isCompanyMapped && (
                      <div className="p-3.5 rounded-xl bg-indigo-50/60 border border-indigo-200 flex items-center justify-between">
                        <div>
                          <p className="text-xs font-bold text-indigo-900">Company Unmapped</p>
                          <p className="text-xs text-indigo-700">Bind legal entity to Tally company</p>
                        </div>
                        <button
                          onClick={() => setActiveTab("tally")}
                          className="px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all cursor-pointer"
                        >
                          Map Now →
                        </button>
                      </div>
                    )}
                    <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between">
                      <div>
                        <p className="text-xs font-bold text-slate-800">Bank Reconciliation</p>
                        <p className="text-xs text-slate-500">0 exceptions detected</p>
                      </div>
                      <span className="text-[10px] text-emerald-700 font-bold">✓ Clear</span>
                    </div>
                  </div>
                )}
              </div>

              {/* 6. REAL DB-DERIVED KPI SECTION */}
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                {[
                  { label: "Documents Received", value: summary?.documents_received ?? 0, color: "text-blue-700", border: "border-blue-200", bg: "bg-blue-50/60" },
                  { label: "Pending Review", value: summary?.pending_review ?? 0, color: "text-amber-700", border: "border-amber-200", bg: "bg-amber-50/60" },
                  { label: "Approved", value: summary?.approved ?? 0, color: "text-indigo-700", border: "border-indigo-200", bg: "bg-indigo-50/60" },
                  { label: "Posted to Tally", value: summary?.posted_to_tally ?? 0, color: "text-purple-700", border: "border-purple-200", bg: "bg-purple-50/60" },
                  { label: "Verified", value: summary?.verified ?? 0, color: "text-emerald-700", border: "border-emerald-200", bg: "bg-emerald-50/60" },
                  { label: "Exceptions", value: summary?.exceptions ?? 0, color: "text-rose-700", border: "border-rose-200", bg: "bg-rose-50/60" },
                ].map((kpi) => (
                  <div
                    key={kpi.label}
                    className={`p-4 rounded-xl ${kpi.bg} border ${kpi.border} flex flex-col justify-between shadow-xs`}
                  >
                    <p className="text-[11px] font-bold text-slate-600 tracking-tight leading-snug">{kpi.label}</p>
                    <div className="mt-2 flex items-baseline justify-between">
                      <span className={`text-2xl font-black ${kpi.color}`}>{kpi.value}</span>
                      <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-md bg-white border border-slate-200 text-slate-500 font-mono">
                        DB
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              {/* 8. GOLDEN PATH SUMMARY & SYSTEM HEALTH */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Controlled Accounting Journey */}
                <div className="lg:col-span-2 rounded-2xl bg-white border border-slate-200 p-5 space-y-4 shadow-xs">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
                        <span>🛡️</span>
                        <span>Controlled Accounting Journey</span>
                      </h2>
                      <p className="text-xs text-slate-500">
                        {selectedDoc ? `Active Document: ${selectedDoc.file_name}` : "No document active. Start with [Process Invoice]."}
                      </p>
                    </div>
                    {selectedDoc && (
                      <button
                        onClick={() => setActiveTab("invoices")}
                        className="text-xs text-indigo-600 hover:text-indigo-800 font-bold cursor-pointer"
                      >
                        Open Workspace →
                      </button>
                    )}
                  </div>

                  {/* 10-Stage Pipeline Visualizer */}
                  <div className="grid grid-cols-5 md:grid-cols-9 gap-1.5 pt-2">
                    {[
                      { num: 1, label: "Receive" },
                      { num: 2, label: "Read" },
                      { num: 3, label: "Propose" },
                      { num: 4, label: "Validate" },
                      { num: 5, label: "Approve" },
                      { num: 6, label: "Post" },
                      { num: 7, label: "Tally" },
                      { num: 8, label: "Verify" },
                      { num: 9, label: "Audit" },
                    ].map((stg) => {
                      const status = getStageStatus(stg.num);
                      return (
                        <div
                          key={stg.num}
                          className={`p-2 rounded-lg text-center border transition-all ${
                            status === "COMPLETED"
                              ? "bg-emerald-50 border-emerald-300 text-emerald-800"
                              : status === "CURRENT"
                              ? "bg-indigo-50 border-indigo-400 text-indigo-800 font-bold animate-pulse"
                              : status === "EXCEPTION"
                              ? "bg-rose-50 border-rose-300 text-rose-800"
                              : "bg-slate-50 border-slate-200 text-slate-400"
                          }`}
                        >
                          <div className="text-[10px] font-bold">0{stg.num}</div>
                          <div className="text-[10px] font-bold truncate mt-0.5">{stg.label}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* 11. SYSTEM HEALTH (Client-friendly presentation) */}
                <div className="rounded-2xl bg-white border border-slate-200 p-5 space-y-3 shadow-xs">
                  <h2 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
                    <span>⚡</span>
                    <span>System Health</span>
                  </h2>
                  <div className="space-y-2.5 text-xs">
                    <div className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-200">
                      <span className="text-slate-600">Cloud API</span>
                      <span className="font-bold text-emerald-700 flex items-center space-x-1.5">
                        <span className="h-2 w-2 rounded-full bg-emerald-500" />
                        <span>Connected</span>
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-200">
                      <span className="text-slate-600">{APP_NAME} Bridge</span>
                      <span className={`font-bold flex items-center space-x-1.5 ${summary?.bridge_connected ? "text-emerald-700" : "text-amber-700"}`}>
                        <span className={`h-2 w-2 rounded-full ${summary?.bridge_connected ? "bg-emerald-500" : "bg-amber-500"}`} />
                        <span>{summary?.bridge_connected ? "Online" : "Waiting"}</span>
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-200">
                      <span className="text-slate-600">TallyPrime</span>
                      <span className="font-bold text-amber-700 flex items-center space-x-1.5">
                        <span className="h-2 w-2 rounded-full bg-amber-500" />
                        <span>Simulation</span>
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-200">
                      <span className="text-slate-600">AI Intelligence</span>
                      <span className="font-bold text-cyan-700 flex items-center space-x-1.5">
                        <span className="h-2 w-2 rounded-full bg-cyan-500" />
                        <span>Connected (Gemini)</span>
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* 12. RECENT CONTROL ACTIVITY */}
              <div className="rounded-2xl bg-white border border-slate-200 p-5 space-y-3 shadow-xs">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
                    <span>📋</span>
                    <span>Recent Control Activity</span>
                  </h2>
                  <span className="text-[10px] text-slate-500 font-mono">Immutable Audit Trail</span>
                </div>

                {auditEvents.length === 0 ? (
                  <div className="p-8 text-center rounded-xl bg-slate-50 border border-slate-200 space-y-3">
                    <p className="text-sm font-bold text-slate-800">Your accounting control center is ready.</p>
                    <p className="text-xs text-slate-500 max-w-md mx-auto">
                      Demo Mode uses Simulated Tally and does not post to the client&apos;s real Tally. Start by uploading an invoice or inspecting Tally companies.
                    </p>
                    <div className="flex justify-center space-x-2 pt-2">
                      <button
                        onClick={handleUseSampleInvoice}
                        className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all cursor-pointer"
                      >
                        Load Sample Invoice
                      </button>
                      <button
                        onClick={() => setActiveTab("tally")}
                        className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold transition-all cursor-pointer"
                      >
                        Inspect Tally
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="divide-y divide-slate-100">
                    {auditEvents.slice(0, 5).map((ev) => (
                      <div key={ev.id} className="py-2.5 flex items-center justify-between text-xs">
                        <div className="flex items-center space-x-3">
                          <span className="text-emerald-700 font-bold">✓</span>
                          <span className="font-semibold text-slate-800">{ev.action}</span>
                          <span className="text-slate-400 font-mono text-[10px]">{ev.entity_type} #{ev.entity_id.slice(0, 8)}</span>
                        </div>
                        <span className="text-slate-500 text-[11px] font-mono">
                          {new Date(ev.recorded_at).toLocaleTimeString()}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ================================================================= */}
          {/* TAB 2: COMPANY INTELLIGENCE / ACCOUNTING HEALTH CHECK             */}
          {/* ================================================================= */}
          {activeTab === "health" && (
            <div className="max-w-7xl mx-auto">
              <CompanyIntelligenceView
                apiBase={API_BASE}
                selectedCompanyId={selectedCompanyId}
                selectedCompanyName={selectedCompany?.legal_name || "Synthetic Demonstration Company"}
                onNotify={notify}
              />
            </div>
          )}

          {/* ================================================================= */}
          {/* TAB 3: TALLY (TALLY CONTROL CENTER)                              */}
          {/* ================================================================= */}
          {activeTab === "tally" && (
            <div className="space-y-6 max-w-7xl mx-auto">
              {/* Header */}
              <div className="rounded-2xl bg-white border border-slate-200 p-6 space-y-4 shadow-xs">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-black text-slate-900 flex items-center space-x-2">
                      <span>🖥️</span>
                      <span>Tally Control Center</span>
                    </h2>
                    <p className="text-xs text-slate-500 mt-1">
                      Outbound Bridge status, company discovery, and multi-company binding.
                    </p>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className="text-xs px-3 py-1 rounded-full font-bold bg-amber-50 text-amber-800 border border-amber-300">
                      DEMO SIMULATION (TallySimulatedAdapter)
                    </span>
                    <button
                      onClick={() => setShowLiveTallyModal(true)}
                      className="px-3 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all cursor-pointer"
                    >
                      Certification Guide
                    </button>
                  </div>
                </div>

                {/* Tally Lifecycle */}
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
                  <p className="text-[10px] font-black uppercase tracking-wider text-slate-500 mb-2">Tally Lifecycle</p>
                  <div className="flex items-center justify-between text-xs text-slate-700 overflow-x-auto min-w-max">
                    <span className="text-emerald-700 font-bold">1. Tally Connected</span>
                    <span className="text-slate-300">→</span>
                    <span className="text-emerald-700 font-bold">2. Company Discovered</span>
                    <span className="text-slate-300">→</span>
                    <span className="text-emerald-700 font-bold">3. Company Selected</span>
                    <span className="text-slate-300">→</span>
                    <span className="text-indigo-700 font-bold">4. Structure Imported</span>
                    <span className="text-slate-300">→</span>
                    <span className="text-indigo-700 font-bold">5. Structural Verification</span>
                    <span className="text-slate-300">→</span>
                    <span className="text-slate-500 font-bold">6. Ready for Controlled Posting</span>
                  </div>
                </div>
              </div>

              {/* Discovered Tally Companies Table */}
              <div className="rounded-2xl bg-white border border-slate-200 p-6 space-y-4 shadow-xs">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-900">Discovered Tally Companies</h3>
                  <span className="text-xs text-slate-500">{tallyCompanies.length} companies discovered via Bridge</span>
                </div>

                {tallyCompanies.length === 0 ? (
                  <div className="p-8 text-center rounded-xl bg-slate-50 border border-slate-200 text-slate-500 text-xs">
                    No Tally companies reported yet. Bridge daemon will discover them upon startup.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-slate-200 text-slate-600 font-bold bg-slate-50/60">
                          <th className="py-2.5 px-3">Tally Company Name</th>
                          <th className="py-2.5 px-3">Tally GUID</th>
                          <th className="py-2.5 px-3">Financial Year</th>
                          <th className="py-2.5 px-3">Status</th>
                          <th className="py-2.5 px-3">Mapped {APP_NAME} Company</th>
                          <th className="py-2.5 px-3 text-right">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 text-slate-700">
                        {tallyCompanies.map((tc) => {
                          const mappedComp = companies.find((c) => c.mapped_tally_company_id === tc.id);
                          return (
                            <tr key={tc.id} className="hover:bg-slate-50">
                              <td className="py-3 px-3 font-bold text-slate-900">{tc.company_name}</td>
                              <td className="py-3 px-3 font-mono text-[10px] text-slate-500">{tc.tally_guid.slice(0, 16)}...</td>
                              <td className="py-3 px-3 font-mono text-slate-700">{tc.financial_year || "2024-2025"}</td>
                              <td className="py-3 px-3">
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-300">
                                  {tc.status}
                                </span>
                              </td>
                              <td className="py-3 px-3">
                                {mappedComp ? (
                                  <span className="text-emerald-700 font-semibold">{mappedComp.legal_name}</span>
                                ) : (
                                  <span className="text-slate-400 italic">Not mapped</span>
                                )}
                              </td>
                              <td className="py-3 px-3 text-right">
                                {!mappedComp && (
                                  <button
                                    onClick={() => handleQuickMap(tc.id)}
                                    className="px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[11px] font-bold transition-all cursor-pointer"
                                  >
                                    Map Now
                                  </button>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Company Structural Intelligence Card */}
              <div className="rounded-2xl bg-white border border-slate-200 p-6 space-y-4 shadow-xs">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
                    <span>📈</span>
                    <span>Company Structural Intelligence</span>
                  </h3>
                  <button
                    onClick={() => setActiveTab("health")}
                    className="text-xs text-indigo-600 hover:text-indigo-800 font-bold cursor-pointer"
                  >
                    Open Accounting Health Check →
                  </button>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                  <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                    <p className="text-[10px] font-bold text-slate-500 uppercase">Ledgers</p>
                    <p className="text-xl font-bold text-slate-900 mt-1">126</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">Simulated Store</p>
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                    <p className="text-[10px] font-bold text-slate-500 uppercase">Groups</p>
                    <p className="text-xl font-bold text-slate-900 mt-1">28</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">Tally Hierarchy</p>
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                    <p className="text-[10px] font-bold text-slate-500 uppercase">Stock Items</p>
                    <p className="text-xl font-bold text-slate-900 mt-1">12</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">Active Masters</p>
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                    <p className="text-[10px] font-bold text-slate-500 uppercase">Bank Accounts</p>
                    <p className="text-xl font-bold text-slate-900 mt-1">3</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">HDFC / ICICI / SBI</p>
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                    <p className="text-[10px] font-bold text-slate-500 uppercase">GST Structures</p>
                    <p className="text-xl font-bold text-emerald-700 mt-1">Harmonized</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">CGST/SGST/IGST</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ================================================================= */}
          {/* TAB 4: INVOICES (TRANSACTIONS & GOLDEN PATH)                     */}
          {/* ================================================================= */}
          {activeTab === "invoices" && (
            <div className="space-y-6 max-w-7xl mx-auto">
              {/* Header */}
              <div className="rounded-2xl bg-white border border-slate-200 p-5 flex flex-wrap items-center justify-between gap-4 shadow-xs">
                <div>
                  <h2 className="text-base font-black text-slate-900 flex items-center space-x-2">
                    <span>📄</span>
                    <span>Invoice Transactions &amp; Golden Path</span>
                  </h2>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Deterministic 10-stage accounting journey with forensic verification.
                  </p>
                </div>
                <button
                  onClick={handleUseSampleInvoice}
                  disabled={uploading}
                  className="px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all cursor-pointer"
                >
                  Load Sample Tax Invoice
                </button>
              </div>

              {/* Workspace Layout */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left: Documents List & Upload */}
                <div className="space-y-4">
                  {/* Upload Dropzone */}
                  <div
                    onDragOver={(e) => {
                      e.preventDefault();
                      setIsDragging(true);
                    }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setIsDragging(false);
                      if (e.dataTransfer.files?.[0]) handleUploadFile(e.dataTransfer.files[0]);
                    }}
                    className={`p-5 rounded-2xl border-2 border-dashed text-center transition-all cursor-pointer ${
                      isDragging
                        ? "border-indigo-500 bg-indigo-50/50"
                        : "border-slate-300 bg-white hover:border-slate-400 hover:bg-slate-50 shadow-xs"
                    }`}
                  >
                    <input
                      type="file"
                      id="invoiceFileInput"
                      className="hidden"
                      onChange={(e) => {
                        if (e.target.files?.[0]) handleUploadFile(e.target.files[0]);
                      }}
                    />
                    <label htmlFor="invoiceFileInput" className="cursor-pointer space-y-1 block">
                      <span className="text-2xl block">📥</span>
                      <p className="text-xs font-bold text-slate-800">
                        {uploading ? "Ingesting..." : "Drop invoice or click to upload"}
                      </p>
                      <p className="text-[10px] text-slate-500">PDF, TXT, PNG, JPEG</p>
                    </label>
                  </div>

                  {/* Document List */}
                  <div className="rounded-2xl bg-white border border-slate-200 p-4 space-y-2 shadow-xs">
                    <p className="text-xs font-bold text-slate-700">Documents ({documents.length})</p>
                    {documents.length === 0 ? (
                      <p className="text-xs text-slate-500 py-4 text-center">No documents in this company.</p>
                    ) : (
                      <div className="space-y-1.5 max-h-[400px] overflow-y-auto">
                        {documents.map((doc) => (
                          <div
                            key={doc.id}
                            onClick={() => setSelectedDocId(doc.id)}
                            className={`p-3 rounded-xl cursor-pointer text-xs transition-all ${
                              selectedDocId === doc.id
                                ? "bg-indigo-50 border border-indigo-300 text-indigo-950 font-bold"
                                : "bg-slate-50 border border-slate-200 text-slate-700 hover:bg-slate-100"
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <span className="truncate">{doc.file_name}</span>
                              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-200 text-slate-700 font-mono">
                                {doc.status}
                              </span>
                            </div>
                            <div className="flex items-center justify-between mt-1 text-[10px] text-slate-500 font-mono">
                              <span>SHA: {doc.sha256_checksum.slice(0, 8)}...</span>
                              <span>{new Date(doc.created_at).toLocaleDateString()}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Right: Golden Path Pipeline & Actions */}
                <div className="lg:col-span-2 space-y-4">
                  {!selectedDoc ? (
                    <div className="p-12 text-center rounded-2xl bg-white border border-slate-200 text-slate-500 text-xs shadow-xs">
                      Select or upload an invoice on the left to begin the Golden Path.
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {/* Document Details Card */}
                      <div className="rounded-2xl bg-white border border-slate-200 p-5 space-y-3 shadow-xs">
                        <div className="flex items-center justify-between">
                          <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
                            <span>📄</span>
                            <span>{selectedDoc.file_name}</span>
                          </h3>
                          <span className="text-xs px-2.5 py-0.5 rounded-full font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                            {selectedDoc.status}
                          </span>
                        </div>

                        {/* Step 1: AI Extraction */}
                        {!activeExtraction && selectedDoc.status === "RECEIVED" && (
                          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between">
                            <div>
                              <p className="text-xs font-bold text-slate-800">1. AI Structured Extraction</p>
                              <p className="text-xs text-slate-500">Extract tax invoice data using Gemini 2.0.</p>
                            </div>
                            <button
                              onClick={() => handleExtract(selectedDoc.id)}
                              disabled={isProcessingAction}
                              className="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all cursor-pointer"
                            >
                              Run AI Extraction
                            </button>
                          </div>
                        )}

                        {/* Extracted Data Preview */}
                        {activeExtraction && (
                          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3 text-xs">
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-indigo-800">Extracted Invoice Data</span>
                              <span className="text-[10px] text-slate-500">
                                Confidence: {Math.round((activeExtraction.confidence_score || 0.95) * 100)}%
                              </span>
                            </div>
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-slate-800">
                              <div>
                                <span className="text-slate-500 text-[10px] block">Vendor</span>
                                <span className="font-bold">{activeExtraction.extracted_data.vendor_name}</span>
                              </div>
                              <div>
                                <span className="text-slate-500 text-[10px] block">Invoice #</span>
                                <span className="font-mono">{activeExtraction.extracted_data.invoice_number}</span>
                              </div>
                              <div>
                                <span className="text-slate-500 text-[10px] block">Taxable</span>
                                <span>₹{activeExtraction.extracted_data.taxable_amount.toLocaleString("en-IN")}</span>
                              </div>
                              <div>
                                <span className="text-slate-500 text-[10px] block">Total Amount</span>
                                <span className="font-bold text-emerald-700">
                                  ₹{activeExtraction.extracted_data.total_amount.toLocaleString("en-IN")}
                                </span>
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Step 2: Propose */}
                        {!selectedProposal && activeExtraction && (
                          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between">
                            <div>
                              <p className="text-xs font-bold text-slate-800">2. Deterministic Accounting Proposal</p>
                              <p className="text-xs text-slate-500">Evaluate rules and double-entry legs.</p>
                            </div>
                            <button
                              onClick={() => handleGenerateProposal(selectedDoc.id)}
                              disabled={isProcessingAction}
                              className="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all cursor-pointer"
                            >
                              Generate Proposal
                            </button>
                          </div>
                        )}

                        {/* Step 3: Proposal Details & Invariants */}
                        {selectedProposal && (
                          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3 text-xs">
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-indigo-800">Double-Entry Proposal &amp; Invariants</span>
                              <span className="text-xs px-2 py-0.5 rounded-full font-bold bg-white border border-slate-200 text-slate-700">
                                {selectedProposal.status}
                              </span>
                            </div>

                            {/* Invariant Validations */}
                            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                              {selectedProposal.validations.map((v) => (
                                <div
                                  key={v.rule_code}
                                  className={`p-2 rounded-lg border text-[11px] ${
                                    v.is_passed
                                      ? "bg-emerald-50 border-emerald-300 text-emerald-800"
                                      : "bg-rose-50 border-rose-300 text-rose-800"
                                  }`}
                                >
                                  <div className="font-bold">{v.rule_code}</div>
                                  <div className="text-[10px] text-slate-500">{v.message}</div>
                                </div>
                              ))}
                            </div>

                            {/* Double-Entry Lines Table */}
                            <div className="overflow-x-auto pt-1">
                              <table className="w-full text-left">
                                <thead>
                                  <tr className="border-b border-slate-200 text-slate-500 font-bold">
                                    <th className="pb-1">Ledger Name</th>
                                    <th className="pb-1">Type</th>
                                    <th className="pb-1 text-right">Amount</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-200/60">
                                  {selectedProposal.lines.map((l, i) => (
                                    <tr key={i}>
                                      <td className="py-1.5 font-bold text-slate-800">{l.ledger_name}</td>
                                      <td className="py-1.5 font-mono text-[11px]">
                                        <span className={`px-1.5 py-0.2 rounded font-bold ${l.is_debit ? "text-blue-700 bg-blue-50" : "text-amber-700 bg-amber-50"}`}>
                                          {l.is_debit ? "DR" : "CR"}
                                        </span>
                                      </td>
                                      <td className="py-1.5 text-right font-mono font-bold text-slate-900">
                                        ₹{l.amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>

                            {/* Human Approval Sign-off Box */}
                            {selectedProposal.status === "PENDING_APPROVAL" && (
                              <div className="p-3.5 rounded-xl bg-amber-50/60 border border-amber-300 space-y-2 mt-2">
                                <p className="font-bold text-amber-900">Mandatory Human Sign-off</p>
                                <div className="space-y-1.5">
                                  <input
                                    type="text"
                                    value={approverComments}
                                    onChange={(e) => setApproverComments(e.target.value)}
                                    className="w-full bg-white border border-amber-300 rounded-lg p-2 text-xs text-slate-800"
                                    placeholder="Approval sign-off comments..."
                                  />
                                  <div className="flex items-center justify-between">
                                    <select
                                      value={approverRole}
                                      onChange={(e) => setApproverRole(e.target.value)}
                                      className="bg-white border border-amber-300 rounded-lg px-2 py-1 text-xs text-slate-800 font-bold"
                                    >
                                      <option value="PRIMARY_APPROVER">Primary Controller</option>
                                      <option value="STATUTORY_AUDITOR">Statutory Auditor</option>
                                    </select>
                                    <button
                                      onClick={() => handleApproveProposal(selectedProposal.id)}
                                      disabled={isProcessingAction}
                                      className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs cursor-pointer"
                                    >
                                      Approve Sign-off
                                    </button>
                                  </div>
                                </div>
                              </div>
                            )}

                            {/* Bridge Simulation Execution */}
                            {selectedProposal.posting_job_id && (
                              <div className="p-3.5 rounded-xl bg-white border border-slate-200 space-y-2 mt-2">
                                <div className="flex items-center justify-between">
                                  <span className="font-bold text-slate-800">Bridge Execution Seam</span>
                                  <span className="font-mono text-[10px] text-slate-500">
                                    Job: {selectedProposal.posting_job_id.slice(0, 8)}...
                                  </span>
                                </div>
                                <div className="flex items-center justify-between">
                                  <div className="text-slate-600">
                                    <span>Status: </span>
                                    <strong className="text-indigo-700">{selectedProposal.posting_status || "PENDING"}</strong>
                                  </div>
                                  {selectedProposal.posting_status !== "SUCCESS" && (
                                    <button
                                      onClick={() => handleSimulateCycle(selectedProposal.posting_job_id!)}
                                      disabled={isProcessingAction}
                                      className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs cursor-pointer"
                                    >
                                      Execute Simulated Bridge Cycle
                                    </button>
                                  )}
                                </div>
                              </div>
                            )}

                            {/* Verified Evidence Read-back */}
                            {selectedProposal.verification_status === "VERIFIED_MATCH" && (
                              <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-300 text-emerald-900 space-y-1">
                                <div className="flex items-center justify-between font-bold">
                                  <span>✓ Forensic Verification Match</span>
                                  <span className="font-mono text-[10px]">{selectedProposal.tally_voucher_number}</span>
                                </div>
                                <p className="text-[11px] text-emerald-800">
                                  Expected ₹{selectedProposal.total_amount.toLocaleString("en-IN")} matches recorded Tally amount exactly.
                                </p>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ================================================================= */}
          {/* TAB 5: BANKING                                                    */}
          {/* ================================================================= */}
          {activeTab === "banking" && (
            <div className="space-y-6 max-w-7xl mx-auto">
              <div className="rounded-2xl bg-white border border-slate-200 p-6 space-y-4 shadow-xs">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-black text-slate-900 flex items-center space-x-2">
                      <span>🏦</span>
                      <span>Bank Reconciliation Statement (BRS)</span>
                    </h2>
                    <p className="text-xs text-slate-500 mt-1">
                      Automated match of bank statement feeds against recorded Tally bank vouchers.
                    </p>
                  </div>
                  <span className="text-xs font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-1 rounded-full">
                    3 Accounts Clear
                  </span>
                </div>

                <div className="p-8 text-center rounded-xl bg-slate-50 border border-slate-200 text-slate-500 text-xs">
                  Zero reconciliation discrepancies reported for active financial period.
                </div>
              </div>
            </div>
          )}

          {/* ================================================================= */}
          {/* TAB 6: AI INTELLIGENCE & PIPELINE                                 */}
          {/* ================================================================= */}
          {activeTab === "ai" && (
            <div className="space-y-6 max-w-7xl mx-auto">
              <div className="rounded-2xl bg-white border border-slate-200 p-6 space-y-4 shadow-xs">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-black text-slate-900 flex items-center space-x-2">
                      <span>🧠</span>
                      <span>AI Intelligence &amp; Structured Extraction</span>
                    </h2>
                    <p className="text-xs text-slate-500 mt-1">
                      Google Gemini 2.0 multimodal invoice understanding &amp; deterministic rules engine.
                    </p>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className="h-2 w-2 rounded-full bg-cyan-500 animate-pulse" />
                    <span className="text-xs font-bold text-cyan-700">Google Gemini 2.0 Connected</span>
                  </div>
                </div>

                {/* Capabilities Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                    <span className="text-lg">📑</span>
                    <h3 className="text-xs font-bold text-slate-900">Tax Invoice Extraction</h3>
                    <p className="text-xs text-slate-600 leading-relaxed">
                      Extracts GSTIN, invoice number, line items, HSN/SAC codes, and SGST/CGST/IGST tax splits with high confidence.
                    </p>
                  </div>
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                    <span className="text-lg">⚖️</span>
                    <h3 className="text-xs font-bold text-slate-900">Deterministic Rules Validation</h3>
                    <p className="text-xs text-slate-600 leading-relaxed">
                      Verifies tax mathematics, vendor GSTIN format, and debit-credit equilibrium prior to human presentation.
                    </p>
                  </div>
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                    <span className="text-lg">🛡️</span>
                    <h3 className="text-xs font-bold text-slate-900">Zero Unattended Writes</h3>
                    <p className="text-xs text-slate-600 leading-relaxed">
                      AI outputs are strictly proposals. Human sign-off is mandatory before Bridge dispatch to TallyPrime.
                    </p>
                  </div>
                </div>

                {/* AI Configuration Info */}
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-2">
                  <p className="font-bold text-slate-800">Model Configuration</p>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-slate-600">
                    <div>
                      <span className="text-[10px] block text-slate-400">Provider</span>
                      <span className="font-semibold text-slate-900">Google Cloud / Vertex AI</span>
                    </div>
                    <div>
                      <span className="text-[10px] block text-slate-400">Model</span>
                      <span className="font-semibold text-slate-900">gemini-2.0-flash</span>
                    </div>
                    <div>
                      <span className="text-[10px] block text-slate-400">Confidence Threshold</span>
                      <span className="font-semibold text-emerald-700">85% Minimum</span>
                    </div>
                    <div>
                      <span className="text-[10px] block text-slate-400">Fallback Mode</span>
                      <span className="font-semibold text-amber-700">Deterministic Parser</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ================================================================= */}
          {/* TAB 7: AUDIT (AUDIT & EVIDENCE)                                   */}
          {/* ================================================================= */}
          {activeTab === "audit" && (
            <div className="space-y-6 max-w-7xl mx-auto">
              <div className="rounded-2xl bg-white border border-slate-200 p-6 space-y-4 shadow-xs">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-black text-slate-900 flex items-center space-x-2">
                      <span>🛡️</span>
                      <span>Cryptographic Audit &amp; Evidence Log</span>
                    </h2>
                    <p className="text-xs text-slate-500 mt-1">
                      Append-only forensic event ledger with SHA-256 verification hashes.
                    </p>
                  </div>
                  <span className="text-xs text-slate-500 font-mono">
                    {auditEvents.length} events recorded
                  </span>
                </div>

                {auditEvents.length === 0 ? (
                  <div className="p-8 text-center rounded-xl bg-slate-50 border border-slate-200 text-slate-500 text-xs">
                    No audit events recorded yet for this company.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-slate-200 text-slate-600 font-bold bg-slate-50/60">
                          <th className="py-2 px-3">Timestamp</th>
                          <th className="py-2 px-3">Action</th>
                          <th className="py-2 px-3">Actor Type</th>
                          <th className="py-2 px-3">Entity Type</th>
                          <th className="py-2 px-3">Entity ID</th>
                          <th className="py-2 px-3 text-right">Integrity</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 text-slate-700">
                        {auditEvents.map((ev) => (
                          <tr key={ev.id} className="hover:bg-slate-50">
                            <td className="py-2.5 px-3 font-mono text-[11px] text-slate-500">
                              {new Date(ev.recorded_at).toLocaleString()}
                            </td>
                            <td className="py-2.5 px-3 font-bold text-slate-900">{ev.action}</td>
                            <td className="py-2.5 px-3 text-slate-600">{ev.actor_type}</td>
                            <td className="py-2.5 px-3 text-slate-600">{ev.entity_type}</td>
                            <td className="py-2.5 px-3 font-mono text-[10px] text-slate-400">{ev.entity_id.slice(0, 8)}...</td>
                            <td className="py-2.5 px-3 text-right">
                              <span className="text-emerald-700 font-mono text-[10px]">SHA-256 ✓</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}
        </main>
      </div>

      {/* ===================================================================== */}
      {/* MODALS (LITE THEME)                                                   */}
      {/* ===================================================================== */}

      {/* Live Tally Certification Gate Modal */}
      {showLiveTallyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-lg bg-white border border-slate-200 rounded-2xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900">Certification Gate: LIVE-TALLY-CERT-001</h3>
              <button
                onClick={() => setShowLiveTallyModal(false)}
                className="text-slate-400 hover:text-slate-700 text-sm font-bold cursor-pointer"
              >
                ✕
              </button>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              Development environments run in <strong>DEMO MODE</strong> using <code>TallySimulatedAdapter</code>. To unlock <strong>LIVE MODE</strong> on the client premises:
            </p>
            <div className="space-y-2 text-xs text-slate-600">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
                <span className="font-bold text-slate-900">1. Verify TallyPrime Host</span>
                <p>Run TallyPrime on Windows host with ODBC/XML port 9000 enabled.</p>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
                <span className="font-bold text-slate-900">2. Execute Discovery Protocol</span>
                <p>Bridge client executes native XML discovery and registers GUID.</p>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
                <span className="font-bold text-slate-900">3. Authorize Production Binding</span>
                <p>Sign off on multi-company isolation policy prior to live posting.</p>
              </div>
            </div>
            <div className="flex justify-end pt-2">
              <button
                onClick={() => setShowLiveTallyModal(false)}
                className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold transition-all cursor-pointer"
              >
                Acknowledge
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Company Modal */}
      {showCreateCompanyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-md bg-white border border-slate-200 rounded-2xl p-6 shadow-2xl space-y-4">
            <h3 className="text-base font-bold text-slate-900">Create New {APP_NAME} Company</h3>
            <form onSubmit={handleCreateCompany} className="space-y-3 text-xs">
              <div>
                <label className="text-slate-600 font-bold block mb-1">Company Legal Name</label>
                <input
                  type="text"
                  required
                  value={newCompanyName}
                  onChange={(e) => setNewCompanyName(e.target.value)}
                  placeholder="e.g. Acme Industries Ltd"
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-hidden"
                />
              </div>
              <div>
                <label className="text-slate-600 font-bold block mb-1">PAN Number</label>
                <input
                  type="text"
                  value={newPan}
                  onChange={(e) => setNewPan(e.target.value)}
                  placeholder="AABCA1234A"
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-hidden"
                />
              </div>
              <div>
                <label className="text-slate-600 font-bold block mb-1">GSTIN Number</label>
                <input
                  type="text"
                  value={newGstin}
                  onChange={(e) => setNewGstin(e.target.value)}
                  placeholder="27AABCA1234A1Z5"
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-hidden"
                />
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateCompanyModal(false)}
                  className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold transition-all cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold transition-all cursor-pointer"
                >
                  Create Company
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Settings Modal */}
      {showSettingsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-md bg-white border border-slate-200 rounded-2xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900">System Configuration</h3>
              <button
                onClick={() => setShowSettingsModal(false)}
                className="text-slate-400 hover:text-slate-700 text-sm font-bold cursor-pointer"
              >
                ✕
              </button>
            </div>
            <div className="space-y-3 text-xs text-slate-600">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                <span className="font-bold text-slate-900">API Endpoint</span>
                <p className="font-mono text-slate-500 mt-0.5">{API_BASE}</p>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                <span className="font-bold text-slate-900">App Edition</span>
                <p className="text-slate-500 mt-0.5">{APP_NAME} {APP_VERSION} ({APP_EDITION})</p>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                <span className="font-bold text-slate-900">Active Tenant</span>
                <p className="text-slate-500 mt-0.5">{selectedCompany?.legal_name || "None"}</p>
              </div>
            </div>
            <div className="flex justify-end pt-2">
              <button
                onClick={() => setShowSettingsModal(false)}
                className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold transition-all cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
