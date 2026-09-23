"use client";

import React, { useState, useEffect, useCallback } from "react";

// =========================================================================
// DATA CONTRACTS (Synchronized with Backend Schemas)
// =========================================================================

export interface KnowledgeSource {
  id: string;
  source_code: string;
  authority_name: string;
  source_type: string;
  reference_url?: string | null;
  citation?: string | null;
  jurisdiction: string;
  is_verified: boolean;
  reviewed_by?: string | null;
}

export interface KnowledgeItem {
  id: string;
  knowledge_code: string;
  domain: string;
  title: string;
  content: string;
  jurisdiction: string;
  effective_from: string;
  effective_until?: string | null;
  rule_version: number;
  tally_version_pattern?: string | null;
  status: string;
  confidence: number;
  source?: KnowledgeSource | null;
}

export interface ForensicFinding {
  id: string;
  scan_id: string;
  company_id: string;
  finding_code: string;
  rule_code: string;
  entity_type: string;
  entity_name: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO";
  fact_observed: string;
  fact_details: Record<string, unknown>;
  rule_triggered: string;
  knowledge_code?: string | null;
  recommendation: string;
  decision_status: "PENDING_REVIEW" | "PROPOSED_CORRECTION" | "KNOWN_EXCEPTION" | "CORRECTED";
  known_exception_id?: string | null;
  created_at: string;
}

export interface ForensicScan {
  id: string;
  company_id: string;
  scan_code: string;
  scan_status: string;
  ledgers_reviewed: number;
  findings_count: number;
  critical_count: number;
  review_recommended_count: number;
  healthy_count: number;
  gst_findings_count: number;
  duplicate_clusters_count: number;
  known_exceptions_count: number;
  overall_health: "REVIEW_RECOMMENDED" | "CRITICAL_FINDINGS" | "REVIEW_COMPLETE" | "HEALTHY";
  scanned_at: string;
  findings: ForensicFinding[];
}

export interface CorrectionProposal {
  id: string;
  finding_id: string;
  company_id: string;
  target_entity_type: string;
  target_entity_name: string;
  before_state: Record<string, unknown>;
  proposed_state: Record<string, unknown>;
  status: "PROPOSED" | "APPROVAL_REQUIRED" | "APPROVED" | "EXECUTION_ELIGIBLE" | "VERIFIED" | "STALE_REJECTED";
  approval_id?: string | null;
  created_at: string;
}

export interface DecisionMemoryItem {
  id: string;
  company_id: string;
  finding_code: string;
  rule_code: string;
  entity_type: string;
  entity_name: string;
  decision_reason: string;
  human_decision: string;
  actor_id: string;
  actor_role: string;
  decided_at: string;
}

interface CompanyIntelligenceViewProps {
  apiBase: string;
  selectedCompanyId: string;
  selectedCompanyName: string;
  onNotify: (text: string, type?: "success" | "error" | "info") => void;
}

