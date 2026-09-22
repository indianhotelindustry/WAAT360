"use client";

import React, { useState, useEffect, useCallback } from "react";

interface TallyStatusInfo {
  is_online?: boolean;
  tally_version?: string;
  response_time_ms?: number;
  error_message?: string;
  capabilities?: Record<string, boolean>;
}

interface BridgeStatus {
  bridge_connected: boolean;
  bridge_client_id: string;
  bridge_status: string;
  tally_online: boolean;
  tally_details: TallyStatusInfo;
  last_heartbeat?: string;
  companies_discovered_count: number;
  tally_instance?: {
    id: string;
    instance_name: string;
    host: string;
    port: number;
    is_active: boolean;
  };
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

interface CompanyItem {
  id: string;
  organization_id: string;
  legal_name: string;
  trade_name: string | null;
  pan: string | null;
  gstin: string | null;
  mapped_tally_company_id: string | null;
  mapped_tally_company_name: string | null;
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

interface ProposalItem {
  id: string;
  document_id: string;
  voucher_type: string;
  proposed_date: string;
  total_amount: number;
  tax_amount: number;
  narration: string;
  status: string;
  lines: Array<{ ledger_name: string; amount: number; is_debit: boolean }>;
  validations: Array<{ rule_code: string; severity: string; is_passed: boolean; message: string }>;
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

export default function GoldenPathDashboard() {
  const [activeTab, setActiveTab] = useState<"discovery" | "golden_path" | "audit">("golden_path");
  const [bridgeStatus, setBridgeStatus] = useState<BridgeStatus | null>(null);
  const [tallyCompanies, setTallyCompanies] = useState<TallyCompanyItem[]>([]);
  const [waastCompanies, setWaastCompanies] = useState<CompanyItem[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>("");
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [proposals, setProposals] = useState<ProposalItem[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEventItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionMessage, setActionMessage] = useState<{ text: string; type: "success" | "error" | "info" } | null>(null);

  // Discovery mapping modal
  const [selectedTallyComp, setSelectedTallyComp] = useState<TallyCompanyItem | null>(null);
  const [selectedWaastCompId, setSelectedWaastCompId] = useState<string>("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newCompanyName, setNewCompanyName] = useState("");
  const [newPan, setNewPan] = useState("");
  const [newGstin, setNewGstin] = useState("");

  // Golden path operations
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState<string>("");
  const [approverComments, setApproverComments] = useState("Audited & verified against GST Portal");
  const [approverRole, setApproverRole] = useState("PRIMARY_APPROVER");

  const API_BASE = "http://127.0.0.1:8000/api/v1";

  const showNotification = (text: string, type: "success" | "error" | "info" = "info") => {
    setActionMessage({ text, type });
    setTimeout(() => setActionMessage(null), 5000);
  };

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [statusRes, tallyRes, compRes] = await Promise.allSettled([
        fetch(`${API_BASE}/bridge/status`).then((r) => (r.ok ? r.json() : null)),
        fetch(`${API_BASE}/tally-companies`).then((r) => (r.ok ? r.json() : [])),
        fetch(`${API_BASE}/companies`).then((r) => (r.ok ? r.json() : [])),
      ]);

      if (statusRes.status === "fulfilled" && statusRes.value) {
        setBridgeStatus(statusRes.value);
      }
      if (tallyRes.status === "fulfilled" && Array.isArray(tallyRes.value)) {
        setTallyCompanies(tallyRes.value);
      }
      if (compRes.status === "fulfilled" && Array.isArray(compRes.value)) {
        setWaastCompanies(compRes.value);
        if (compRes.value.length > 0 && !selectedCompanyId) {
          setSelectedCompanyId(compRes.value[0].id);
        }
      }
    } catch {
      showNotification("Could not reach WAAST360 Cloud API on port 8000.", "error");
    } finally {
      setLoading(false);
    }
  }, [API_BASE, selectedCompanyId]);

