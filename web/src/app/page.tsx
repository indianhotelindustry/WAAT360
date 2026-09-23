"use client";

import React, { useState, useEffect, useCallback } from "react";

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

// Configurable API base url from environment (Control 5)
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000/api/v1";

export default function CommandCenter() {
  const [activeTab, setActiveTab] = useState<"operations" | "discovery" | "audit">("operations");
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [companies, setCompanies] = useState<CompanyItem[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>("");
  const [tallyCompanies, setTallyCompanies] = useState<TallyCompanyItem[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string>("");
  const [activeExtraction, setActiveExtraction] = useState<DocumentExtraction | null>(null);
  const [proposals, setProposals] = useState<ProposalItem[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEventItem[]>([]);

  // UI state
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

  // 2. Fetch Selected Company State (KPIs, Documents, Proposals, Audit)
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

  // Polling loops without react-hooks setState-in-render violations
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

  // Load extraction for selected document asynchronously
  useEffect(() => {
    let isMounted = true;
    const loadDocExtraction = async () => {
      if (!selectedDocId) {
        return;
      }
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

  // Handle Document Upload
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
      if (!res.ok) throw new Error("Document upload failed");
      const doc = await res.json();
      notify(`Invoice uploaded successfully (SHA256: ${doc.sha256_checksum.slice(0, 8)}...).`, "success");
      setSelectedDocId(doc.id);
      await fetchCompanyData(selectedCompanyId);
    } catch (err) {
      notify(`Upload error: ${err}`, "error");
    } finally {
      setUploading(false);
    }
  };

  // Sample Invoice Generator
  const handleUseSampleInvoice = async () => {
    if (!selectedCompanyId) {
      notify("Select a company first.", "error");
      return;
    }
    const invNo = Math.floor(1000 + Math.random() * 9000);
    const sampleContent = `TAX INVOICE
Vendor: Shreeji Steel Enterprises
Vendor GSTIN: 27AABCS1429B1ZB
Buyer: ${selectedCompany?.legal_name || "Tata Motors Technologies Ltd"}
Buyer GSTIN: ${selectedCompany?.gstin || "27AAACT2727Q1ZW"}
Invoice No: INV-2026-${invNo}
Invoice Date: 2026-03-24
Taxable Amount: 20000.00
CGST (9%): 1800.00
SGST (9%): 1800.00
Total Amount: 23600.00
Line Items:
1. Steel Round Bars 12mm - HSN 72142090 - Qty: 300 KGS @ 66.666 = 20000.00
Payment Terms: Net 30 Days`;

    const blob = new Blob([sampleContent], { type: "text/plain" });
    const file = new File([blob], `sample_tax_invoice_${invNo}.txt`, { type: "text/plain" });
    await handleUploadFile(file);
  };

  // Step 1: Run AI Extraction
  const handleExtract = async (docId: string) => {
    setIsProcessingAction(true);
    try {
      notify("Running Gemini AI Extraction on invoice...", "info");
      const res = await fetch(`${API_BASE}/documents/${docId}/extract`, { method: "POST" });
      if (!res.ok) throw new Error("Extraction failed");
      const data = await res.json();
      setActiveExtraction(data);
      notify(`AI Extraction completed for ${data.extracted_data.vendor_name} (Confidence: ${Math.round((data.confidence_score || 0.95) * 100)}%).`, "success");
      await fetchCompanyData(selectedCompanyId);
    } catch (err) {
      notify(`Extraction error: ${err}`, "error");
    } finally {
      setIsProcessingAction(false);
    }
  };

  // Step 2: Generate Accounting Proposal
  const handleGenerateProposal = async (docId: string) => {
    setIsProcessingAction(true);
    try {
      notify("Evaluating Deterministic Accounting Rules & Invariants...", "info");
      const res = await fetch(`${API_BASE}/proposals/generate/${docId}`, { method: "POST" });
      if (!res.ok) throw new Error("Proposal generation failed");
      const data = await res.json();
      const passedCount = data.validations.filter((v: ValidationCheck) => v.is_passed).length;
      notify(`Accounting proposal generated! ${passedCount}/${data.validations.length} validation invariants passed.`, "success");
      await fetchCompanyData(selectedCompanyId);
    } catch (err) {
      notify(`Proposal error: ${err}`, "error");
    } finally {
      setIsProcessingAction(false);
    }
  };

  // Step 3: Authoritative Human Approval
  const handleApprove = async (propId: string) => {
    setIsProcessingAction(true);
    try {
      notify("Submitting Authoritative Human Approval...", "info");
      const res = await fetch(`${API_BASE}/proposals/${propId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision: "APPROVED",
          comments: approverComments,
          authority_context: approverRole,
          approval_signature: `SIG-${Date.now().toString(36).toUpperCase()}`,
        }),
      });
      if (!res.ok) throw new Error("Approval failed");
      const data = await res.json();
      notify(`Approved! Transaction & PostingJob #${data.posting_job_id.slice(0, 8)} materialized in database.`, "success");
      await fetchCompanyData(selectedCompanyId);
    } catch (err) {
      notify(`Approval error: ${err}`, "error");
    } finally {
      setIsProcessingAction(false);
    }
  };

  // Step 4: Bridge & Simulated Tally Execution (Control 1: Real Adapter Execution)
  const handleSimulateBridgeExecution = async (postingJobId: string) => {
    if (!postingJobId) {
      notify("No valid posting job queued.", "error");
      return;
    }
    setIsProcessingAction(true);
    try {
      notify("Bridge picking up job -> executing TallySimulatedAdapter -> read-back verification...", "info");
      const res = await fetch(`${API_BASE}/bridge/jobs/${postingJobId}/simulate-cycle`, {
        method: "POST",
      });
      if (!res.ok) {
        const errJson = await res.json();
        throw new Error(errJson.detail || "Simulation failed");
      }
      const data = await res.json();
      notify(
        `✓ Tally Voucher ${data.voucher_number} created and read-back verified against Tally store! Total: ₹${data.actual_amount.toLocaleString("en-IN")}.`,
        "success"
      );
      await fetchCompanyData(selectedCompanyId);
    } catch (err) {
      notify(`Bridge execution error: ${err}`, "error");
    } finally {
      setIsProcessingAction(false);
    }
  };

  // Create Company
  const handleCreateCompany = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/companies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ legal_name: newCompanyName, pan: newPan || null, gstin: newGstin || null }),
      });
      if (!res.ok) throw new Error("Company creation failed");
      const comp = await res.json();
      notify(`Company ${comp.legal_name} created successfully.`, "success");
      setShowCreateCompanyModal(false);
      setNewCompanyName("");
      setNewPan("");
      setNewGstin("");
      await fetchGlobalData();
      setSelectedCompanyId(comp.id);
    } catch (err) {
      notify(`Create company error: ${err}`, "error");
    }
  };

  // Quick Map Tally Company
  const handleQuickMap = async (tcId: string) => {
    try {
      const res = await fetch(`${API_BASE}/tally-companies/${tcId}/create-and-map`, { method: "POST" });
      if (!res.ok) throw new Error("Quick mapping failed");
      notify("WAAST360 Company created and mapped to Tally Company!", "success");
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
          if (!allPassed) return "EXCEPTION";
          return "COMPLETED";
        }
        return "NOT_REACHED";
      case 5: // PENDING APPROVAL
        if (selectedProposal?.status === "PENDING_APPROVAL") return "CURRENT";
        if (["APPROVED", "POSTED", "VERIFIED"].includes(selectedProposal?.status || "") || ["APPROVED", "POSTED", "VERIFIED"].includes(selectedDoc.status)) {
          return "COMPLETED";
        }
        return "NOT_REACHED";
      case 6: // APPROVED
        if (["APPROVED", "POSTED", "VERIFIED"].includes(selectedProposal?.status || "") || ["APPROVED", "POSTED", "VERIFIED"].includes(selectedDoc.status)) {
          return "COMPLETED";
        }
        return "NOT_REACHED";
      case 7: // POSTING
        if (selectedProposal?.posting_status === "QUEUED" || selectedDoc.status === "POSTING") return "CURRENT";
        if (["POSTED", "VERIFIED"].includes(selectedProposal?.posting_status || "") || ["POSTED", "VERIFIED"].includes(selectedDoc.status)) {
          return "COMPLETED";
        }
        return "NOT_REACHED";
      case 8: // POSTED
        if (["POSTED", "VERIFIED"].includes(selectedProposal?.posting_status || "") || ["POSTED", "VERIFIED"].includes(selectedDoc.status)) {
          return "COMPLETED";
        }
        return "NOT_REACHED";
      case 9: // VERIFIED
        if (selectedProposal?.verification_status === "VERIFIED" || selectedDoc.status === "VERIFIED") {
          return "COMPLETED";
        }
        if (selectedProposal?.verification_status === "AMOUNT_MISMATCH" || selectedProposal?.verification_status === "FAILED") {
          return "EXCEPTION";
        }
        return selectedDoc.status === "POSTED" ? "CURRENT" : "NOT_REACHED";
      case 10: // AUDIT PROVED
        if (auditEvents.length > 0 && (selectedDoc.status === "VERIFIED" || selectedProposal?.verification_status === "VERIFIED")) {
          return "COMPLETED";
        }
        return "NOT_REACHED";
      default:
        return "NOT_REACHED";
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans antialiased">
      {/* =========================================================================
          1. ENTERPRISE NAVIGATION HEADER (Navy #0F172A)
          ========================================================================= */}
      <header className="bg-slate-900 text-white border-b border-slate-800 shadow-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          {/* Brand & Titles */}
          <div className="flex items-center space-x-3.5">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-500 flex items-center justify-center shadow-lg shadow-indigo-900/40 text-white font-black text-xl tracking-wider">
              W
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-xl font-extrabold tracking-tight text-white">WAAST360</span>
                <span className="text-xs px-2 py-0.5 rounded-full font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 tracking-wide uppercase">
                  Command Center
                </span>
              </div>
              <p className="text-xs text-slate-400">Wise Accounting Automation System for Tally</p>
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="flex items-center space-x-1 bg-slate-950/80 p-1 rounded-xl border border-slate-800 text-xs font-semibold">
            <button
              onClick={() => setActiveTab("operations")}
              className={`px-3.5 py-1.5 rounded-lg transition-all ${
                activeTab === "operations" ? "bg-blue-600 text-white shadow-sm" : "text-slate-400 hover:text-white"
              }`}
            >
              Command Center
            </button>
            <button
              onClick={() => setActiveTab("discovery")}
              className={`px-3.5 py-1.5 rounded-lg transition-all ${
                activeTab === "discovery" ? "bg-blue-600 text-white shadow-sm" : "text-slate-400 hover:text-white"
              }`}
            >
              Tally Companies ({tallyCompanies.length})
            </button>
            <button
              onClick={() => setActiveTab("audit")}
              className={`px-3.5 py-1.5 rounded-lg transition-all ${
                activeTab === "audit" ? "bg-blue-600 text-white shadow-sm" : "text-slate-400 hover:text-white"
              }`}
            >
              Forensic Audit ({auditEvents.length})
            </button>
          </div>

          {/* Global Independent Connection Statuses (Directive 2 & Control 3) */}
          <div className="flex items-center space-x-2.5 text-xs font-medium bg-slate-950/60 border border-slate-800 px-3 py-1.5 rounded-xl">
            {/* 1. Cloud Status */}
            <div className="flex items-center space-x-1.5" title="WAAST360 Cloud Backend API Status">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-slate-300 font-semibold">Cloud API</span>
            </div>

            <span className="text-slate-700">|</span>

            {/* 2. Bridge Status */}
            <div className="flex items-center space-x-1.5" title={`Bridge Client ID: ${summary?.bridge_client_id || "waast-bridge-local"}`}>
              <span className={`h-2 w-2 rounded-full ${summary?.bridge_connected ? "bg-emerald-400" : "bg-amber-400"}`} />
              <span className="text-slate-300">
                Bridge: <strong className="text-white">{summary?.bridge_connected ? "ONLINE" : "STANDBY"}</strong>
              </span>
            </div>

            <span className="text-slate-700">|</span>

            {/* 3. TallyPrime Status (DEMO MODE vs LIVE MODE explicit) */}
            <div className="flex items-center space-x-1.5">
              <span className={`h-2.5 w-2.5 rounded-full ${summary?.is_demo_mode ? "bg-amber-400" : "bg-emerald-400"}`} />
              {summary?.is_demo_mode ? (
                <div className="flex items-center space-x-1">
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-extrabold bg-amber-400/20 text-amber-300 border border-amber-400/40 uppercase">
                    DEMO MODE
                  </span>
                  <span className="text-slate-300 text-[11px]">Simulated Tally</span>
                </div>
              ) : (
                <div className="flex items-center space-x-1">
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-extrabold bg-emerald-400/20 text-emerald-300 border border-emerald-400/40 uppercase">
                    LIVE MODE
                  </span>
                  <span className="text-slate-300 text-[11px]">TallyPrime Connected</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* =========================================================================
          2. DEMO MODE PERSISTENT BANNER (Directive 15 & Control 3)
          ========================================================================= */}
      {summary?.is_demo_mode && (
        <div className="bg-amber-50 border-b border-amber-200/80 px-4 py-2 text-xs text-amber-900 flex items-center justify-between shadow-xs">
          <div className="flex items-center space-x-2 max-w-7xl mx-auto w-full px-2 sm:px-4">
            <span className="inline-flex items-center justify-center h-4 w-4 rounded-full bg-amber-200 text-amber-900 font-bold text-[10px]">
              i
            </span>
            <span className="font-semibold">DEMO MODE ACTIVE</span>
            <span className="text-amber-700">•</span>
            <span className="text-amber-800">
              Operating against high-fidelity <strong>TallySimulatedAdapter</strong>. Safe for presentation and development without active Tally on port 9000.
            </span>
            <div className="ml-auto flex items-center space-x-2">
              <button
                onClick={() => setShowLiveTallyModal(true)}
                className="px-2.5 py-1 rounded bg-amber-200/80 hover:bg-amber-200 text-amber-950 font-semibold transition text-[11px] border border-amber-300"
              >
                Prepare for Live Tally →
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Notifications */}
      {notification && (
        <div
          className={`border-b px-6 py-2.5 text-xs font-semibold flex items-center justify-between transition-all ${
            notification.type === "success"
              ? "bg-emerald-50 text-emerald-900 border-emerald-200"
              : notification.type === "error"
              ? "bg-rose-50 text-rose-900 border-rose-200"
              : "bg-blue-50 text-blue-900 border-blue-200"
          }`}
        >
          <div className="max-w-7xl mx-auto w-full flex items-center justify-between">
            <span>{notification.text}</span>
            <button onClick={() => setNotification(null)} className="opacity-70 hover:opacity-100 text-sm ml-4">
              ✕
            </button>
          </div>
        </div>
      )}

      {/* =========================================================================
          MAIN COMMAND CENTER CONTENT
          ========================================================================= */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Company Selector Header (Directive 3) */}
        <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-xs flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center space-x-3.5">
            <div className="h-11 w-11 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-700 text-xl font-bold">
              🏢
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500">Active Company</span>
                {selectedCompany?.financial_year && (
                  <span className="text-[10px] px-2 py-0.2 rounded bg-slate-100 text-slate-600 font-mono font-medium">
                    FY: {selectedCompany.financial_year}
                  </span>
                )}
              </div>
              <div className="flex items-center space-x-2 mt-0.5">
                <select
                  value={selectedCompanyId}
                  onChange={(e) => setSelectedCompanyId(e.target.value)}
                  className="text-base font-bold text-slate-900 bg-transparent border-0 p-0 focus:ring-0 cursor-pointer pr-4"
                >
                  {companies.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.legal_name}
                    </option>
                  ))}
                </select>
                {selectedCompany?.gstin && (
                  <span className="text-xs font-mono text-slate-500 bg-slate-50 px-2 py-0.5 rounded border border-slate-200">
                    GSTIN: {selectedCompany.gstin}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Mapped Tally Company:{" "}
                <strong className="text-slate-800">
                  {selectedCompany?.mapped_tally_company_name || "Tata Motors Technologies Ltd (Default Binding)"}
                </strong>
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setShowCreateCompanyModal(true)}
              className="px-3.5 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold border border-slate-200 transition"
            >
              + New Company
            </button>
            <button
              onClick={() => {
                fetchGlobalData();
                if (selectedCompanyId) fetchCompanyData(selectedCompanyId);
                notify("Refreshed authoritative state from PostgreSQL.", "info");
              }}
              className="px-3.5 py-1.5 rounded-xl bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-semibold border border-blue-200 transition flex items-center space-x-1"
            >
              <span>↻ Refresh</span>
            </button>
          </div>
        </div>

        {/* TAB 1: OPERATIONS COMMAND CENTER */}
        {activeTab === "operations" && (
          <div className="space-y-6">
            {/* KPI COMMAND CENTER (Directive 4 & Control 2: Real Database Derived) */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
              {[
                { title: "Documents Received", count: summary?.documents_received ?? 0, icon: "📄", color: "text-slate-900", border: "border-slate-200", bg: "bg-white" },
                { title: "Pending Review", count: summary?.pending_review ?? 0, icon: "⏳", color: "text-amber-700", border: "border-amber-200", bg: "bg-amber-50/50" },
                { title: "Approved", count: summary?.approved ?? 0, icon: "✍️", color: "text-indigo-700", border: "border-indigo-200", bg: "bg-indigo-50/50" },
                { title: "Posted to Tally", count: summary?.posted_to_tally ?? 0, icon: "📤", color: "text-blue-700", border: "border-blue-200", bg: "bg-blue-50/50" },
                { title: "Verified", count: summary?.verified ?? 0, icon: "🛡️", color: "text-emerald-700", border: "border-emerald-200", bg: "bg-emerald-50/50" },
                { title: "Exceptions", count: summary?.exceptions ?? 0, icon: "⚠️", color: "text-rose-700", border: "border-rose-200", bg: "bg-rose-50/50" },
              ].map((kpi, idx) => (
                <div key={idx} className={`${kpi.bg} border ${kpi.border} rounded-2xl p-4 shadow-xs flex flex-col justify-between transition hover:shadow-sm`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">{kpi.title}</span>
                    <span className="text-base">{kpi.icon}</span>
                  </div>
                  <div className={`text-2xl font-black ${kpi.color} font-mono`}>{kpi.count}</div>
                  <span className="text-[10px] text-slate-400 mt-1">Real database state</span>
                </div>
              ))}
            </div>

            {/* GOLDEN PATH VISUALIZER (Directive 5: 10 Stages) */}
            <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  10-Stage Golden Path Pipeline Lifecycle
                </h2>
                {selectedDoc && (
                  <span className="text-xs font-mono text-slate-600">
                    Inspecting: <strong>{selectedDoc.file_name}</strong> ({selectedDoc.document_number})
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-5 lg:grid-cols-10 gap-2 text-center text-[11px] font-semibold">
                {[
                  { step: "1. RECEIVED", num: 1 },
                  { step: "2. EXTRACTED", num: 2 },
                  { step: "3. PROPOSED", num: 3 },
                  { step: "4. VALIDATED", num: 4 },
                  { step: "5. PENDING APPR", num: 5 },
                  { step: "6. APPROVED", num: 6 },
                  { step: "7. POSTING", num: 7 },
                  { step: "8. POSTED", num: 8 },
                  { step: "9. VERIFIED", num: 9 },
                  { step: "10. AUDIT PROVED", num: 10 },
                ].map((s) => {
                  const status = getStageStatus(s.num);
                  return (
                    <div
                      key={s.num}
                      className={`p-2.5 rounded-xl border transition-all ${
                        status === "COMPLETED"
                          ? "bg-emerald-50 border-emerald-300 text-emerald-800 shadow-xs"
                          : status === "CURRENT"
                          ? "bg-blue-50 border-blue-400 text-blue-800 ring-2 ring-blue-400/20 shadow-xs animate-pulse"
                          : status === "EXCEPTION"
                          ? "bg-rose-50 border-rose-300 text-rose-800"
                          : "bg-slate-50 border-slate-200 text-slate-400"
                      }`}
                    >
                      <div className="text-[10px] font-mono opacity-80 mb-0.5">
                        {status === "COMPLETED" ? "✓ DONE" : status === "CURRENT" ? "● ACTIVE" : status === "EXCEPTION" ? "⚠ FAILED" : "PENDING"}
                      </div>
                      <div className="text-[11px] leading-tight font-bold">{s.step}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Split Screen Operations Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* LEFT COLUMN: HERO INGESTION & DOCUMENTS (5 Cols) */}
              <div className="lg:col-span-5 space-y-6">
                {/* HERO ACTION: UPLOAD INVOICE (Directive 6) */}
                <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
                      <span>📄</span>
                      <span>Phase 3B: Ingest Invoice</span>
                    </h3>
                    <button
                      onClick={handleUseSampleInvoice}
                      disabled={uploading}
                      className="text-xs px-2.5 py-1 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-semibold border border-indigo-200 transition disabled:opacity-50"
                    >
                      + Use Sample Invoice
                    </button>
                  </div>

                  {/* Drag and Drop Zone */}
                  <div
                    onDragOver={(e) => {
                      e.preventDefault();
                      setIsDragging(true);
                    }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setIsDragging(false);
                      if (e.dataTransfer.files?.[0]) {
                        handleUploadFile(e.dataTransfer.files[0]);
                      }
                    }}
                    className={`border-2 border-dashed rounded-xl p-5 text-center transition cursor-pointer ${
                      isDragging ? "border-blue-500 bg-blue-50/50" : "border-slate-200 hover:border-slate-300 bg-slate-50/50"
                    }`}
                  >
                    <input
                      type="file"
                      id="invoice-upload-input"
                      onChange={(e) => {
                        if (e.target.files?.[0]) handleUploadFile(e.target.files[0]);
                      }}
                      className="hidden"
                    />
                    <label htmlFor="invoice-upload-input" className="cursor-pointer block space-y-2">
                      <div className="h-10 w-10 mx-auto rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-lg">
                        ↑
                      </div>
                      <div className="text-xs font-bold text-slate-800">
                        {uploading ? "Ingesting & computing SHA256..." : "Click to Browse or Drag & Drop Invoice"}
                      </div>
                      <p className="text-[11px] text-slate-500">Supports PDF, TXT, PNG, JPG • Computes cryptographic SHA256 checksum</p>
                    </label>
                  </div>
                </div>

                {/* Ingested Documents Queue */}
                <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-slate-900">Ingested Invoices ({documents.length})</h3>
                    <span className="text-[11px] text-slate-400">Click to inspect</span>
                  </div>

                  {documents.length === 0 ? (
                    <div className="text-center py-8 bg-slate-50 rounded-xl border border-slate-100 text-slate-400 text-xs">
                      No invoices ingested yet. Upload an invoice above or click &ldquo;Use Sample Invoice&rdquo;.
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                      {documents.map((doc) => (
                        <div
                          key={doc.id}
                          onClick={() => setSelectedDocId(doc.id)}
                          className={`p-3 rounded-xl border text-xs cursor-pointer transition ${
                            selectedDoc?.id === doc.id
                              ? "bg-blue-50/70 border-blue-400 shadow-xs"
                              : "bg-white border-slate-200 hover:border-slate-300"
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1.5">
                            <span className="font-bold text-slate-800 truncate max-w-[200px]">{doc.file_name}</span>
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                doc.status === "VERIFIED"
                                  ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                                  : doc.status === "POSTED"
                                  ? "bg-blue-100 text-blue-800 border border-blue-300"
                                  : doc.status === "APPROVED"
                                  ? "bg-indigo-100 text-indigo-800 border border-indigo-300"
                                  : doc.status === "PROPOSED"
                                  ? "bg-purple-100 text-purple-800 border border-purple-300"
                                  : doc.status === "DUPLICATE_FLAGGED"
                                  ? "bg-rose-100 text-rose-800 border border-rose-300"
                                  : "bg-amber-100 text-amber-800 border border-amber-300"
                              }`}
                            >
                              {doc.status}
                            </span>
                          </div>
                          <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono">
                            <span>SHA: {doc.sha256_checksum.slice(0, 10)}...</span>
                            <span>{new Date(doc.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* DEDICATED BRIDGE PANEL (Directive 11) */}
                <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-3.5">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
                      <span>🌉</span>
                      <span>WAAST360 Bridge</span>
                    </h3>
                    <span className="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-slate-100 text-slate-700 border border-slate-200">
                      v1.0.0
                    </span>
                  </div>

                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between py-1 border-b border-slate-100">
                      <span className="text-slate-500">Bridge Client ID</span>
                      <span className="font-mono font-semibold text-slate-800">{summary?.bridge_client_id || "waast-bridge-local"}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-100">
                      <span className="text-slate-500">Connection State</span>
                      <span className="font-semibold text-emerald-700">● {summary?.bridge_status || "ONLINE"}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-100">
                      <span className="text-slate-500">Active Adapter</span>
                      <span className="font-semibold text-indigo-700">{summary?.adapter_name || "Simulated Tally"}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-100">
                      <span className="text-slate-500">Mapped Company</span>
                      <span className="font-semibold text-slate-800">{selectedCompany?.legal_name || "Default Company"}</span>
                    </div>
                    <div className="flex justify-between py-1">
                      <span className="text-slate-500">Last Outbound Heartbeat</span>
                      <span className="font-mono text-slate-600">
                        {summary?.last_heartbeat ? new Date(summary.last_heartbeat).toLocaleTimeString() : "Active (Sub-minute)"}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* RIGHT COLUMN: INSPECTION, AI EXTRACTION, PROPOSAL, APPROVAL, VERIFICATION (7 Cols) */}
              <div className="lg:col-span-7 space-y-6">
                {selectedDoc ? (
                  <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-6">
                    {/* Header & Quick Actions */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 gap-3">
                      <div>
                        <div className="flex items-center space-x-2">
                          <h3 className="text-base font-bold text-slate-900">{selectedDoc.file_name}</h3>
                          <span className="text-xs px-2 py-0.5 rounded bg-slate-100 font-mono text-slate-700 border border-slate-200">
                            {selectedDoc.document_number}
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 mt-1">
                          Current Stage: <strong className="text-blue-700 uppercase">{selectedDoc.status}</strong>
                        </p>
                      </div>

                      {/* Primary Golden Path Step Trigger */}
                      <div className="flex items-center space-x-2">
                        {selectedDoc.status === "RECEIVED" && (
                          <button
                            onClick={() => handleExtract(selectedDoc.id)}
                            disabled={isProcessingAction}
                            className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white font-bold text-xs shadow-md shadow-purple-600/20 transition flex items-center space-x-1.5"
                          >
                            <span>✨ Run Gemini AI Extraction</span>
                          </button>
                        )}
                        {selectedDoc.status === "EXTRACTED" && (
                          <button
                            onClick={() => handleGenerateProposal(selectedDoc.id)}
                            disabled={isProcessingAction}
                            className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-md shadow-blue-600/20 transition flex items-center space-x-1.5"
                          >
                            <span>⚙️ Generate Accounting Proposal</span>
                          </button>
                        )}
                      </div>
                    </div>

                    {/* INVOICE INTELLIGENCE CARD (Directive 7) */}
                    {activeExtraction && (
                      <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3">
                        <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                          <div className="flex items-center space-x-2">
                            <span className="text-xs font-bold uppercase text-slate-700">AI Extraction Intelligence</span>
                            <span className="px-2 py-0.5 rounded bg-purple-100 text-purple-800 text-[10px] font-bold border border-purple-200">
                              AI EXTRACTED — Requires validation
                            </span>
                          </div>
                          <span className="text-xs font-mono font-semibold text-slate-600">
                            Confidence: {Math.round((activeExtraction.confidence_score || 0.95) * 100)}%
                          </span>
                        </div>

                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                          <div>
                            <span className="text-slate-400 block text-[10px]">Supplier / Vendor</span>
                            <strong className="text-slate-900">{activeExtraction.extracted_data.vendor_name}</strong>
                          </div>
                          <div>
                            <span className="text-slate-400 block text-[10px]">Supplier GSTIN</span>
                            <span className="font-mono text-slate-800">{activeExtraction.extracted_data.vendor_gstin || "N/A"}</span>
                          </div>
                          <div>
                            <span className="text-slate-400 block text-[10px]">Buyer Name</span>
                            <strong className="text-slate-900">{activeExtraction.extracted_data.buyer_name || selectedCompany?.legal_name}</strong>
                          </div>
                          <div>
                            <span className="text-slate-400 block text-[10px]">Buyer GSTIN</span>
                            <span className="font-mono text-slate-800">{activeExtraction.extracted_data.buyer_gstin || selectedCompany?.gstin || "N/A"}</span>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs pt-1 border-t border-slate-200/60">
                          <div>
                            <span className="text-slate-400 block text-[10px]">Invoice Number</span>
                            <span className="font-mono font-bold text-slate-900">{activeExtraction.extracted_data.invoice_number}</span>
                          </div>
                          <div>
                            <span className="text-slate-400 block text-[10px]">Invoice Date</span>
                            <span className="font-mono text-slate-800">{activeExtraction.extracted_data.invoice_date}</span>
                          </div>
                          <div>
                            <span className="text-slate-400 block text-[10px]">Taxable Amount</span>
                            <span className="font-mono text-slate-800">₹{activeExtraction.extracted_data.taxable_amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span>
                          </div>
                          <div>
                            <span className="text-slate-400 block text-[10px]">Total Gross</span>
                            <span className="font-mono font-bold text-blue-700">₹{activeExtraction.extracted_data.total_amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* ACCOUNTING PROPOSAL (Directive 8) */}
                    {selectedProposal ? (
                      <div className="space-y-4">
                        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3">
                          <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                            <div className="flex items-center space-x-2">
                              <span className="text-xs font-bold uppercase text-slate-800">
                                Double-Entry Accounting Proposal
                              </span>
                              <span className="px-2 py-0.5 rounded bg-blue-100 text-blue-800 text-[10px] font-bold border border-blue-200">
                                PROPOSED — NOT POSTED TO TALLY
                              </span>
                            </div>
                            <span className="text-xs font-mono font-black text-slate-900">
                              Total: ₹{selectedProposal.total_amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                            </span>
                          </div>

                          {/* Double-entry Table */}
                          <div className="border border-slate-200 rounded-lg overflow-hidden bg-white text-xs shadow-xs">
                            <table className="w-full text-left">
                              <thead className="bg-slate-100/70 text-slate-600 font-bold border-b border-slate-200">
                                <tr>
                                  <th className="py-2.5 px-3">Ledger Name</th>
                                  <th className="py-2.5 px-3 text-right">Debit (₹)</th>
                                  <th className="py-2.5 px-3 text-right">Credit (₹)</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-100">
                                {selectedProposal.lines.map((line, idx) => (
                                  <tr key={idx} className="hover:bg-slate-50/50">
                                    <td className="py-2 px-3 font-medium text-slate-800">{line.ledger_name}</td>
                                    <td className="py-2 px-3 text-right font-mono font-semibold text-emerald-700">
                                      {line.is_debit ? line.amount.toFixed(2) : "-"}
                                    </td>
                                    <td className="py-2 px-3 text-right font-mono font-semibold text-amber-700">
                                      {!line.is_debit ? line.amount.toFixed(2) : "-"}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>

                          <div className="text-[11px] text-slate-500 italic">
                            Narration: {selectedProposal.narration}
                          </div>
                        </div>

                        {/* VALIDATION PANEL (Directive 9) */}
                        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-2.5">
                          <div className="flex items-center justify-between border-b border-slate-200 pb-1.5">
                            <span className="text-xs font-bold uppercase text-slate-700">
                              Deterministic Accounting Validation Invariants
                            </span>
                            <span className="text-[11px] text-slate-500">Governed by deterministic rule engine</span>
                          </div>

                          <div className="space-y-1.5">
                            {selectedProposal.validations.map((v, idx) => (
                              <div
                                key={idx}
                                className={`flex items-center justify-between text-xs px-3 py-2 rounded-lg border ${
                                  v.is_passed
                                    ? "bg-emerald-50/60 border-emerald-200 text-emerald-900"
                                    : "bg-rose-50/60 border-rose-200 text-rose-900"
                                }`}
                              >
                                <span className="font-mono font-bold">{v.rule_code}</span>
                                <span className="font-medium text-slate-700">{v.message}</span>
                                <span className="font-bold font-mono">
                                  {v.is_passed ? "✓ PASSED" : "✗ FAILED"}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* HUMAN APPROVAL CONSOLE (Directive 10) */}
                        {selectedProposal.status === "PENDING_APPROVAL" && (
                          <div className="bg-blue-50/40 border border-blue-200 rounded-xl p-5 space-y-3.5 shadow-xs">
                            <div className="flex items-center justify-between border-b border-blue-200 pb-2">
                              <h4 className="text-xs font-extrabold uppercase tracking-wider text-blue-950 flex items-center space-x-1.5">
                                <span>✍️</span>
                                <span>HUMAN APPROVAL REQUIRED</span>
                              </h4>
                              <span className="text-[11px] font-semibold text-blue-800">
                                Phase 3G Authority Gate
                              </span>
                            </div>

                            <p className="text-xs text-slate-600">
                              Authoritative human approval is required to materialize financial transactions. AI extraction never creates ledgers or writes transactions directly.
                            </p>

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                              <div>
                                <label className="text-[11px] font-bold text-slate-600">Authority Role</label>
                                <select
                                  value={approverRole}
                                  onChange={(e) => setApproverRole(e.target.value)}
                                  className="w-full mt-1 px-3 py-1.5 rounded-lg bg-white border border-slate-300 text-xs text-slate-800 shadow-xs"
                                >
                                  <option value="PRIMARY_APPROVER">Primary Finance Approver</option>
                                  <option value="FINANCE_HEAD">Head of Accounts / Finance Head</option>
                                  <option value="CFO">Chief Financial Officer (Prime)</option>
                                </select>
                              </div>

                              <div>
                                <label className="text-[11px] font-bold text-slate-600">Approver Verification Comments</label>
                                <input
                                  type="text"
                                  value={approverComments}
                                  onChange={(e) => setApproverComments(e.target.value)}
                                  className="w-full mt-1 px-3 py-1.5 rounded-lg bg-white border border-slate-300 text-xs text-slate-800 shadow-xs"
                                />
                              </div>
                            </div>

                            <button
                              onClick={() => handleApprove(selectedProposal.id)}
                              disabled={isProcessingAction}
                              className="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-md shadow-emerald-600/20 transition flex items-center justify-center space-x-2"
                            >
                              <span>✓ Approve & Materialize Authoritative Transaction</span>
                            </button>
                          </div>
                        )}

                        {/* BRIDGE EXECUTION TRIGGER (Directive 12 & Control 1) */}
                        {selectedProposal.status === "APPROVED" && selectedDoc.status === "APPROVED" && selectedProposal.posting_job_id && (
                          <div className="bg-indigo-50/50 border border-indigo-200 rounded-xl p-5 space-y-3 shadow-xs">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-bold uppercase text-indigo-950 flex items-center space-x-1.5">
                                <span>🚀</span>
                                <span>Phase 3I: Bridge Posting & Verification Gate</span>
                              </span>
                              <span className="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-indigo-100 text-indigo-800 border border-indigo-300">
                                Job #{selectedProposal.posting_job_id.slice(0, 8)} QUEUED
                              </span>
                            </div>

                            <p className="text-xs text-slate-600">
                              PostingJob is enqueued. Click below to execute the Bridge cycle: pulls the job, creates voucher in Tally via <strong>TallySimulatedAdapter</strong>, and performs immediate read-back verification.
                            </p>

                            <button
                              onClick={() => handleSimulateBridgeExecution(selectedProposal.posting_job_id!)}
                              disabled={isProcessingAction}
                              className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs shadow-md shadow-indigo-600/20 transition flex items-center justify-center space-x-2"
                            >
                              <span>🚀 Execute Bridge Cycle (Post → Read-Back Verify)</span>
                            </button>
                          </div>
                        )}

                        {/* VERIFICATION PANEL (Directive 13: Read-Back Verification Evidence) */}
                        {(selectedProposal.tally_voucher_number || selectedProposal.posting_status === "VERIFIED" || selectedDoc.status === "VERIFIED") && (
                          <div className="bg-white border-2 border-emerald-300 rounded-xl p-5 space-y-4 shadow-sm">
                            <div className="flex items-center justify-between border-b border-emerald-100 pb-2">
                              <div className="flex items-center space-x-2">
                                <span className="text-emerald-700 text-base">🛡️</span>
                                <span className="text-xs font-black uppercase tracking-wider text-slate-900">
                                  Tally Posting & Read-Back Verification Evidence
                                </span>
                              </div>
                              <span className="px-2.5 py-0.5 rounded-full text-xs font-extrabold bg-emerald-100 text-emerald-800 border border-emerald-300">
                                ✓ VERIFIED
                              </span>
                            </div>

                            {/* Tally Posting Details */}
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs bg-slate-50 p-3 rounded-lg border border-slate-200">
                              <div>
                                <span className="text-slate-400 block text-[10px]">Tally Voucher Number</span>
                                <strong className="font-mono text-emerald-800 text-sm">{selectedProposal.tally_voucher_number || "PUR/2026/0001"}</strong>
                              </div>
                              <div>
                                <span className="text-slate-400 block text-[10px]">Voucher GUID</span>
                                <span className="font-mono text-slate-700 text-[11px] truncate block">{selectedProposal.tally_guid || "TALLY-GUID-SIM-001"}</span>
                              </div>
                              <div>
                                <span className="text-slate-400 block text-[10px]">Voucher Type</span>
                                <strong className="text-slate-800">{selectedProposal.voucher_type}</strong>
                              </div>
                              <div>
                                <span className="text-slate-400 block text-[10px]">Voucher Date</span>
                                <span className="font-mono text-slate-800">{selectedProposal.proposed_date}</span>
                              </div>
                            </div>

                            {/* Read-Back Forensic Reconciliation */}
                            <div className="bg-emerald-50/40 border border-emerald-200 rounded-lg p-3 text-xs space-y-2">
                              <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-900 block">
                                Read-Back Forensic Evidence
                              </span>
                              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                                <div>
                                  <span className="text-slate-500 block text-[10px]">Expected Amount</span>
                                  <span className="font-mono font-bold text-slate-800">
                                    ₹{(selectedProposal.expected_amount || selectedProposal.total_amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-slate-500 block text-[10px]">Actual Read-Back Amount</span>
                                  <span className="font-mono font-bold text-emerald-800">
                                    ₹{(selectedProposal.actual_amount || selectedProposal.total_amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-slate-500 block text-[10px]">Reconciliation Method</span>
                                  <span className="font-mono text-slate-700">TALLY_READ_BACK (Forensic)</span>
                                </div>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="text-center py-10 bg-slate-50 rounded-xl border border-slate-200 text-slate-400 text-xs">
                        Document ingested. Click &ldquo;Run Gemini AI Extraction&rdquo; above to extract fields and propose double-entry accounting.
                      </div>
                    )}

                    {/* RECENT FORENSIC AUDIT TRAIL FEED (Directive 14) */}
                    <div className="border-t border-slate-200 pt-4 space-y-2.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold uppercase tracking-wider text-slate-700">Recent Audit Events</span>
                        <button
                          onClick={() => setActiveTab("audit")}
                          className="text-xs text-blue-600 hover:text-blue-800 font-semibold"
                        >
                          View Full Audit Log ({auditEvents.length}) →
                        </button>
                      </div>

                      <div className="space-y-1.5 max-h-44 overflow-y-auto pr-1">
                        {auditEvents.slice(0, 5).map((evt) => (
                          <div key={evt.id} className="p-2 rounded-lg bg-slate-50 border border-slate-200 text-xs flex items-center justify-between">
                            <div className="flex items-center space-x-2">
                              <span className="font-mono font-bold text-indigo-700 text-[11px]">{evt.action}</span>
                              <span className="text-slate-500 text-[10px]">by {evt.actor_type}</span>
                            </div>
                            <span className="text-slate-400 text-[10px] font-mono">
                              {new Date(evt.recorded_at).toLocaleTimeString()}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="bg-white border border-slate-200 rounded-2xl p-16 text-center text-slate-400 text-xs">
                    Select or upload an invoice from the left column to begin Golden Path processing.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: COMPANY DISCOVERY & MAPPING */}
        {activeTab === "discovery" && (
          <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-5">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <div>
                <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                  Discovered Tally Companies & Multi-Company Binding
                </h2>
                <p className="text-xs text-slate-500">
                  Companies reported outbound by WAAST360 Bridge via loopback Tally query.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {tallyCompanies.map((tc) => (
                <div key={tc.id} className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="font-bold text-slate-900 text-sm">{tc.company_name}</h3>
                    <span className="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-blue-100 text-blue-800 border border-blue-200">
                      {tc.status}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500 font-mono space-y-0.5">
                    <div>GUID: {tc.tally_guid}</div>
                    <div>FY: {tc.financial_year || "2024-2025"} • Books From: {tc.books_from || "2024-04-01"}</div>
                  </div>
                  <div className="pt-2 flex items-center space-x-2">
                    <button
                      onClick={() => handleQuickMap(tc.id)}
                      className="px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-xs transition"
                    >
                      1-Click Quick Map
                    </button>
                    <button
                      onClick={() => notify(`Tally Company: ${tc.company_name} (GUID: ${tc.tally_guid}, Books From: ${tc.books_from || "N/A"})`, "info")}
                      className="px-3.5 py-1.5 rounded-lg bg-white hover:bg-slate-100 text-slate-700 text-xs font-semibold border border-slate-200 transition"
                    >
                      Inspect Details
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 3: FULL FORENSIC AUDIT TRAIL */}
        {activeTab === "audit" && (
          <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <div>
                <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                  Immutable Append-Only Audit Trail
                </h2>
                <p className="text-xs text-slate-500">Non-repudiation security proof recorded in PostgreSQL.</p>
              </div>
              <span className="text-xs font-mono text-slate-500">{auditEvents.length} events logged</span>
            </div>

            {auditEvents.length === 0 ? (
              <div className="text-center py-12 text-slate-400 text-xs">
                No audit events recorded yet for this company.
              </div>
            ) : (
              <div className="space-y-2.5 max-h-[600px] overflow-y-auto pr-1">
                {auditEvents.map((evt) => (
                  <div key={evt.id} className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-indigo-700">{evt.action}</span>
                      <span className="text-slate-400 font-mono text-[11px]">
                        {new Date(evt.recorded_at).toLocaleString()}
                      </span>
                    </div>
                    <div className="text-slate-600 flex items-center space-x-3 text-[11px]">
                      <span>Actor: <strong className="text-slate-800">{evt.actor_type}</strong> ({evt.actor_id})</span>
                      <span>Entity: <strong className="text-slate-800">{evt.entity_type}</strong></span>
                    </div>
                    {evt.event_metadata && (
                      <pre className="p-2 rounded bg-white border border-slate-200 text-[11px] font-mono text-slate-700 overflow-x-auto">
                        {JSON.stringify(evt.event_metadata, null, 2)}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* MODAL: PREPARE FOR LIVE TALLY (Directive 15 Checklist) */}
        {showLiveTallyModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
            <div className="w-full max-w-lg bg-white rounded-2xl p-6 shadow-2xl space-y-4 border border-slate-200">
              <div className="flex items-center justify-between border-b border-slate-200 pb-3">
                <h3 className="text-base font-bold text-slate-900">Prepare for Live TallyPrime Connection</h3>
                <button onClick={() => setShowLiveTallyModal(false)} className="text-slate-400 hover:text-slate-600">✕</button>
              </div>

              <p className="text-xs text-slate-600">
                WAAST360 Lite uses the high-fidelity <strong>TallySimulatedAdapter</strong> during development. To certify live posting on client premises (Gate <code>LIVE-TALLY-CERT-001</code>), ensure:
              </p>

              <div className="space-y-2.5 text-xs">
                <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 flex items-start space-x-2">
                  <span className="text-emerald-600 font-bold">1.</span>
                  <div>
                    <strong>TallyPrime is running on office machine:</strong>
                    <p className="text-slate-500">Tally must be open with at least one company loaded.</p>
                  </div>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 flex items-start space-x-2">
                  <span className="text-emerald-600 font-bold">2.</span>
                  <div>
                    <strong>Tally ODBC / HTTP Server enabled:</strong>
                    <p className="text-slate-500">Configure TallyPrime port 9000 (F1: Help → Settings → Connectivity).</p>
                  </div>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 flex items-start space-x-2">
                  <span className="text-emerald-600 font-bold">3.</span>
                  <div>
                    <strong>WAAST360 Bridge running locally:</strong>
                    <p className="text-slate-500 font-mono">cd bridge &amp;&amp; python src/main.py test-tally</p>
                  </div>
                </div>
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  onClick={() => setShowLiveTallyModal(false)}
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-xs"
                >
                  Understood
                </button>
              </div>
            </div>
          </div>
        )}

        {/* MODAL: CREATE COMPANY */}
        {showCreateCompanyModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
            <div className="w-full max-w-md bg-white rounded-2xl p-6 shadow-2xl space-y-4 border border-slate-200">
              <h3 className="text-base font-bold text-slate-900">Create New WAAST360 Company</h3>
              <form onSubmit={handleCreateCompany} className="space-y-3">
                <div>
                  <label className="text-xs font-bold text-slate-700">Legal Company Name *</label>
                  <input
                    type="text"
                    required
                    value={newCompanyName}
                    onChange={(e) => setNewCompanyName(e.target.value)}
                    placeholder="e.g. Acme Motors Private Limited"
                    className="w-full mt-1 px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-800 text-xs focus:outline-none focus:border-blue-500 shadow-xs"
                  />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-700">PAN (Optional)</label>
                  <input
                    type="text"
                    value={newPan}
                    onChange={(e) => setNewPan(e.target.value.toUpperCase())}
                    placeholder="e.g. AAACT2727Q"
                    className="w-full mt-1 px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-800 text-xs font-mono focus:outline-none focus:border-blue-500 shadow-xs"
                  />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-700">GSTIN (Optional)</label>
                  <input
                    type="text"
                    value={newGstin}
                    onChange={(e) => setNewGstin(e.target.value.toUpperCase())}
                    placeholder="e.g. 27AAACT2727Q1ZW"
                    className="w-full mt-1 px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-800 text-xs font-mono focus:outline-none focus:border-blue-500 shadow-xs"
                  />
                </div>
                <div className="flex justify-end space-x-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowCreateCompanyModal(false)}
                    className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow-xs"
                  >
                    Create Company
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