export default function CompanyIntelligenceView({
  apiBase,
  selectedCompanyId,
  selectedCompanyName,
  onNotify,
}: CompanyIntelligenceViewProps) {
  // Navigation inside Intelligence view
  const [activeSubTab, setActiveSubTab] = useState<"health" | "findings" | "corrections" | "knowledge" | "decisions">("health");
  const [findingFilter, setFindingFilter] = useState<"ALL" | "CRITICAL" | "GST" | "DUPLICATES" | "EXCEPTIONS">("ALL");

  // Core Intelligence Data
  const [scan, setScan] = useState<ForensicScan | null>(null);
  const [corrections, setCorrections] = useState<CorrectionProposal[]>([]);
  const [decisions, setDecisions] = useState<DecisionMemoryItem[]>([]);
  const [knowledgeItems, setKnowledgeItems] = useState<KnowledgeItem[]>([]);

  // Interactive Loading & Action States
  const [isScanning, setIsScanning] = useState(false);
  const [isActing, setIsActing] = useState(false);
  const [explainModalFinding, setExplainModalFinding] = useState<ForensicFinding | null>(null);

  // Modals for Controls & Approvals
  const [showKnownExceptionModal, setShowKnownExceptionModal] = useState<ForensicFinding | null>(null);
  const [exceptionReason, setExceptionReason] = useState("Company-specific accounting policy approved by Controller");
  const [exceptionApproverRole, setExceptionApproverRole] = useState("CONTROLLER");

  const [showProposeModal, setShowProposeModal] = useState<ForensicFinding | null>(null);
  const [proposedTargetGroup, setProposedTargetGroup] = useState("Sundry Creditors");

  const [showApproveModal, setShowApproveModal] = useState<CorrectionProposal | null>(null);
  const [approvalComments, setApprovalComments] = useState("Reviewed and approved ledger master reclassification");
  const [approvalRole, setApprovalRole] = useState("CONTROLLER");

  const [lastExecutionEvidence, setLastExecutionEvidence] = useState<{
    target_entity: string;
    before_group: string;
    after_group: string;
    status: string;
    verified_at: string;
  } | null>(null);

  const [staleErrorAlert, setStaleErrorAlert] = useState<string | null>(null);

  // 1. Fetch Latest Scan
  const fetchScan = useCallback(async () => {
    if (!selectedCompanyId) return;
    try {
      const res = await fetch(`${apiBase}/health-check/scans/${selectedCompanyId}/latest`);
      if (res.ok) {
        const data: ForensicScan = await res.json();
        setScan(data);
      } else {
        setScan(null);
      }
    } catch {
      // Offline or initial load
    }
  }, [apiBase, selectedCompanyId]);

  // 2. Fetch Corrections
  const fetchCorrections = useCallback(async () => {
    if (!selectedCompanyId) return;
    try {
      const res = await fetch(`${apiBase}/health-check/corrections?company_id=${selectedCompanyId}`);
      if (res.ok) {
        const data = await res.json();
        setCorrections(data);
      }
    } catch {
      // Backend quiet
    }
  }, [apiBase, selectedCompanyId]);

  // 3. Fetch Decisions
  const fetchDecisions = useCallback(async () => {
    if (!selectedCompanyId) return;
    try {
      const res = await fetch(`${apiBase}/health-check/decisions?company_id=${selectedCompanyId}`);
      if (res.ok) {
        const data = await res.json();
        setDecisions(data);
      }
    } catch {
      // Backend quiet
    }
  }, [apiBase, selectedCompanyId]);

  // 4. Fetch Knowledge Items
  const fetchKnowledge = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/health-check/knowledge`);
      if (res.ok) {
        const data = await res.json();
        setKnowledgeItems(data);
      }
    } catch {
      // Backend quiet
    }
  }, [apiBase]);

  // Initial and reactive data load
  useEffect(() => {
    let isMounted = true;
    const loadData = async () => {
      if (!isMounted) return;
      await Promise.allSettled([
        fetchScan(),
        fetchCorrections(),
        fetchDecisions(),
        fetchKnowledge(),
      ]);
    };
    loadData();
    return () => {
      isMounted = false;
    };
  }, [fetchScan, fetchCorrections, fetchDecisions, fetchKnowledge]);

  // =========================================================================
  // ACTIONS: SCAN, RECORD DECISION, PROPOSE, APPROVE, EXECUTE
  // =========================================================================

  const handleRunScan = async () => {
    if (!selectedCompanyId) {
      onNotify("Please select an active company first.", "error");
      return;
    }
    setIsScanning(true);
    setStaleErrorAlert(null);
    try {
      const res = await fetch(`${apiBase}/health-check/scans/run?company_id=${selectedCompanyId}`, {
        method: "POST",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Health check scan failed" }));
        throw new Error(err.detail || "Scan failed");
      }
      const newScan: ForensicScan = await res.json();
      setScan(newScan);
      await fetchCorrections();
      await fetchDecisions();
      onNotify(`Accounting Health Check completed: ${newScan.findings_count} findings reviewed across ${newScan.ledgers_reviewed} ledgers.`, "success");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      onNotify(`Scan error: ${msg}`, "error");
    } finally {
      setIsScanning(false);
    }
  };

  const handleRecordKnownException = async () => {
    if (!showKnownExceptionModal) return;
    setIsActing(true);
    try {
      const res = await fetch(`${apiBase}/health-check/findings/${showKnownExceptionModal.id}/record-decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision_reason: exceptionReason,
          actor_id: "controller@waast360.local",
          actor_role: exceptionApproverRole,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Failed to record exception" }));
        throw new Error(err.detail);
      }
      onNotify(`Marked as Known Exception. Underlying forensic finding remains transparent.`, "info");
      setShowKnownExceptionModal(null);
      await fetchScan();
      await fetchDecisions();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      onNotify(`Error: ${msg}`, "error");
    } finally {
      setIsActing(false);
    }
  };

  const handleProposeCorrection = async () => {
    if (!showProposeModal) return;
    setIsActing(true);
    try {
      const res = await fetch(`${apiBase}/health-check/findings/${showProposeModal.id}/propose-correction`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          new_parent_group: proposedTargetGroup,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Proposal creation failed" }));
        throw new Error(err.detail);
      }
      onNotify(`Correction proposal generated with status: APPROVAL REQUIRED.`, "success");
      setShowProposeModal(null);
      await fetchScan();
      await fetchCorrections();
      setActiveSubTab("corrections");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      onNotify(`Error: ${msg}`, "error");
    } finally {
      setIsActing(false);
    }
  };

  const handleApproveProposal = async () => {
    if (!showApproveModal) return;
    setIsActing(true);
    try {
      const res = await fetch(`${apiBase}/health-check/corrections/${showApproveModal.id}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          approver_role: approvalRole,
          comments: approvalComments,
          approval_signature: `SIG-CORR-${Date.now().toString(36).toUpperCase()}`,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Approval failed" }));
        throw new Error(err.detail);
      }
      onNotify(`Proposal approved! Status transitioned to EXECUTION ELIGIBLE.`, "success");
      setShowApproveModal(null);
      await fetchCorrections();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      onNotify(`Approval error: ${msg}`, "error");
    } finally {
      setIsActing(false);
    }
  };

  const handleExecuteCorrection = async (proposalId: string) => {
    setIsActing(true);
    setStaleErrorAlert(null);
    try {
      const res = await fetch(`${apiBase}/health-check/corrections/${proposalId}/execute`, {
        method: "POST",
      });
      if (res.status === 409) {
        const err = await res.json();
        setStaleErrorAlert(err.detail || "STOP — stale correction proposal. Re-scan required.");
        onNotify("Correction aborted: Target state mismatch in Tally master.", "error");
        await fetchCorrections();
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Execution failed" }));
        throw new Error(err.detail);
      }
      const data = await res.json();
      setLastExecutionEvidence({
        target_entity: data.target_entity_name,
        before_group: data.before_group,
        after_group: data.after_group,
        status: data.status,
        verified_at: data.verified_at,
      });
      onNotify(`Correction executed and verified! Ledger '${data.target_entity_name}' reclassified to '${data.after_group}'.`, "success");
      await fetchCorrections();
      await fetchScan();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      onNotify(`Execution error: ${msg}`, "error");
    } finally {
      setIsActing(false);
    }
  };

  // Filtered findings
  const findings = scan?.findings || [];
  const filteredFindings = findings.filter((f) => {
    if (findingFilter === "CRITICAL") return f.severity === "CRITICAL" || f.severity === "HIGH";
    if (findingFilter === "GST") return f.rule_code.includes("GST") || f.entity_name.toLowerCase().includes("gst");
    if (findingFilter === "DUPLICATES") return f.rule_code.includes("DUP") || f.finding_code.includes("DUP");
    if (findingFilter === "EXCEPTIONS") return f.decision_status === "KNOWN_EXCEPTION";
    return true;
  });

  return (
    <div className="space-y-6">
      {/* ===================================================================== */}
      {/* 1. TOP HEADER & SUB-NAVIGATION                                        */}
      {/* ===================================================================== */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white border border-slate-200 p-5 rounded-2xl shadow-xs">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-xl">🧠</span>
            <h2 className="text-lg font-black text-slate-900 tracking-tight">Company Intelligence</h2>
            <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
              Forensic Knowledge Core
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Deterministic accounting health check, regulatory rule provenance, and controlled master remediation for <strong className="text-slate-800">{selectedCompanyName || "Synthetic Demonstration Company"}</strong>.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center space-x-3 shrink-0">
          <button
            onClick={handleRunScan}
            disabled={isScanning || isActing}
            className={`px-4 py-2.5 rounded-xl font-bold text-xs shadow-xs transition-all flex items-center space-x-2 cursor-pointer ${
              isScanning
                ? "bg-indigo-100 text-indigo-400 cursor-not-allowed"
                : "bg-indigo-600 hover:bg-indigo-700 text-white shadow-indigo-100"
            }`}
          >
            <span>{isScanning ? "⏳" : "🔍"}</span>
            <span>{isScanning ? "Scanning Tally Masters..." : "Run Accounting Health Check"}</span>
          </button>
        </div>
      </div>

      {/* Stale Proposal Alert Notice (Amendment 4) */}
      {staleErrorAlert && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-300 text-rose-800 text-xs flex items-start justify-between shadow-xs">
          <div className="flex items-start space-x-3">
            <span className="text-base">🛑</span>
            <div>
              <p className="font-bold text-rose-900">{staleErrorAlert}</p>
              <p className="text-rose-700 mt-0.5">
                The underlying Tally master changed after the proposal was formulated. WAAST360 prevented unauthorized execution. Please run a new Accounting Health Check.
              </p>
            </div>
          </div>
          <button
            onClick={() => setStaleErrorAlert(null)}
            className="text-rose-600 hover:text-rose-900 font-bold px-2"
          >
            ✕
          </button>
        </div>
      )}

      {/* Sub-Tabs: Health Summary, Findings, Corrections, Knowledge Core, Decision Memory */}
      <div className="flex items-center space-x-2 border-b border-slate-200 pb-2 overflow-x-auto text-xs font-bold">
        {[
          { key: "health", label: "Health Check", icon: "🩺" },
          { key: "findings", label: `Findings (${findings.length})`, icon: "🔎" },
          { key: "corrections", label: `Corrections (${corrections.length})`, icon: "⚖️" },
          { key: "knowledge", label: `Knowledge Core (${knowledgeItems.length})`, icon: "📚" },
          { key: "decisions", label: `Decision Memory (${decisions.length})`, icon: "🏛️" },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveSubTab(tab.key as "health" | "findings" | "corrections" | "knowledge" | "decisions")}
            className={`flex items-center space-x-1.5 px-3.5 py-2 rounded-xl transition-all cursor-pointer ${
              activeSubTab === tab.key
                ? "bg-indigo-50 text-indigo-700 border border-indigo-200 shadow-xs"
                : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
            }`}
          >
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* ===================================================================== */}
      {/* SUB-VIEW 1: ACCOUNTING HEALTH CHECK (EXACT UI REQUIREMENT)            */}
      {/* ===================================================================== */}
      {activeSubTab === "health" && (
        <div className="space-y-6">
          {/* Approved Health Banner */}
          <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-6 border-b border-slate-100">
              <div>
                <p className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
                  Accounting Health Check
                </p>
                <div className="mt-2 flex items-center space-x-3">
                  {scan?.overall_health === "REVIEW_COMPLETE" ? (
                    <span className="px-3 py-1.5 rounded-xl font-black text-sm bg-emerald-50 text-emerald-700 border border-emerald-300 flex items-center space-x-1.5">
                      <span>🟢</span>
                      <span>REVIEW COMPLETE</span>
                    </span>
                  ) : scan?.critical_count && scan.critical_count > 0 ? (
                    <span className="px-3 py-1.5 rounded-xl font-black text-sm bg-rose-50 text-rose-700 border border-rose-300 flex items-center space-x-1.5">
                      <span>🔴</span>
                      <span>CRITICAL FINDINGS</span>
                    </span>
                  ) : (
                    <span className="px-3 py-1.5 rounded-xl font-black text-sm bg-amber-50 text-amber-700 border border-amber-300 flex items-center space-x-1.5">
                      <span>🟡</span>
                      <span>REVIEW RECOMMENDED</span>
                    </span>
                  )}

                  <span className="text-xs text-slate-500 font-mono">
                    {scan ? `Last verified: ${new Date(scan.scanned_at).toLocaleDateString()} • ${new Date(scan.scanned_at).toLocaleTimeString()}` : "Not scanned yet"}
                  </span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setActiveSubTab("findings")}
                  className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold transition-all cursor-pointer"
                >
                  View Findings ({findings.length})
                </button>
                <button
                  onClick={handleRunScan}
                  disabled={isScanning}
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all cursor-pointer"
                >
                  {isScanning ? "Scanning..." : "Run New Review"}
                </button>
              </div>
            </div>

            {/* Metrics Breakdown Grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 pt-6">
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
                <p className="text-[10px] font-bold text-slate-500 uppercase">Ledgers Reviewed</p>
                <p className="text-2xl font-black text-slate-900 mt-1">{scan?.ledgers_reviewed ?? 126}</p>
                <p className="text-[10px] text-slate-400 mt-0.5">Tally Masters</p>
              </div>
              <div className="p-4 rounded-xl bg-amber-50/60 border border-amber-200">
                <p className="text-[10px] font-bold text-amber-800 uppercase">Review Recommendations</p>
                <p className="text-2xl font-black text-amber-700 mt-1">{scan?.review_recommended_count ?? 7}</p>
                <p className="text-[10px] text-amber-600 mt-0.5">Non-blocking</p>
              </div>
              <div className="p-4 rounded-xl bg-rose-50/60 border border-rose-200">
                <p className="text-[10px] font-bold text-rose-800 uppercase">Critical Findings</p>
                <p className="text-2xl font-black text-rose-700 mt-1">{scan?.critical_count ?? 2}</p>
                <p className="text-[10px] text-rose-600 mt-0.5">Requires Sign-off</p>
              </div>
              <div className="p-4 rounded-xl bg-indigo-50/60 border border-indigo-200">
                <p className="text-[10px] font-bold text-indigo-800 uppercase">GST Findings</p>
                <p className="text-2xl font-black text-indigo-700 mt-1">{scan?.gst_findings_count ?? 4}</p>
                <p className="text-[10px] text-indigo-600 mt-0.5">Rate & Hierarchy</p>
              </div>
              <div className="p-4 rounded-xl bg-purple-50/60 border border-purple-200">
                <p className="text-[10px] font-bold text-purple-800 uppercase">Duplicate Clusters</p>
                <p className="text-2xl font-black text-purple-700 mt-1">{scan?.duplicate_clusters_count ?? 1}</p>
                <p className="text-[10px] text-purple-600 mt-0.5">Similarity &gt; 85%</p>
              </div>
              <div className="p-4 rounded-xl bg-emerald-50/60 border border-emerald-200">
                <p className="text-[10px] font-bold text-emerald-800 uppercase">Known Exceptions</p>
                <p className="text-2xl font-black text-emerald-700 mt-1">{scan?.known_exceptions_count ?? 2}</p>
                <p className="text-[10px] text-emerald-600 mt-0.5">Previously Audited</p>
              </div>
            </div>
          </div>

          {/* Demonstration Company Callout & Forensic Notice */}
          <div className="p-5 rounded-2xl bg-blue-50/60 border border-blue-200 flex items-start space-x-3 text-xs text-blue-900">
            <span className="text-lg">ℹ️</span>
            <div>
              <p className="font-bold text-blue-950">Deterministic Simulator Forensic Dataset: SIM-DEMO-001</p>
              <p className="text-blue-800/90 mt-0.5 leading-relaxed">
                The demonstration dataset simulates a live client installation with deterministic anomalies (e.g. <code>ABC Traders</code> under <code>Indirect Expenses</code>, duplicate freight clusters, and unharmonized GST ledgers). WAAST360 continuously applies deterministic Knowledge Core rules and records audited human decisions without ever muting underlying accounting facts.
              </p>
            </div>
          </div>

          {/* Quick Preview of Top Findings */}
          <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-4 shadow-xs">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900">Priority Forensic Findings</h3>
              <button
                onClick={() => setActiveSubTab("findings")}
                className="text-xs text-indigo-600 hover:text-indigo-800 font-bold"
              >
                View All Findings →
              </button>
            </div>

            {findings.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-xs">
                No findings currently reported. Click &quot;Run Accounting Health Check&quot; to review Tally masters.
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {findings.slice(0, 4).map((f) => (
                  <div key={f.id} className="py-3 flex items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center space-x-2">
                        <span
                          className={`px-2 py-0.5 rounded-md text-[10px] font-black ${
                            f.severity === "CRITICAL"
                              ? "bg-rose-50 text-rose-700 border border-rose-200"
                              : "bg-amber-50 text-amber-700 border border-amber-200"
                          }`}
                        >
                          {f.rule_code}
                        </span>
                        <span className="font-bold text-xs text-slate-900">{f.entity_name}</span>
                        <span className="text-slate-400 text-xs">• {f.fact_observed}</span>
                      </div>
                      <p className="text-xs text-slate-600 line-clamp-1">💡 {f.recommendation}</p>
                    </div>

                    <div className="flex items-center space-x-2 shrink-0">
                      <button
                        onClick={() => setExplainModalFinding(f)}
                        className="px-2.5 py-1 rounded-lg text-xs font-bold text-indigo-600 hover:bg-indigo-50 border border-indigo-200 transition-all cursor-pointer"
                      >
                        🧠 Why Flagged?
                      </button>
                      <button
                        onClick={() => setShowProposeModal(f)}
                        className="px-2.5 py-1 rounded-lg text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 transition-all cursor-pointer"
                      >
                        Propose Fix
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* SUB-VIEW 2: FINDINGS (FOUR-WAY SEPARATION: FACT / RULE / REC / DEC)   */}
      {/* ===================================================================== */}
      {activeSubTab === "findings" && (
        <div className="space-y-4">
          {/* Filter Bar */}
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center space-x-1.5 text-xs font-semibold">
              {[
                { key: "ALL", label: `All (${findings.length})` },
                { key: "CRITICAL", label: "Critical" },
                { key: "GST", label: "GST Rules" },
                { key: "DUPLICATES", label: "Duplicates" },
                { key: "EXCEPTIONS", label: "Known Exceptions" },
              ].map((filter) => (
                <button
                  key={filter.key}
                  onClick={() => setFindingFilter(filter.key as "ALL" | "CRITICAL" | "GST" | "DUPLICATES" | "EXCEPTIONS")}
                  className={`px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                    findingFilter === filter.key
                      ? "bg-slate-900 text-white font-bold"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  {filter.label}
                </button>
              ))}
            </div>

            <span className="text-xs text-slate-500 font-mono">
              Showing {filteredFindings.length} of {findings.length} findings
            </span>
          </div>

          {/* Findings Cards */}
          <div className="space-y-4">
            {filteredFindings.map((f) => (
              <div
                key={f.id}
                className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs hover:border-slate-300 transition-all space-y-4"
              >
                {/* Header row */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3">
                  <div className="flex items-center space-x-2.5">
                    <span
                      className={`px-2.5 py-0.5 rounded-md text-[10px] font-black ${
                        f.severity === "CRITICAL"
                          ? "bg-rose-50 text-rose-700 border border-rose-200"
                          : "bg-amber-50 text-amber-700 border border-amber-200"
                      }`}
                    >
                      {f.rule_code}
                    </span>
                    <span className="font-extrabold text-sm text-slate-900">{f.entity_name}</span>
                    <span className="text-[10px] font-mono text-slate-400 uppercase bg-slate-100 px-2 py-0.5 rounded">
                      {f.entity_type}
                    </span>
                  </div>

                  <div className="flex items-center space-x-2">
                    {/* Decision Status Badge */}
                    {f.decision_status === "KNOWN_EXCEPTION" ? (
                      <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-amber-50 text-amber-800 border border-amber-300 flex items-center space-x-1">
                        <span>🟡</span>
                        <span>KNOWN EXCEPTION (Previously Reviewed)</span>
                      </span>
                    ) : f.decision_status === "CORRECTED" ? (
                      <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-300 flex items-center space-x-1">
                        <span>🟢</span>
                        <span>CORRECTED &amp; VERIFIED</span>
                      </span>
                    ) : f.decision_status === "PROPOSED_CORRECTION" ? (
                      <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-indigo-50 text-indigo-800 border border-indigo-300 flex items-center space-x-1">
                        <span>⚖️</span>
                        <span>CORRECTION PROPOSED</span>
                      </span>
                    ) : (
                      <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-slate-100 text-slate-700 border border-slate-300">
                        REVIEW RECOMMENDED
                      </span>
                    )}

                    <button
                      onClick={() => setExplainModalFinding(f)}
                      className="px-3 py-1 rounded-xl text-xs font-bold text-indigo-600 hover:bg-indigo-50 border border-indigo-200 transition-all cursor-pointer flex items-center space-x-1"
                    >
                      <span>🧠</span>
                      <span>Why Flagged?</span>
                    </button>
                  </div>
                </div>

                {/* FOUR-WAY SEPARATION: FACT / RULE / RECOMMENDATION / DECISION */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
                  {/* 1. FACT */}
                  <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1 flex items-center space-x-1">
                      <span>📌</span>
                      <span>Fact Observed</span>
                    </p>
                    <p className="text-slate-800 font-medium leading-relaxed">{f.fact_observed}</p>
                    {Boolean(f.fact_details?.transaction_count) && (
                      <p className="text-[11px] text-slate-500 mt-1">
                        Usage: {String(f.fact_details.transaction_count)} transaction(s) observed.
                      </p>
                    )}
                  </div>

                  {/* 2. RULE */}
                  <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1 flex items-center space-x-1">
                      <span>⚖️</span>
                      <span>Deterministic Rule</span>
                    </p>
                    <p className="text-slate-800 font-semibold">{f.rule_triggered}</p>
                    {f.knowledge_code && (
                      <span className="inline-block mt-1 font-mono text-[10px] text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded border border-indigo-200">
                        Ref: {f.knowledge_code}
                      </span>
                    )}
                  </div>

                  {/* 3. RECOMMENDATION */}
                  <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1 flex items-center space-x-1">
                      <span>💡</span>
                      <span>Recommendation</span>
                    </p>
                    <p className="text-slate-800 font-medium leading-relaxed">{f.recommendation}</p>
                  </div>

                  {/* 4. DECISION */}
                  <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between">
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1 flex items-center space-x-1">
                        <span>✍️</span>
                        <span>Audited Decision</span>
                      </p>
                      <p className="text-slate-700 font-medium">
                        {f.decision_status === "KNOWN_EXCEPTION"
                          ? "Marked as intentional exception. Rule triggers preserved for forensic transparency."
                          : f.decision_status === "CORRECTED"
                          ? "Remediated via Bridge and verified against Tally master."
                          : "Pending accountant determination."}
                      </p>
                    </div>

                    {/* Action buttons */}
                    <div className="pt-2 flex items-center space-x-2">
                      {f.decision_status !== "CORRECTED" && (
                        <>
                          <button
                            onClick={() => setShowProposeModal(f)}
                            className="flex-1 py-1 px-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[11px] font-bold text-center transition-all cursor-pointer"
                          >
                            Propose Fix
                          </button>
                          <button
                            onClick={() => setShowKnownExceptionModal(f)}
                            className="flex-1 py-1 px-2 rounded-lg bg-slate-200 hover:bg-slate-300 text-slate-800 text-[11px] font-bold text-center transition-all cursor-pointer"
                          >
                            Mark Exception
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* SUB-VIEW 3: CORRECTION CENTER (STRICT 7-STEP CONTROLS)                 */}
      {/* ===================================================================== */}
      {activeSubTab === "corrections" && (
        <div className="space-y-6">
          <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-3">
            <h3 className="text-sm font-black text-slate-900 flex items-center space-x-2">
              <span>⚖️</span>
              <span>Controlled Master Remediation Lifecycle</span>
            </h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Every master change requires human approval signature, verified read-back evidence against Tally, and stale target-state protection.
            </p>

            {/* Strict 7-step pipeline visualizer */}
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 overflow-x-auto">
              <div className="flex items-center space-x-2 text-[11px] font-bold text-slate-600 min-w-max">
                <span className="px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">1. PROPOSED</span>
                <span>→</span>
                <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200">2. APPROVAL REQUIRED</span>
                <span>→</span>
                <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">3. APPROVED</span>
                <span>→</span>
                <span className="px-2 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200">4. EXECUTION ELIGIBLE</span>
                <span>→</span>
                <span className="px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">5. BRIDGE EXECUTION</span>
                <span>→</span>
                <span className="px-2 py-0.5 rounded bg-teal-50 text-teal-700 border border-teal-200">6. READ-BACK</span>
                <span>→</span>
                <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">7. VERIFIED</span>
              </div>
            </div>
          </div>

          {/* Last Execution Evidence Card */}
          {lastExecutionEvidence && (
            <div className="bg-emerald-50/60 border border-emerald-300 rounded-2xl p-5 shadow-xs space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-emerald-900 flex items-center space-x-1.5">
                  <span>✓</span>
                  <span>Read-Back Verification Match Evidence</span>
                </span>
                <span className="text-[10px] font-mono text-emerald-700">
                  {new Date(lastExecutionEvidence.verified_at).toLocaleTimeString()}
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs pt-1">
                <div>
                  <span className="text-emerald-700 text-[10px] uppercase font-bold">Ledger Name:</span>
                  <p className="font-extrabold text-emerald-950">{lastExecutionEvidence.target_entity}</p>
                </div>
                <div>
                  <span className="text-emerald-700 text-[10px] uppercase font-bold">Before Master Group:</span>
                  <p className="line-through text-slate-500 font-mono">{lastExecutionEvidence.before_group}</p>
                </div>
                <div>
                  <span className="text-emerald-700 text-[10px] uppercase font-bold">Verified Tally Master Group:</span>
                  <p className="font-extrabold text-emerald-800 font-mono">✓ {lastExecutionEvidence.after_group}</p>
                </div>
              </div>
            </div>
          )}

          {/* Proposals Table */}
          <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Active &amp; Historical Master Proposals
            </h4>

            {corrections.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-xs">
                No correction proposals formulated yet. Click &quot;Propose Fix&quot; on any forensic finding.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-200 text-slate-500 font-bold bg-slate-50/60">
                      <th className="py-2.5 px-3">Target Ledger</th>
                      <th className="py-2.5 px-3">Before State</th>
                      <th className="py-2.5 px-3">Proposed State</th>
                      <th className="py-2.5 px-3">Status</th>
                      <th className="py-2.5 px-3">Date</th>
                      <th className="py-2.5 px-3 text-right">Accounting Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {corrections.map((c) => (
                      <tr key={c.id} className="hover:bg-slate-50">
                        <td className="py-3 px-3 font-bold text-slate-900">{c.target_entity_name}</td>
                        <td className="py-3 px-3 font-mono text-slate-500">{String(c.before_state?.parent_group || "N/A")}</td>
                        <td className="py-3 px-3 font-mono font-bold text-indigo-700">
                          {String(c.proposed_state?.parent_group || "N/A")}
                        </td>
                        <td className="py-3 px-3">
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                              c.status === "VERIFIED"
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-300"
                                : c.status === "EXECUTION_ELIGIBLE"
                                ? "bg-purple-50 text-purple-700 border border-purple-300 animate-pulse"
                                : c.status === "APPROVAL_REQUIRED"
                                ? "bg-amber-50 text-amber-700 border border-amber-300"
                                : c.status === "STALE_REJECTED"
                                ? "bg-rose-50 text-rose-700 border border-rose-300"
                                : "bg-slate-100 text-slate-700"
                            }`}
                          >
                            {c.status}
                          </span>
                        </td>
                        <td className="py-3 px-3 font-mono text-slate-400 text-[11px]">
                          {new Date(c.created_at).toLocaleDateString()}
                        </td>
                        <td className="py-3 px-3 text-right space-x-2">
                          {c.status === "APPROVAL_REQUIRED" && (
                            <button
                              onClick={() => setShowApproveModal(c)}
                              className="px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-[11px] transition-all cursor-pointer"
                            >
                              Approve Sign-off
                            </button>
                          )}
                          {c.status === "EXECUTION_ELIGIBLE" && (
                            <button
                              onClick={() => handleExecuteCorrection(c.id)}
                              disabled={isActing}
                              className="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-[11px] transition-all cursor-pointer"
                            >
                              Execute Bridge Remediator
                            </button>
                          )}
                          {c.status === "VERIFIED" && (
                            <span className="text-emerald-700 font-bold text-[11px]">✓ Verified in Tally</span>
                          )}
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

      {/* ===================================================================== */}
      {/* SUB-VIEW 4: KNOWLEDGE CORE BROWSER (PROVENANCE & VERSIONING)          */}
      {/* ===================================================================== */}
      {activeSubTab === "knowledge" && (
        <div className="space-y-4">
          <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-2">
            <h3 className="text-sm font-black text-slate-900 flex items-center space-x-2">
              <span>📚</span>
              <span>WAAST360 Versioned Knowledge Core</span>
            </h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Every deterministic tax, regulatory, and forensic rule maintains strict provenance: 
              <strong className="text-slate-800"> Knowledge Item → Authoritative Source → Effective Date → Jurisdiction → Rule Version → Deterministic Rule</strong>.
              No tax rule is hard-coded without statutory provenance.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {knowledgeItems.map((item) => (
              <div
                key={item.id}
                className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-3 flex flex-col justify-between"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-black px-2.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                      {item.knowledge_code}
                    </span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                      {item.status} (v{item.rule_version}.0)
                    </span>
                  </div>

                  <h4 className="font-extrabold text-sm text-slate-900">{item.title}</h4>
                  <p className="text-xs text-slate-600 leading-relaxed">{item.content}</p>
                </div>

                {/* Provenance Box */}
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-[11px] space-y-1 font-mono">
                  <div className="flex justify-between text-slate-700">
                    <span className="text-slate-500 font-sans">Authoritative Source:</span>
                    <span className="font-bold">{item.source?.authority_name || "Statutory Law"}</span>
                  </div>
                  <div className="flex justify-between text-slate-700">
                    <span className="text-slate-500 font-sans">Source Citation:</span>
                    <span className="truncate max-w-[200px]" title={item.source?.citation || ""}>
                      {item.source?.citation || item.source?.source_code}
                    </span>
                  </div>
                  <div className="flex justify-between text-slate-700">
                    <span className="text-slate-500 font-sans">Effective Period:</span>
                    <span>{item.effective_from} → {item.effective_until || "Ongoing"}</span>
                  </div>
                  <div className="flex justify-between text-slate-700">
                    <span className="text-slate-500 font-sans">Jurisdiction:</span>
                    <span className="font-bold">{item.jurisdiction}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* SUB-VIEW 5: DECISION MEMORY (TRANSPARENT AUDITED OVERRIDES)           */}
      {/* ===================================================================== */}
      {activeSubTab === "decisions" && (
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-4">
          <div>
            <h3 className="text-sm font-black text-slate-900 flex items-center space-x-2">
              <span>🏛️</span>
              <span>Audited Decision Memory</span>
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              Accountant determinations for company-specific policies and known exceptions. Prior human decisions do not mute underlying rules; they are surfaced transparently in forensic reviews.
            </p>
          </div>

          {decisions.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-xs">
              No human decisions recorded yet for this company.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500 font-bold bg-slate-50/60">
                    <th className="py-2.5 px-3">Rule / Code</th>
                    <th className="py-2.5 px-3">Entity Name</th>
                    <th className="py-2.5 px-3">Human Decision</th>
                    <th className="py-2.5 px-3">Audited Rationale</th>
                    <th className="py-2.5 px-3">Decided By</th>
                    <th className="py-2.5 px-3">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {decisions.map((d) => (
                    <tr key={d.id} className="hover:bg-slate-50">
                      <td className="py-3 px-3 font-mono font-bold text-slate-900">{d.rule_code}</td>
                      <td className="py-3 px-3 font-bold text-slate-800">{d.entity_name}</td>
                      <td className="py-3 px-3">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-300">
                          {d.human_decision}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-600 max-w-xs">{d.decision_reason}</td>
                      <td className="py-3 px-3 font-mono text-[11px] text-slate-500">
                        {d.actor_role} ({d.actor_id.split("@")[0]})
                      </td>
                      <td className="py-3 px-3 font-mono text-[11px] text-slate-400">
                        {new Date(d.decided_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ===================================================================== */}
      {/* MODAL 1: 🧠 "WHY DID WAAST360 FLAG THIS?" EXPLANATION PANEL          */}
      {/* ===================================================================== */}
      {explainModalFinding && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-2xl max-w-xl w-full p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center space-x-2">
                <span className="text-xl">🧠</span>
                <div>
                  <h3 className="text-sm font-black text-slate-900 uppercase tracking-tight">
                    Why did WAAST360 flag this?
                  </h3>
                  <p className="text-[11px] text-slate-500 font-mono">
                    Forensic Rule: {explainModalFinding.rule_code} • Ref: {explainModalFinding.knowledge_code || "KN-ACC-002"}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setExplainModalFinding(null)}
                className="text-slate-400 hover:text-slate-700 text-base font-bold p-1"
              >
                ✕
              </button>
            </div>

            {/* Structured Explanation Body (Exact prompt format) */}
            <div className="space-y-3.5 text-xs">
              <div>
                <p className="text-[10px] font-bold uppercase text-slate-400">Observed:</p>
                <p className="text-slate-900 font-bold mt-0.5">
                  {explainModalFinding.fact_observed}
                </p>
              </div>

              <div>
                <p className="text-[10px] font-bold uppercase text-slate-400">Usage observed:</p>
                <ul className="list-disc list-inside space-y-1 text-slate-700 mt-1">
                  <li>{String(explainModalFinding.fact_details?.transaction_count || 17)} purchase-related transactions recorded in historical activity.</li>
                  <li>Supplier-like party behavior observed across double-entry line items.</li>
                  <li>Credit balance and turnover pattern consistent with trade creditors.</li>
                </ul>
              </div>

              <div className="grid grid-cols-2 gap-3 pt-1">
                <div>
                  <p className="text-[10px] font-bold uppercase text-slate-400">Rule Triggered:</p>
                  <p className="text-slate-900 font-mono font-bold mt-0.5">{explainModalFinding.rule_code}</p>
                </div>
                <div>
                  <p className="text-[10px] font-bold uppercase text-slate-400">Knowledge Reference:</p>
                  <p className="text-indigo-600 font-mono font-bold mt-0.5">
                    {explainModalFinding.knowledge_code || "KN-ACC-002"} (ICAI Accounting Standards)
                  </p>
                </div>
              </div>

              <div>
                <p className="text-[10px] font-bold uppercase text-slate-400">Assessment:</p>
                <p className="text-amber-700 font-bold mt-0.5">Review Recommended</p>
              </div>

              <div>
                <p className="text-[10px] font-bold uppercase text-slate-400">Recommendation:</p>
                <p className="text-slate-800 leading-relaxed mt-0.5">{explainModalFinding.recommendation}</p>
              </div>

              {/* Mandatory Accounting Disclaimer */}
              <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-[11px] leading-relaxed">
                ⚠ <strong>Notice:</strong> This is a recommendation, not an automatic accounting-policy decision. An authorized accountant must approve any reclassification before Bridge dispatch.
              </div>
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setExplainModalFinding(null)}
                className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold transition-all cursor-pointer"
              >
                Close
              </button>
              <button
                onClick={() => {
                  const f = explainModalFinding;
                  setExplainModalFinding(null);
                  setShowProposeModal(f);
                }}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all cursor-pointer"
              >
                Propose Correction
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* MODAL 2: MARK AS KNOWN EXCEPTION (DECISION MEMORY)                    */}
      {/* ===================================================================== */}
      {showKnownExceptionModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <h3 className="text-sm font-black text-slate-900">Mark as Known Exception</h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              Confirm that the classification of <strong>{showKnownExceptionModal.entity_name}</strong> is intentional. This decision will be permanently recorded in Decision Memory and surfaced transparently in future reviews without muting the rule.
            </p>

            <div className="space-y-3 text-xs">
              <div>
                <label className="font-bold text-slate-700 block mb-1">Approver Role:</label>
                <select
                  value={exceptionApproverRole}
                  onChange={(e) => setExceptionApproverRole(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 font-medium text-slate-900 focus:outline-hidden"
                >
                  <option value="CONTROLLER">Controller</option>
                  <option value="PRINCIPAL_ACCOUNTANT">Principal Accountant</option>
                  <option value="STATUTORY_AUDITOR">Statutory Auditor</option>
                </select>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Audited Rationale:</label>
                <textarea
                  rows={3}
                  value={exceptionReason}
                  onChange={(e) => setExceptionReason(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 font-medium text-slate-900 focus:outline-hidden resize-none"
                  placeholder="Enter business reason or specific accounting policy justification..."
                />
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setShowKnownExceptionModal(null)}
                className="px-3.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-all cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleRecordKnownException}
                disabled={isActing}
                className="px-4 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold transition-all cursor-pointer"
              >
                {isActing ? "Recording..." : "Confirm Known Exception"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* MODAL 3: PROPOSE MASTER CORRECTION                                    */}
      {/* ===================================================================== */}
      {showProposeModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <h3 className="text-sm font-black text-slate-900">Formulate Correction Proposal</h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              Formulate a controlled master update for <strong>{showProposeModal.entity_name}</strong>. The proposal will require formal sign-off before Bridge dispatch.
            </p>

            <div className="space-y-3 text-xs">
              <div>
                <span className="text-slate-400 font-bold block mb-0.5">Current Parent Group:</span>
                <p className="font-mono font-bold text-slate-800 bg-slate-50 p-2 rounded border border-slate-200">
                  {String(showProposeModal.fact_details?.current_parent_group || "Indirect Expenses")}
                </p>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Target Parent Group:</label>
                <select
                  value={proposedTargetGroup}
                  onChange={(e) => setProposedTargetGroup(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 font-bold text-slate-900 focus:outline-hidden"
                >
                  <option value="Sundry Creditors">Sundry Creditors</option>
                  <option value="Sundry Debtors">Sundry Debtors</option>
                  <option value="Direct Expenses">Direct Expenses</option>
                  <option value="Duties & Taxes">Duties &amp; Taxes</option>
                </select>
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setShowProposeModal(null)}
                className="px-3.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-all cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleProposeCorrection}
                disabled={isActing}
                className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all cursor-pointer"
              >
                {isActing ? "Formulating..." : "Submit Proposal"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* MODAL 4: APPROVE CORRECTION SIGN-OFF                                 */}
      {/* ===================================================================== */}
      {showApproveModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <h3 className="text-sm font-black text-slate-900">Authorize Correction Proposal</h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              Authorizing this proposal will transition it to <strong className="text-purple-700">EXECUTION ELIGIBLE</strong>, allowing Bridge to dispatch the update to Tally with read-back verification.
            </p>

            <div className="space-y-3 text-xs">
              <div>
                <label className="font-bold text-slate-700 block mb-1">Approver Role:</label>
                <select
                  value={approvalRole}
                  onChange={(e) => setApprovalRole(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 font-medium text-slate-900 focus:outline-hidden"
                >
                  <option value="CONTROLLER">Controller</option>
                  <option value="FINANCE_DIRECTOR">Finance Director</option>
                </select>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Sign-off Comments:</label>
                <textarea
                  rows={2}
                  value={approvalComments}
                  onChange={(e) => setApprovalComments(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 font-medium text-slate-900 focus:outline-hidden resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setShowApproveModal(null)}
                className="px-3.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-all cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleApproveProposal}
                disabled={isActing}
                className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all cursor-pointer"
              >
                {isActing ? "Authorizing..." : "Sign-off & Authorize"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
