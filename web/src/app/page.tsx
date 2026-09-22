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

export default function CompanyDiscoveryDashboard() {
  const [bridgeStatus, setBridgeStatus] = useState<BridgeStatus | null>(null);
  const [tallyCompanies, setTallyCompanies] = useState<TallyCompanyItem[]>([]);
  const [waastCompanies, setWaastCompanies] = useState<CompanyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionMessage, setActionMessage] = useState<{ text: string; type: "success" | "error" | "info" } | null>(null);
  
  // Mapping modal state
  const [selectedTallyComp, setSelectedTallyComp] = useState<TallyCompanyItem | null>(null);
  const [selectedWaastCompId, setSelectedWaastCompId] = useState<string>("");
  const [showCreateModal, setShowCreateModal] = useState(false);

  // New company form
  const [newCompanyName, setNewCompanyName] = useState("");
  const [newPan, setNewPan] = useState("");
  const [newGstin, setNewGstin] = useState("");

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
      }
    } catch {
      showNotification("Could not reach WAAST360 Cloud API on port 8000. Ensure API server is running.", "error");
    } finally {
      setLoading(false);
    }
  }, [API_BASE]);

  useEffect(() => {
    let ignore = false;
    const fetchInitial = async () => {
      try {
        const [statusRes, tallyRes, compRes] = await Promise.allSettled([
          fetch(`${API_BASE}/bridge/status`).then((r) => (r.ok ? r.json() : null)),
          fetch(`${API_BASE}/tally-companies`).then((r) => (r.ok ? r.json() : [])),
          fetch(`${API_BASE}/companies`).then((r) => (r.ok ? r.json() : [])),
        ]);
        if (!ignore) {
          if (statusRes.status === "fulfilled" && statusRes.value) {
            setBridgeStatus(statusRes.value);
          }
          if (tallyRes.status === "fulfilled" && Array.isArray(tallyRes.value)) {
            setTallyCompanies(tallyRes.value);
          }
          if (compRes.status === "fulfilled" && Array.isArray(compRes.value)) {
            setWaastCompanies(compRes.value);
          }
        }
      } catch {
        // Handled gracefully
      }
    };

    fetchInitial();
    const interval = setInterval(fetchInitial, 5000);
    return () => {
      ignore = true;
      clearInterval(interval);
    };
  }, [API_BASE]);


  // Handle 1-Click Quick Map
  const handleQuickCreateAndMap = async (tc: TallyCompanyItem) => {
    try {
      const res = await fetch(`${API_BASE}/tally-companies/${tc.id}/create-and-map`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Failed to auto-create and map company");
      showNotification(`Successfully mapped Tally Company "${tc.company_name}" to new WAAST360 Company`, "success");
      loadData();
    } catch (e: unknown) {
      showNotification((e as Error).message, "error");
    }
  };

  // Handle Manual Mapping
  const handleManualMap = async () => {
    if (!selectedTallyComp || !selectedWaastCompId) return;
    try {
      const res = await fetch(`${API_BASE}/companies/${selectedWaastCompId}/map-tally/${selectedTallyComp.id}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Failed to associate Tally Company");
      showNotification(`Associated "${selectedTallyComp.company_name}" successfully!`, "success");
      setSelectedTallyComp(null);
      setSelectedWaastCompId("");
      loadData();
    } catch (e: unknown) {
      showNotification((e as Error).message, "error");
    }
  };

  // Handle Create WAAST360 Company
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
          pan: newPan || null,
          gstin: newGstin || null,
        }),
      });
      if (!res.ok) throw new Error("Failed to create WAAST360 Company");
      showNotification(`Created WAAST360 Company "${newCompanyName}"`, "success");
      setNewCompanyName("");
      setNewPan("");
      setNewGstin("");
      setShowCreateModal(false);
      loadData();
    } catch (err: unknown) {
      showNotification((err as Error).message, "error");
    }
  };

  const isTallyOnline = bridgeStatus?.tally_online ?? false;
  const isBridgeConnected = bridgeStatus?.bridge_connected ?? false;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-indigo-500 selection:text-white pb-16">
      {/* Top Ambient Glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-48 bg-gradient-to-b from-indigo-500/10 via-cyan-500/5 to-transparent blur-3xl pointer-events-none" />

      {/* Navigation Bar */}
      <header className="sticky top-0 z-50 backdrop-blur-md bg-slate-950/80 border-b border-slate-800/80 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 p-[1px] shadow-lg shadow-indigo-500/20">
              <div className="h-full w-full bg-slate-950 rounded-[11px] flex items-center justify-center font-black text-indigo-400 text-lg tracking-wider">
                W
              </div>
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-xl tracking-tight text-white">WAAST360</span>
                <span className="text-xs px-2 py-0.5 rounded-full font-semibold uppercase tracking-wider bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  Lite / Phase 2D
                </span>
              </div>
              <p className="text-xs text-slate-400">Wise Accounting Automation System for Tally</p>
            </div>
          </div>

          {/* Right Status Badges */}
          <div className="flex items-center space-x-3">
            {/* Bridge Status Pill */}
            <div className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs">
              <span className={`h-2 w-2 rounded-full ${isBridgeConnected ? "bg-emerald-400 animate-pulse" : "bg-amber-400"}`} />
              <span className="text-slate-400">Bridge Agent:</span>
              <span className="font-semibold text-slate-200">
                {isBridgeConnected ? bridgeStatus?.bridge_client_id : "Awaiting Agent"}
              </span>
            </div>

            {/* Tally Connectivity Pill */}
            <div className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs">
              <span className={`h-2 w-2 rounded-full ${isTallyOnline ? "bg-emerald-400 animate-pulse" : "bg-rose-500"}`} />
              <span className="text-slate-400">Tally localhost:9000:</span>
              <span className={`font-semibold ${isTallyOnline ? "text-emerald-400" : "text-rose-400"}`}>
                {isTallyOnline ? "Connected" : "Not Responding"}
              </span>
            </div>

            <button
              onClick={loadData}
              disabled={loading}
              className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white transition shadow-sm hover:shadow-indigo-500/20 disabled:opacity-50"
            >
              {loading ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Container */}
      <main className="max-w-7xl mx-auto px-6 pt-8 space-y-8 relative">
        {/* Toast Notification */}
        {actionMessage && (
          <div
            className={`fixed bottom-6 right-6 z-50 px-4 py-3 rounded-xl border shadow-xl backdrop-blur-md transition-all ${
              actionMessage.type === "success"
                ? "bg-emerald-950/90 border-emerald-500/30 text-emerald-200"
                : actionMessage.type === "error"
                ? "bg-rose-950/90 border-rose-500/30 text-rose-200"
                : "bg-slate-900/90 border-slate-700 text-slate-200"
            }`}
          >
            <div className="flex items-center space-x-2 text-sm font-medium">
              <span>{actionMessage.text}</span>
            </div>
          </div>
        )}

        {/* Hero Architectural Flow Banner */}
        <section className="p-6 rounded-2xl bg-gradient-to-r from-slate-900/90 via-slate-900/60 to-indigo-950/30 border border-slate-800/80 shadow-2xl relative overflow-hidden">
          <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
            <div className="space-y-2 max-w-xl">
              <div className="inline-flex items-center space-x-2 text-xs font-semibold text-indigo-400 uppercase tracking-wider">
                <span className="px-2 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20">Phase 2D Proven</span>
                <span>Explicit Separation Topology</span>
              </div>
              <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
                Company Discovery & Mapping Engine
              </h1>
              <p className="text-sm text-slate-400 leading-relaxed">
                Preserves strict architectural isolation:{" "}
                <strong className="text-slate-200">TallyInstance</strong> (Host/Port Runtime) ≠{" "}
                <strong className="text-slate-200">TallyCompany</strong> (Native Tally Identity &amp; GUID) ≠{" "}
                <strong className="text-slate-200">WAAST360 Company</strong> (Internal Accounting Entity).
              </p>
            </div>

            {/* Topology Interactive Badges */}
            <div className="flex flex-wrap items-center gap-3">
              <div className="px-4 py-3 rounded-xl bg-slate-950/80 border border-slate-800 text-left">
                <div className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">Layer 1: Runtime</div>
                <div className="text-sm font-bold text-slate-200">TallyInstance</div>
                <div className="text-xs text-slate-400">127.0.0.1:9000</div>
              </div>

              <div className="text-slate-600 font-bold">→</div>

              <div className="px-4 py-3 rounded-xl bg-slate-950/80 border border-slate-800 text-left">
                <div className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">Layer 2: Discovered</div>
                <div className="text-sm font-bold text-indigo-400">TallyCompany</div>
                <div className="text-xs text-slate-400">{tallyCompanies.length} Discovered</div>
              </div>

              <div className="text-slate-600 font-bold">→</div>

              <div className="px-4 py-3 rounded-xl bg-slate-950/80 border border-slate-800 text-left">
                <div className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">Layer 3: WAAST360</div>
                <div className="text-sm font-bold text-emerald-400">Company</div>
                <div className="text-xs text-slate-400">{waastCompanies.length} Registered</div>
              </div>
            </div>
          </div>
        </section>

        {/* Live Diagnostics Card if Tally is offline */}
        {!isTallyOnline && (
          <section className="p-5 rounded-xl bg-amber-950/20 border border-amber-500/30 text-amber-200 space-y-3">
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-3">
                <span className="flex h-3 w-3 rounded-full bg-amber-400 animate-ping" />
                <h3 className="font-semibold text-sm text-amber-100">Live Tally Connection on localhost:9000</h3>
              </div>
              <span className="text-xs font-mono bg-amber-900/40 px-2 py-0.5 rounded text-amber-300">
                Action Required
              </span>
            </div>
            <p className="text-xs text-amber-200/80 leading-relaxed">
              TallyPrime is currently not responding on port 9000. To perform live discovery against a running TallyPrime instance:
            </p>
            <ol className="list-decimal list-inside text-xs text-amber-200/90 space-y-1 font-mono bg-amber-950/40 p-3 rounded-lg border border-amber-800/40">
              <li>Launch TallyPrime on this machine.</li>
              <li>Press <strong>F12 (Configure)</strong> → <strong>Advanced Configuration</strong>.</li>
              <li>Set <strong>Tally is acting as: Both</strong> (or Server) and set <strong>Port: 9000</strong>.</li>
              <li>Load your target company in TallyPrime.</li>
              <li>Run: <code className="text-amber-300 font-bold">python bridge/src/main.py discover</code> or start the Bridge daemon.</li>
            </ol>
          </section>
        )}

        {/* Main 2-Column Split: Discovered Tally Companies vs Registered WAAST360 Companies */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Column 1: Discovered Tally Companies (7 cols) */}
          <div className="lg:col-span-7 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-white flex items-center space-x-2">
                  <span>Discovered Tally Companies</span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                    {tallyCompanies.length}
                  </span>
                </h2>
                <p className="text-xs text-slate-400">Companies discovered live via Bridge from Tally Instance</p>
              </div>
            </div>

            {tallyCompanies.length === 0 ? (
              <div className="p-8 rounded-xl bg-slate-900/40 border border-slate-800/80 text-center space-y-3">
                <div className="text-slate-600 text-3xl">🏢</div>
                <h4 className="text-sm font-semibold text-slate-300">No Tally Companies Discovered Yet</h4>
                <p className="text-xs text-slate-500 max-w-sm mx-auto">
                  Run <code className="text-indigo-400">python bridge/src/main.py discover</code> or start the Bridge daemon to query TallyPrime and synchronize loaded companies.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {tallyCompanies.map((tc) => {
                  const isMapped = tc.status === "MAPPED";
                  return (
                    <div
                      key={tc.id}
                      className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition space-y-3"
                    >
                      <div className="flex items-start justify-between">
                        <div className="space-y-1">
                          <div className="flex items-center space-x-2">
                            <span className="font-bold text-slate-100 text-base">{tc.company_name}</span>
                            <span
                              className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full border ${
                                isMapped
                                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                                  : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                              }`}
                            >
                              {tc.status}
                            </span>
                          </div>
                          <div className="flex items-center space-x-3 text-xs text-slate-400 font-mono">
                            <span>GUID: {tc.tally_guid}</span>
                            {tc.financial_year && <span>• FY: {tc.financial_year}</span>}
                            {tc.books_from && <span>• Books: {tc.books_from}</span>}
                          </div>
                        </div>

                        {/* Actions */}
                        <div className="flex items-center space-x-2">
                          {!isMapped ? (
                            <>
                              <button
                                onClick={() => handleQuickCreateAndMap(tc)}
                                className="px-3 py-1.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 text-xs font-semibold transition"
                              >
                                1-Click Quick Map
                              </button>
                              <button
                                onClick={() => setSelectedTallyComp(tc)}
                                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold transition"
                              >
                                Link to Existing
                              </button>
                            </>
                          ) : (
                            <span className="text-xs text-emerald-400 font-medium flex items-center space-x-1">
                              <span>✓ Mapped &amp; Ready</span>
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Column 2: WAAST360 Registered Companies (5 cols) */}
          <div className="lg:col-span-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-white flex items-center space-x-2">
                  <span>WAAST360 Companies</span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    {waastCompanies.length}
                  </span>
                </h2>
                <p className="text-xs text-slate-400">Internal Accounting Entities &amp; Ledgers</p>
              </div>
              <button
                onClick={() => setShowCreateModal(true)}
                className="px-3 py-1.5 rounded-lg bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 border border-indigo-500/30 text-xs font-semibold transition"
              >
                + New Company
              </button>
            </div>

            {waastCompanies.length === 0 ? (
              <div className="p-8 rounded-xl bg-slate-900/40 border border-slate-800/80 text-center space-y-3">
                <div className="text-slate-600 text-3xl">📋</div>
                <h4 className="text-sm font-semibold text-slate-300">No WAAST360 Companies</h4>
                <p className="text-xs text-slate-500">Create one or use 1-Click Quick Map from discovered Tally companies.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {waastCompanies.map((c) => (
                  <div
                    key={c.id}
                    className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition space-y-2"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <h4 className="font-bold text-slate-200 text-sm">{c.legal_name}</h4>
                        {c.trade_name && c.trade_name !== c.legal_name && (
                          <p className="text-xs text-slate-400">{c.trade_name}</p>
                        )}
                        <div className="text-xs text-slate-500 font-mono mt-1">
                          {c.gstin ? `GSTIN: ${c.gstin}` : c.pan ? `PAN: ${c.pan}` : "No Tax IDs"}
                        </div>
                      </div>
                    </div>

                    {/* Mapping Indicator */}
                    <div className="pt-2 border-t border-slate-800/60 flex items-center justify-between text-xs">
                      <span className="text-slate-500">Mapped Tally:</span>
                      {c.mapped_tally_company_name ? (
                        <span className="font-semibold text-emerald-400">
                          {c.mapped_tally_company_name}
                        </span>
                      ) : (
                        <span className="text-amber-400/80 italic">Unmapped</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Modal: Map Discovered Tally Company to WAAST360 Company */}
        {selectedTallyComp && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
            <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4">
              <h3 className="text-lg font-bold text-white">Map Tally Company</h3>
              <p className="text-xs text-slate-400">
                Link <strong className="text-indigo-400">{selectedTallyComp.company_name}</strong> to a WAAST360 accounting entity.
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

        {/* Modal: Create New WAAST360 Company */}
        {showCreateModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
            <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4">
              <h3 className="text-lg font-bold text-white">Create WAAST360 Company</h3>
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