  const loadGoldenPathData = useCallback(async (compId: string) => {
    if (!compId) return;
    try {
      const [docRes, propRes, auditRes] = await Promise.allSettled([
        fetch(`${API_BASE}/documents?company_id=${compId}`).then((r) => (r.ok ? r.json() : [])),
        fetch(`${API_BASE}/proposals?company_id=${compId}`).then((r) => (r.ok ? r.json() : [])),
        fetch(`${API_BASE}/bridge/audit/events?company_id=${compId}`).then((r) => (r.ok ? r.json() : [])),
      ]);
      if (docRes.status === "fulfilled" && Array.isArray(docRes.value)) {
        setDocuments(docRes.value);
        if (docRes.value.length > 0 && !selectedDocId) {
          setSelectedDocId(docRes.value[0].id);
        }
      }
      if (propRes.status === "fulfilled" && Array.isArray(propRes.value)) {
        setProposals(propRes.value);
      }
      if (auditRes.status === "fulfilled" && Array.isArray(auditRes.value)) {
        setAuditEvents(auditRes.value);
      }
    } catch {
      // Background poll
    }
  }, [API_BASE, selectedDocId]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  useEffect(() => {
    if (selectedCompanyId) {
      loadGoldenPathData(selectedCompanyId);
      const interval = setInterval(() => loadGoldenPathData(selectedCompanyId), 5000);
      return () => clearInterval(interval);
    }
  }, [selectedCompanyId, loadGoldenPathData]);

  // Handle Document Upload
  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile || !selectedCompanyId) {
      showNotification("Select a file and target company first.", "error");
      return;
    }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", uploadFile);
      formData.append("company_id", selectedCompanyId);

      const res = await fetch(`${API_BASE}/documents/upload`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Upload failed");
      const data = await res.json();
      showNotification(`Invoice uploaded successfully (DOC-${data.sha256_checksum.slice(0, 6)}).`, "success");
      setUploadFile(null);
      setSelectedDocId(data.id);
      loadGoldenPathData(selectedCompanyId);
    } catch (err) {
      showNotification(`Upload error: ${err}`, "error");
    } finally {
      setUploading(false);
    }
  };

  // Sample Invoice Generator
  const handleSampleUpload = async () => {
    if (!selectedCompanyId) {
      showNotification("Select a company first.", "error");
      return;
    }
    const invNo = Math.floor(1000 + Math.random() * 9000);
    const sampleContent = `TAX INVOICE
Vendor: Acme Steels & Hardware
Vendor GSTIN: 27AABCA1234F1Z9
Invoice No: INV-2026-${invNo}
Invoice Date: 2026-03-20
Taxable Amount: 15000.00
CGST 9%: 1350.00
SGST 9%: 1350.00
Total Amount: 17700.00
Terms: Net 30 Days`;
    const blob = new Blob([sampleContent], { type: "text/plain" });
    const file = new File([blob], `sample_tax_invoice_${invNo}.txt`, { type: "text/plain" });
    
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("company_id", selectedCompanyId);
      const res = await fetch(`${API_BASE}/documents/upload`, { method: "POST", body: formData });
      if (!res.ok) throw new Error("Upload failed");
      const data = await res.json();
      showNotification(`Sample Invoice created & ingested (SHA256: ${data.sha256_checksum.slice(0, 8)}...).`, "success");
      setSelectedDocId(data.id);
      loadGoldenPathData(selectedCompanyId);
    } catch (err) {
      showNotification(`Sample error: ${err}`, "error");
    } finally {
      setUploading(false);
    }
  };

  // Trigger AI Extraction
  const handleExtract = async (docId: string) => {
    try {
      showNotification("Triggering Gemini AI Extraction...", "info");
      const res = await fetch(`${API_BASE}/documents/${docId}/extract`, { method: "POST" });
      if (!res.ok) throw new Error("Extraction failed");
      const data = await res.json();
      showNotification(`AI Extraction complete for ${data.extracted_data.vendor_name} (Confidence: ${Math.round((data.confidence_score || 0.95) * 100)}%).`, "success");
      loadGoldenPathData(selectedCompanyId);
    } catch (err) {
      showNotification(`Extraction error: ${err}`, "error");
    }
  };

  // Generate Accounting Proposal
  const handleGenerateProposal = async (docId: string) => {
    try {
      showNotification("Evaluating Deterministic Accounting Rules & Invariants...", "info");
      const res = await fetch(`${API_BASE}/proposals/generate/${docId}`, { method: "POST" });
      if (!res.ok) throw new Error("Proposal generation failed");
      const data = await res.json();
      const passedCount = data.validations.filter((v: { is_passed: boolean }) => v.is_passed).length;
      showNotification(`Accounting Proposal generated! ${passedCount}/${data.validations.length} validation rules passed.`, "success");
      loadGoldenPathData(selectedCompanyId);
    } catch (err) {
      showNotification(`Proposal error: ${err}`, "error");
    }
  };

  // Approve Proposal
  const handleApprove = async (propId: string) => {
    try {
      showNotification("Submitting authoritative human approval...", "info");
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
      showNotification(`Approved! Transaction & PostingJob #${data.posting_job_id.slice(0, 8)} materialized.`, "success");
      loadGoldenPathData(selectedCompanyId);
    } catch (err) {
      showNotification(`Approval error: ${err}`, "error");
    }
  };

  // Simulate Bridge Posting & Read-Back Cycle
  const handleSimulateBridgeExecution = async (postingJobId: string) => {
    try {
      showNotification("Bridge picking up queued job from Cloud API...", "info");
      const vchNo = `PUR/2026/${Math.floor(1000 + Math.random() * 9000)}`;
      const vchGuid = `TALLY-GUID-${Date.now().toString(36).toUpperCase()}`;

      // 1. Post attempt
      await fetch(`${API_BASE}/bridge/jobs/${postingJobId}/attempts`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Bridge-Client-Id": "waast-bridge-local",
          "X-Bridge-Key": "dev-key",
        },
        body: JSON.stringify({
          success: true,
          voucher_guid: vchGuid,
          voucher_number: vchNo,
          master_id: Math.floor(1000 + Math.random() * 5000),
          status_code: 200,
          raw_response: `<RESPONSE><STATUS>1</STATUS><VOUCHERNUMBER>${vchNo}</VOUCHERNUMBER></RESPONSE>`,
        }),
      });

      // 2. Read-back verification
      await fetch(`${API_BASE}/bridge/jobs/${postingJobId}/verification`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Bridge-Client-Id": "waast-bridge-local",
          "X-Bridge-Key": "dev-key",
        },
        body: JSON.stringify({
          is_verified: true,
          status: "VERIFIED",
          actual_voucher_number: vchNo,
          actual_guid: vchGuid,
          actual_amount: 17700.0,
          raw_payload: { method: "TALLY_READ_BACK", reconciled: true },
        }),
      });

      showNotification(`Tally posting succeeded! Voucher ${vchNo} read-back verified. Audit log recorded.`, "success");
      loadGoldenPathData(selectedCompanyId);
    } catch (err) {
      showNotification(`Bridge cycle error: ${err}`, "error");
    }
  };

  // Create & Map Company
  const handleCreateCompany = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/companies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ legal_name: newCompanyName, pan: newPan || null, gstin: newGstin || null }),
      });
      if (!res.ok) throw new Error("Creation failed");
      const comp = await res.json();
      showNotification(`Company ${comp.legal_name} created successfully.`, "success");
      setShowCreateModal(false);
      setNewCompanyName("");
      setNewPan("");
      setNewGstin("");
      loadData();
    } catch (err) {
      showNotification(`Error creating company: ${err}`, "error");
    }
  };

  const handleQuickCreateAndMap = async (tallyCompId: string) => {
    try {
      const res = await fetch(`${API_BASE}/tally-companies/${tallyCompId}/create-and-map`, { method: "POST" });
      if (!res.ok) throw new Error("Mapping failed");
      showNotification("WAAST360 Company created and mapped to Tally company!", "success");
      loadData();
    } catch (err) {
      showNotification(`Quick-map error: ${err}`, "error");
    }
  };

  const handleManualMap = async () => {
    if (!selectedTallyComp || !selectedWaastCompId) return;
    try {
      const res = await fetch(`${API_BASE}/companies/${selectedWaastCompId}/map-tally/${selectedTallyComp.id}`, { method: "POST" });
      if (!res.ok) throw new Error("Mapping failed");
      showNotification("Company mapped successfully!", "success");
      setSelectedTallyComp(null);
      setSelectedWaastCompId("");
      loadData();
    } catch (err) {
      showNotification(`Manual map error: ${err}`, "error");
    }
  };

  const selectedDoc = documents.find((d) => d.id === selectedDocId) || documents[0];
  const selectedProposal = proposals.find((p) => selectedDoc && p.document_id === selectedDoc.id);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans antialiased selection:bg-indigo-500 selection:text-white">
      {/* Top Header */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur-xl sticky top-0 z-40 px-6 py-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-lg shadow-indigo-500/20 font-black text-xl text-white">
            W
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold tracking-tight text-white">WAAST360</h1>
              <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-400 font-semibold border border-indigo-500/30">
                Lite Golden Path
              </span>
            </div>
            <p className="text-xs text-slate-400">Wise Accounting Automation System for Tally</p>
          </div>
        </div>

        {/* Global Connection Badge & Tab Navigation */}
        <div className="flex items-center space-x-3">
          <div className="flex bg-slate-900 border border-slate-800 rounded-xl p-1 text-xs font-semibold">
            <button
              onClick={() => setActiveTab("golden_path")}
              className={`px-3 py-1.5 rounded-lg transition ${
                activeTab === "golden_path" ? "bg-indigo-600 text-white shadow" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Golden Path Operations
            </button>
            <button
              onClick={() => setActiveTab("discovery")}
              className={`px-3 py-1.5 rounded-lg transition ${
                activeTab === "discovery" ? "bg-indigo-600 text-white shadow" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Tally Company Discovery ({tallyCompanies.length})
            </button>
            <button
              onClick={() => setActiveTab("audit")}
              className={`px-3 py-1.5 rounded-lg transition ${
                activeTab === "audit" ? "bg-indigo-600 text-white shadow" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Forensic Audit Trail ({auditEvents.length})
            </button>
          </div>

          <div className="flex items-center space-x-2 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-xl text-xs font-medium">
            <span className={`h-2.5 w-2.5 rounded-full ${bridgeStatus?.bridge_connected ? "bg-emerald-500 animate-pulse" : "bg-rose-500"}`} />
            <span className="text-slate-300">Bridge: {bridgeStatus?.bridge_status || "OFFLINE"}</span>
            <span className="text-slate-600">|</span>
            <span className={`h-2.5 w-2.5 rounded-full ${bridgeStatus?.tally_online ? "bg-emerald-500" : "bg-amber-500"}`} />
            <span className="text-slate-300">Tally: {bridgeStatus?.tally_online ? "ONLINE" : "SIMULATED / READY"}</span>
          </div>
        </div>
      </header>

      {/* Notifications */}
      {actionMessage && (
        <div
          className={`px-6 py-2.5 text-xs font-medium flex items-center justify-between border-b transition-all ${
            actionMessage.type === "success"
              ? "bg-emerald-950/80 text-emerald-300 border-emerald-800"
              : actionMessage.type === "error"
              ? "bg-rose-950/80 text-rose-300 border-rose-800"
              : "bg-blue-950/80 text-blue-300 border-blue-800"
          }`}
        >
          <span>{actionMessage.text}</span>
          <button onClick={() => setActionMessage(null)} className="opacity-70 hover:opacity-100 text-sm">
            ✕
          </button>
        </div>
      )}

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        {/* Company Selector Header */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 backdrop-blur-sm">
          <div className="flex items-center space-x-3">
            <div className="h-9 w-9 rounded-lg bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400 font-bold text-sm">
              🏢
            </div>
            <div>
              <label className="text-[10px] uppercase font-bold tracking-wider text-slate-500">Active WAAST360 Company</label>
              <select
                value={selectedCompanyId}
                onChange={(e) => setSelectedCompanyId(e.target.value)}
                className="block text-sm font-semibold bg-transparent text-white border-0 focus:ring-0 p-0 cursor-pointer"
              >
                {waastCompanies.map((c) => (
                  <option key={c.id} value={c.id} className="bg-slate-900 text-white">
                    {c.legal_name} {c.mapped_tally_company_name ? `→ (${c.mapped_tally_company_name})` : "(Unmapped)"}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setShowCreateModal(true)}
              className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition"
            >
              + New Company
            </button>
            <button
              onClick={() => {
                loadData();
                if (selectedCompanyId) loadGoldenPathData(selectedCompanyId);
              }}
              className="px-3 py-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 text-xs font-semibold border border-indigo-500/30 transition flex items-center space-x-1"
            >
              <span>↻ Refresh</span>
            </button>
          </div>
        </div>

        {/* TAB 1: GOLDEN PATH OPERATIONS */}
        {activeTab === "golden_path" && (
          <div className="space-y-6">
            {/* Golden Path Pipeline Visualizer */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 backdrop-blur-sm">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-4">
                10-Stage Golden Path Pipeline Lifecycle
              </h2>
              <div className="grid grid-cols-2 sm:grid-cols-5 lg:grid-cols-10 gap-2 text-center text-[11px] font-semibold">
                {[
                  { step: "1. RECEIVED", status: selectedDoc ? "DONE" : "PENDING" },
                  { step: "2. EXTRACTED", status: selectedDoc?.status !== "RECEIVED" && selectedDoc ? "DONE" : "PENDING" },
                  { step: "3. PROPOSED", status: selectedProposal ? "DONE" : "PENDING" },
                  { step: "4. VALIDATED", status: selectedProposal?.validations?.every((v) => v.is_passed) ? "DONE" : "PENDING" },
                  { step: "5. PENDING APPR", status: selectedProposal?.status === "PENDING_APPROVAL" ? "CURRENT" : selectedProposal?.status === "APPROVED" ? "DONE" : "PENDING" },
                  { step: "6. APPROVED", status: selectedProposal?.status === "APPROVED" ? "DONE" : "PENDING" },
                  { step: "7. POSTING", status: selectedDoc?.status === "POSTING" ? "CURRENT" : ["POSTED", "VERIFIED"].includes(selectedDoc?.status || "") ? "DONE" : "PENDING" },
                  { step: "8. POSTED", status: ["POSTED", "VERIFIED"].includes(selectedDoc?.status || "") ? "DONE" : "PENDING" },
                  { step: "9. VERIFIED", status: selectedDoc?.status === "VERIFIED" ? "DONE" : "PENDING" },
                  { step: "10. AUDIT PROVED", status: auditEvents.length > 0 ? "DONE" : "PENDING" },
                ].map((s, i) => (
                  <div
                    key={i}
                    className={`p-2.5 rounded-xl border transition-all ${
                      s.status === "DONE"
                        ? "bg-emerald-950/40 border-emerald-500/50 text-emerald-300"
                        : s.status === "CURRENT"
                        ? "bg-indigo-950/60 border-indigo-500 text-indigo-300 ring-2 ring-indigo-500/30 animate-pulse"
                        : "bg-slate-950/50 border-slate-800 text-slate-500"
                    }`}
                  >
                    <div className="text-[10px] opacity-70 mb-0.5">{s.status}</div>
                    <div>{s.step}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Split Screen: Left = Ingestion & Documents, Right = Proposal & Approval */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Left Column (5 Cols) */}
              <div className="lg:col-span-5 space-y-6">
                {/* Upload Invoice Card */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 backdrop-blur-sm space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                      <span>📄</span>
                      <span>Phase 3B: Ingest Invoice</span>
                    </h3>
                    <button
                      onClick={handleSampleUpload}
                      disabled={uploading}
                      className="text-xs px-2.5 py-1 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 transition disabled:opacity-50"
                    >
                      + Quick Sample Invoice
                    </button>
                  </div>

                  <form onSubmit={handleUpload} className="space-y-3">
                    <div className="border-2 border-dashed border-slate-800 hover:border-slate-700 rounded-xl p-4 text-center cursor-pointer transition">
                      <input
                        type="file"
                        onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                        className="block w-full text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-indigo-600 file:text-white hover:file:bg-indigo-500 cursor-pointer"
                      />
                      <p className="text-[11px] text-slate-500 mt-2">Upload Tax Invoice (PDF, TXT, PNG) • Computes SHA256</p>
                    </div>

                    <button
                      type="submit"
                      disabled={!uploadFile || uploading}
                      className="w-full py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold text-xs shadow-lg shadow-indigo-600/20 transition"
                    >
                      {uploading ? "Ingesting & Hashing..." : "Ingest Document"}
                    </button>
                  </form>
                </div>

                {/* Ingested Documents List */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 backdrop-blur-sm space-y-3">
                  <h3 className="text-sm font-bold text-white flex items-center justify-between">
                    <span>Ingested Documents ({documents.length})</span>
                    <span className="text-xs text-slate-500 font-normal">Select to inspect</span>
                  </h3>

                  {documents.length === 0 ? (
                    <div className="text-center py-6 text-slate-500 text-xs">
                      No documents ingested yet. Upload an invoice above or use Quick Sample Invoice.
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                      {documents.map((doc) => (
                        <div
                          key={doc.id}
                          onClick={() => setSelectedDocId(doc.id)}
                          className={`p-3 rounded-xl border text-xs cursor-pointer transition ${
                            selectedDoc?.id === doc.id
                              ? "bg-indigo-950/40 border-indigo-500 shadow-md"
                              : "bg-slate-950/60 border-slate-800 hover:border-slate-700"
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-semibold text-slate-200">{doc.file_name}</span>
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                doc.status === "VERIFIED"
                                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                                  : doc.status === "POSTED"
                                  ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                                  : doc.status === "APPROVED"
                                  ? "bg-indigo-500/20 text-indigo-400 border border-indigo-500/30"
                                  : doc.status === "PROPOSED"
                                  ? "bg-purple-500/20 text-purple-400 border border-purple-500/30"
                                  : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                              }`}
                            >
                              {doc.status}
                            </span>
                          </div>
                          <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono">
                            <span>SHA: {doc.sha256_checksum.slice(0, 10)}...</span>
                            <span>{new Date(doc.created_at).toLocaleTimeString()}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Right Column (7 Cols): Inspection, Extraction, Proposal, Approval */}
              <div className="lg:col-span-7 space-y-6">
                {selectedDoc ? (
                  <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 backdrop-blur-sm space-y-5">
                    {/* Document Header & AI Action */}
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-4 border-b border-slate-800 gap-3">
                      <div>
                        <div className="flex items-center space-x-2">
                          <h3 className="text-base font-bold text-white">{selectedDoc.file_name}</h3>
                          <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
                            {selectedDoc.document_number}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400 mt-1">
                          Current Stage: <span className="font-semibold text-indigo-400">{selectedDoc.status}</span>
                        </p>
                      </div>

                      <div className="flex items-center space-x-2">
                        {selectedDoc.status === "RECEIVED" && (
                          <button
                            onClick={() => handleExtract(selectedDoc.id)}
                            className="px-3.5 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-lg shadow-purple-600/20 transition flex items-center space-x-1.5"
                          >
                            <span>✨ Run Gemini AI Extraction</span>
                          </button>
                        )}
                        {selectedDoc.status === "EXTRACTED" && (
                          <button
                            onClick={() => handleGenerateProposal(selectedDoc.id)}
                            className="px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/20 transition flex items-center space-x-1.5"
                          >
                            <span>⚙️ Generate Accounting Proposal</span>
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Proposal & Validation Card */}
                    {selectedProposal ? (
                      <div className="space-y-4">
                        <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 space-y-3">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold uppercase text-slate-400">
                              Proposed Double-Entry Voucher
                            </span>
                            <span className="text-xs font-mono font-bold text-emerald-400">
                              Total: ₹{selectedProposal.total_amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                            </span>
                          </div>

                          <div className="border border-slate-800 rounded-lg overflow-hidden text-xs">
                            <table className="w-full text-left">
                              <thead className="bg-slate-900 text-slate-400 font-medium">
                                <tr>
                                  <th className="py-2 px-3">Ledger Name</th>
                                  <th className="py-2 px-3 text-right">Debit (₹)</th>
                                  <th className="py-2 px-3 text-right">Credit (₹)</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-800">
                                {selectedProposal.lines.map((line, idx) => (
                                  <tr key={idx} className="hover:bg-slate-900/50">
                                    <td className="py-2 px-3 text-slate-200 font-medium">{line.ledger_name}</td>
                                    <td className="py-2 px-3 text-right font-mono text-emerald-400">
                                      {line.is_debit ? line.amount.toFixed(2) : "-"}
                                    </td>
                                    <td className="py-2 px-3 text-right font-mono text-amber-400">
                                      {!line.is_debit ? line.amount.toFixed(2) : "-"}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>

                          <p className="text-[11px] text-slate-400 italic">
                            Narration: {selectedProposal.narration}
                          </p>
                        </div>

                        {/* Deterministic Validation Checks */}
                        <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 space-y-2">
                          <h4 className="text-xs font-bold uppercase text-slate-400 mb-2">
                            Deterministic Validation Rules
                          </h4>
                          <div className="space-y-1.5">
                            {selectedProposal.validations.map((v, idx) => (
                              <div
                                key={idx}
                                className={`flex items-center justify-between text-xs px-3 py-1.5 rounded-lg border ${
                                  v.is_passed
                                    ? "bg-emerald-950/30 border-emerald-800/50 text-emerald-300"
                                    : "bg-rose-950/30 border-rose-800/50 text-rose-300"
                                }`}
                              >
                                <span className="font-mono font-semibold">{v.rule_code}</span>
                                <span>{v.message}</span>
                                <span>{v.is_passed ? "✓ PASSED" : "✗ FAILED"}</span>
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Human Approval Console */}
                        {selectedProposal.status === "PENDING_APPROVAL" && (
                          <div className="bg-indigo-950/30 border border-indigo-500/30 rounded-xl p-4 space-y-3">
                            <h4 className="text-xs font-bold uppercase tracking-wider text-indigo-300">
                              Phase 3G: Authoritative Human Approval Gate
                            </h4>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                              <div>
                                <label className="text-[11px] font-semibold text-slate-400">Approver Comments</label>
                                <input
                                  type="text"
                                  value={approverComments}
                                  onChange={(e) => setApproverComments(e.target.value)}
                                  className="w-full mt-1 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200"
                                />
                              </div>
                              <div>
                                <label className="text-[11px] font-semibold text-slate-400">Authority Role</label>
                                <select
                                  value={approverRole}
                                  onChange={(e) => setApproverRole(e.target.value)}
                                  className="w-full mt-1 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200"
                                >
                                  <option value="PRIMARY_APPROVER">Primary Finance Approver</option>
                                  <option value="FINANCE_HEAD">Head of Accounts / Finance Head</option>
                                  <option value="CFO">Chief Financial Officer (Prime)</option>
                                </select>
                              </div>
                            </div>

                            <button
                              onClick={() => handleApprove(selectedProposal.id)}
                              className="w-full py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs shadow-lg shadow-emerald-600/20 transition flex items-center justify-center space-x-2"
                            >
                              <span>✓ Approve & Materialize Authoritative Transaction</span>
                            </button>
                          </div>
                        )}

                        {/* Bridge Execution Trigger */}
                        {selectedProposal.status === "APPROVED" && selectedDoc.status === "APPROVED" && (
                          <div className="bg-slate-950/80 border border-indigo-500/30 rounded-xl p-4 space-y-3">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-bold uppercase text-indigo-300">
                                Phase 3I: Bridge Posting & Verification Gate
                              </span>
                              <span className="text-xs px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-400 font-semibold">
                                Job Queued
                              </span>
                            </div>
                            <p className="text-xs text-slate-400">
                              The posting job is enqueued in WAAST360 Cloud. Click below to simulate the Bridge pulling the job, creating the voucher in Tally, and performing instant read-back verification.
                            </p>
                            <button
                              onClick={() => handleSimulateBridgeExecution(selectedProposal.id)}
                              className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs shadow-lg shadow-indigo-600/20 transition"
                            >
                              🚀 Execute Bridge Cycle (Post → Read-Back Verify)
                            </button>
                          </div>
                        )}

                        {selectedDoc.status === "VERIFIED" && (
                          <div className="bg-emerald-950/40 border border-emerald-500/40 rounded-xl p-4 text-center space-y-1">
                            <div className="text-emerald-400 font-bold text-sm">
                              ✓ Golden Path Certified: Read-Back Verified & Audit Proved
                            </div>
                            <p className="text-xs text-slate-400">
                              Voucher recorded in Tally with forensic verification evidence and immutable audit log.
                            </p>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="text-center py-10 bg-slate-950/40 rounded-xl border border-slate-800 text-slate-500 text-xs">
                        Document ingested. Click &ldquo;Run Gemini AI Extraction&rdquo; above to extract line items and generate accounting proposals.
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-12 text-center text-slate-500 text-xs">
                    Select or upload a document to begin the Golden Path operations.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: COMPANY DISCOVERY & MAPPING */}
        {activeTab === "discovery" && (
          <div className="space-y-6">
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 backdrop-blur-sm space-y-4">
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                Discovered Tally Companies & Multi-Company Binding
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {tallyCompanies.map((tc) => (
                  <div key={tc.id} className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="font-bold text-slate-200 text-sm">{tc.company_name}</h3>
                      <span className="text-[10px] px-2 py-0.5 rounded font-mono bg-indigo-500/10 text-indigo-400 border border-indigo-500/30">
                        {tc.status}
                      </span>
                    </div>
                    <div className="text-xs text-slate-400 space-y-1 font-mono">
                      <div>GUID: {tc.tally_guid}</div>
                      <div>FY: {tc.financial_year || "2024-2025"} • Books: {tc.books_from || "2024-04-01"}</div>
                    </div>
                    <div className="flex items-center space-x-2 pt-2">
                      <button
                        onClick={() => handleQuickCreateAndMap(tc.id)}
                        className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition"
                      >
                        1-Click Quick Map
                      </button>
                      <button
                        onClick={() => setSelectedTallyComp(tc)}
                        className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition"
                      >
                        Map Existing...
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: FORENSIC AUDIT TRAIL */}
        {activeTab === "audit" && (
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 backdrop-blur-sm space-y-4">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center justify-between">
              <span>Immutable Append-Only Audit Trail</span>
              <span className="text-xs text-slate-500 font-mono">Non-Repudiation Security Model</span>
            </h2>

            {auditEvents.length === 0 ? (
              <div className="text-center py-10 text-slate-500 text-xs">
                No audit events recorded yet for this company.
              </div>
            ) : (
              <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2">
                {auditEvents.map((evt) => (
                  <div key={evt.id} className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-indigo-400">{evt.action}</span>
                      <span className="text-slate-500 font-mono text-[11px]">{new Date(evt.recorded_at).toLocaleString()}</span>
                    </div>
                    <div className="text-slate-400 flex items-center space-x-3 text-[11px]">
                      <span>Actor: <strong className="text-slate-200">{evt.actor_type}</strong> ({evt.actor_id})</span>
                      <span>Target: <strong className="text-slate-200">{evt.entity_type}</strong></span>
                    </div>
                    {evt.event_metadata && (
                      <pre className="p-2 rounded bg-slate-900 border border-slate-850 text-[10px] text-slate-400 font-mono overflow-x-auto">
                        {JSON.stringify(evt.event_metadata, null, 2)}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Modal: Manual Map Existing */}
        {selectedTallyComp && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
            <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4">
              <h3 className="text-base font-bold text-white">Map Tally Company</h3>
              <p className="text-xs text-slate-400">
                Associating Tally Company: <strong className="text-white">{selectedTallyComp.company_name}</strong>
              </p>
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-300">Select Target WAAST360 Company</label>
                <select
                  value={selectedWaastCompId}
                  onChange={(e) => setSelectedWaastCompId(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-slate-200 text-sm focus:outline-none focus:border-indigo-500"
                >
                  <option value="">-- Choose Company --</option>
                  {waastCompanies.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.legal_name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex items-center justify-end space-x-3 pt-3">
                <button
                  onClick={() => setSelectedTallyComp(null)}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition"
                >
                  Cancel
                </button>
                <button
                  onClick={handleManualMap}
                  disabled={!selectedWaastCompId}
                  className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold transition"
                >
                  Confirm Mapping
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Modal: Create Company */}
        {showCreateModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
            <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4">
              <h3 className="text-base font-bold text-white">Create WAAST360 Company</h3>
              <form onSubmit={handleCreateCompany} className="space-y-3">
                <div>
                  <label className="text-xs font-semibold text-slate-300">Legal Name *</label>
                  <input
                    type="text"
                    required
                    value={newCompanyName}
                    onChange={(e) => setNewCompanyName(e.target.value)}
                    placeholder="e.g. Acme Enterprise Pvt Ltd"
                    className="w-full mt-1 px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-slate-200 text-sm focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-300">PAN (Optional)</label>
                  <input
                    type="text"
                    value={newPan}
                    onChange={(e) => setNewPan(e.target.value.toUpperCase())}
                    placeholder="e.g. ABCDE1234F"
                    className="w-full mt-1 px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-slate-200 text-sm focus:outline-none focus:border-indigo-500 font-mono"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-300">GSTIN (Optional)</label>
                  <input
                    type="text"
                    value={newGstin}
                    onChange={(e) => setNewGstin(e.target.value.toUpperCase())}
                    placeholder="e.g. 27ABCDE1234F1Z5"
                    className="w-full mt-1 px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-slate-200 text-sm focus:outline-none focus:border-indigo-500 font-mono"
                  />
                </div>
                <div className="flex items-center justify-end space-x-3 pt-3">
                  <button
                    type="button"
                    onClick={() => setShowCreateModal(false)}
                    className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition"
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
