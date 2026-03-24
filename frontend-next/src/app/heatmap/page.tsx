"use client";

import React, { useEffect, useState } from "react";
import { LayoutGrid, List, X, ExternalLink } from "lucide-react";
import { ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";

export default function HeatmapPriorityPage() {
  const [opportunities, setOpportunities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<'table' | 'heatmap'>('table');
  
  // Selection State
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  
  // Review Modal State
  const [reviewOpp, setReviewOpp] = useState<any | null>(null);
  const [feedbackTier, setFeedbackTier] = useState<string>("T1");
  const [feedbackReason, setFeedbackReason] = useState<string>("");
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);

  useEffect(() => {
    async function fetchData() {
      try {
        const url = process.env.NEXT_PUBLIC_API_URL 
          ? `${process.env.NEXT_PUBLIC_API_URL}/api/heatmap/opportunities`
          : "http://localhost:8000/api/heatmap/opportunities";
        
        console.log("Fetching heatmap opportunities from:", url);
        const res = await fetch(url, { cache: 'no-store' });
        const data = await res.json();
        
        if (data.opportunities) {
          const sorted = data.opportunities.sort((a: any, b: any) => b.total_score - a.total_score);
          setOpportunities(sorted);
        }
      } catch (err) {
        console.error("Failed to fetch opportunities", err);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  // Compute Dashboard Stats
  const totalMonitored = opportunities.length;
  const tier1 = opportunities.filter((o) => o.tier === "T1").length;
  const pending = opportunities.filter((o) => o.status === "Pending").length;
  const avgScore = totalMonitored > 0 
    ? (opportunities.reduce((acc, curr) => acc + curr.total_score, 0) / totalMonitored).toFixed(1) 
    : "0.0";

  // Selection Logic
  const handleSelectAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      setSelectedIds(new Set(opportunities.map(o => o.contract_id || o.request_id)));
    } else {
      setSelectedIds(new Set());
    }
  };

  const handleSelectOne = (id: string) => {
    const nextSet = new Set(selectedIds);
    if (nextSet.has(id)) nextSet.delete(id);
    else nextSet.add(id);
    setSelectedIds(nextSet);
  };

  // Feedback Submission Logic
  const submitFeedback = async () => {
    if (!reviewOpp) return;
    setFeedbackSubmitting(true);
    try {
      const url = process.env.NEXT_PUBLIC_API_URL 
        ? `${process.env.NEXT_PUBLIC_API_URL}/api/heatmap/feedback`
        : "http://localhost:8000/api/heatmap/feedback";

      const payload = {
        opportunity_id: reviewOpp.id?.toString() || reviewOpp.contract_id || reviewOpp.request_id,
        user_id: "human-manager",
        original_tier: reviewOpp.tier,
        suggested_tier: feedbackTier,
        feedback_notes: feedbackReason
      };

      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      
      if (res.ok) {
        // Optimistic UI update
        const updated = opportunities.map(o => {
          if ((o.contract_id || o.request_id) === (reviewOpp.contract_id || reviewOpp.request_id)) {
            return { ...o, tier: feedbackTier, status: "Approved" };
          }
          return o;
        });
        setOpportunities(updated);
        setReviewOpp(null);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setFeedbackSubmitting(false);
    }
  };

  // Prepare Chart Data
  const chartData = opportunities.map(o => ({
    ...o,
    x: o.fis_score || o.es_score || (o.total_score / 2),
    y: o.eus_score || o.ius_score || (o.total_score / 2),
    z: (o.total_score * 15) // visual size
  }));

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white p-4 border border-slate-200 shadow-xl rounded-lg max-w-xs">
          <p className="font-bold text-slate-800">{data.supplier_name || 'New Request'}</p>
          <p className="text-xs text-slate-500 mb-2">{data.contract_id || data.request_id}</p>
          <div className="flex justify-between items-center mb-2">
            <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-100">{data.tier}</span>
            <span className="font-bold text-sponsor-blue">{data.total_score.toFixed(1)}/10</span>
          </div>
          <p className="text-xs text-slate-600 line-clamp-3 leading-snug">{data.justification_summary}</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-8 bg-slate-50 min-h-screen relative">
      <div className="max-w-7xl mx-auto space-y-6 pb-20">
        <header className="flex flex-col md:flex-row justify-between items-start md:items-end mb-6 gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Sourcing Priority Heatmap</h1>
            <p className="text-slate-500 mt-2 text-sm">Agentic continuous evaluation of existing contracts and new requests.</p>
          </div>
          <div className="flex items-center gap-3 bg-white p-1 rounded-lg border border-slate-200 shadow-sm">
            <button 
              onClick={() => setViewMode('table')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${viewMode === 'table' ? 'bg-slate-100 text-slate-900' : 'text-slate-500 hover:text-slate-700'}`}
            >
              <List className="w-4 h-4" /> Table
            </button>
            <button 
              onClick={() => setViewMode('heatmap')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${viewMode === 'heatmap' ? 'bg-slate-100 text-slate-900' : 'text-slate-500 hover:text-slate-700'}`}
            >
              <LayoutGrid className="w-4 h-4" /> Matrix
            </button>
          </div>
        </header>

        {/* Dashboard Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h3 className="text-sm font-medium text-slate-500 mb-1">Total Monitored</h3>
            <p className="text-3xl font-bold text-slate-800">{loading ? "..." : totalMonitored}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h3 className="text-sm font-medium text-slate-500 mb-1">Tier 1 Opportunities</h3>
            <p className="text-3xl font-bold text-mit-red">{loading ? "..." : tier1}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h3 className="text-sm font-medium text-slate-500 mb-1">Pending Review</h3>
            <p className="text-3xl font-bold text-sponsor-orange">{loading ? "..." : pending}</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h3 className="text-sm font-medium text-slate-500 mb-1">Avg Score</h3>
            <p className="text-3xl font-bold text-slate-800">{loading ? "..." : avgScore}</p>
          </div>
        </div>

        {/* View Router */}
        {viewMode === 'heatmap' ? (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <h2 className="font-semibold text-slate-800 mb-6">Strategic Impact vs Urgency Matrix</h2>
            <div className="w-full h-[500px]">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                  <XAxis type="number" dataKey="x" name="Impact" tick={{fontSize: 12, fill: '#64748b'}} label={{ value: 'Financial Impact Score (FIS / ES) →', position: 'bottom', fill: '#64748b', fontSize: 13 }} domain={[0, 10]} />
                  <YAxis type="number" dataKey="y" name="Urgency" tick={{fontSize: 12, fill: '#64748b'}} label={{ value: 'Urgency & Risk Score (EUS / RSS) →', angle: -90, position: 'left', fill: '#64748b', fontSize: 13 }} domain={[0, 10]} />
                  <ZAxis type="number" dataKey="z" range={[60, 400]} name="Volume" />
                  <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3' }} />
                  <Scatter name="Opportunities" data={chartData} onClick={(data) => setReviewOpp(data.payload)}>
                    {chartData.map((entry, index) => {
                      let fill = "#64748b"; // T4
                      if (entry.tier === "T1") fill = "#ef4444";
                      if (entry.tier === "T2") fill = "#f97316";
                      if (entry.tier === "T3") fill = "#3b82f6";
                      return <Cell key={`cell-${index}`} fill={fill} fillOpacity={0.7} stroke={fill} strokeWidth={2} className="cursor-pointer transition-all hover:fill-opacity-100" />
                    })}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
            </div>
            <div className="flex justify-center gap-6 mt-4 text-xs font-medium text-slate-500">
              <span className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-mit-red opacity-80"></div> Tier 1 (Critical)</span>
              <span className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-orange-500 opacity-80"></div> Tier 2 (Immediate)</span>
              <span className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-blue-500 opacity-80"></div> Tier 3 (Monitor)</span>
              <span className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-slate-500 opacity-80"></div> Tier 4 (Low)</span>
            </div>
          </div>
        ) : (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
              <div className="flex items-center gap-4">
                <h2 className="font-semibold text-slate-800">Prioritized Opportunities</h2>
                {selectedIds.size > 0 && (
                  <span className="text-xs bg-blue-50 text-sponsor-blue font-medium px-2.5 py-1 rounded-full border border-blue-100">
                    {selectedIds.size} selected
                  </span>
                )}
              </div>
              <div className="flex gap-3">
                <input 
                  type="text" 
                  placeholder="Search suppliers..." 
                  className="pl-3 pr-4 py-1.5 border border-slate-300 rounded-md text-sm w-64 focus:outline-none focus:ring-1 focus:ring-sponsor-blue"
                />
                {selectedIds.size > 0 && (
                  <button className="px-3 py-1.5 bg-sponsor-blue text-white rounded-md text-sm font-medium hover:bg-blue-700 transition">
                    Push to Casework
                  </button>
                )}
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider border-b border-slate-200 text-left">
                    <th className="px-6 py-4 font-medium w-10">
                      <input 
                        type="checkbox" 
                        className="rounded border-slate-300 w-4 h-4 text-sponsor-blue focus:ring-sponsor-blue" 
                        checked={selectedIds.size === opportunities.length && opportunities.length > 0}
                        onChange={handleSelectAll}
                      />
                    </th>
                    <th className="px-6 py-4 font-medium">Supplier / Request</th>
                    <th className="px-6 py-4 font-medium">Category</th>
                    <th className="px-6 py-4 font-medium">Tier</th>
                    <th className="px-6 py-4 font-medium">Score Breakdown</th>
                    <th className="px-6 py-4 font-medium">Total</th>
                    <th className="px-6 py-4 font-medium">Action Window</th>
                    <th className="px-6 py-4 font-medium text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {loading ? (
                    <tr>
                      <td colSpan={8} className="px-6 py-12 text-center text-slate-500">
                        <div className="flex flex-col items-center justify-center">
                          <div className="w-8 h-8 rounded-full border-2 border-slate-200 border-t-sponsor-blue animate-spin mb-3"></div>
                          <p>Loading scored opportunities from backend...</p>
                        </div>
                      </td>
                    </tr>
                  ) : opportunities.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-6 py-12 text-center text-slate-500">
                        No opportunities found in the scoring engine.
                      </td>
                    </tr>
                  ) : (
                    opportunities.map((opp) => {
                      const id = opp.contract_id || opp.request_id;
                      const isSelected = selectedIds.has(id);
                      return (
                        <tr key={id} className={`transition-colors ${isSelected ? 'bg-blue-50/50' : 'hover:bg-slate-50'}`}>
                          <td className="px-6 py-4 border-l-2 border-transparent" style={{borderLeftColor: isSelected ? '#1e3a8a' : 'transparent'}}>
                            <input 
                              type="checkbox" 
                              className="rounded border-slate-300 w-4 h-4 text-sponsor-blue focus:ring-sponsor-blue" 
                              checked={isSelected}
                              onChange={() => handleSelectOne(id)}
                            />
                          </td>
                          <td className="px-6 py-4">
                            <div className="font-semibold text-slate-900">{opp.supplier_name || 'New Requirement'}</div>
                            <div className="text-xs text-slate-500 font-mono mt-0.5">{id}</div>
                          </td>
                          <td className="px-6 py-4 text-sm text-slate-600">
                            {opp.category}<br/>
                            <span className="text-xs text-slate-400">{opp.subcategory || 'General'}</span>
                          </td>
                          <td className="px-6 py-4">
                            {opp.tier === 'T1' && <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-mit-red ring-1 ring-inset ring-red-100 border border-mit-red/20">T1</span>}
                            {opp.tier === 'T2' && <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-700 ring-1 ring-inset ring-orange-100 border border-orange-200">T2</span>}
                            {opp.tier === 'T3' && <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-sponsor-blue border border-sponsor-blue/20">T3</span>}
                            {opp.tier === 'T4' && <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">T4</span>}
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex flex-wrap gap-1.5 text-[10px] font-mono">
                              {opp.eus_score !== null && <span title="Expiry Urgency Score" className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 border border-slate-200">EUS:{opp.eus_score?.toFixed(1)}</span>}
                              {opp.ius_score !== null && <span title="Implement Urgency Score" className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 border border-slate-200">IUS:{opp.ius_score?.toFixed(1)}</span>}
                              {opp.fis_score !== null && <span title="Financial Impact Score" className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 border border-slate-200">FIS:{opp.fis_score?.toFixed(1)}</span>}
                              {opp.es_score !== null && <span title="Estimated Spend Score" className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 border border-slate-200">ES:{opp.es_score?.toFixed(1)}</span>}
                              {opp.rss_score !== null && <span title="Supplier Risk Score" className="px-1.5 py-0.5 bg-slate-100 rounded border border-orange-200 text-orange-700 bg-orange-50">RSS:{opp.rss_score?.toFixed(1)}</span>}
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <div className="text-lg font-bold text-slate-900">{opp.total_score?.toFixed(1)}<span className="text-xs text-slate-500 font-normal">/10</span></div>
                          </td>
                          <td className="px-6 py-4 text-sm font-medium text-slate-700">
                            {opp.recommended_action_window || (opp.tier === 'T1' ? 'Critical' : opp.tier === 'T2' ? 'Immediate' : 'Monitor')}
                          </td>
                          <td className="px-6 py-4 text-right">
                            {opp.status === 'Approved' ? (
                              <span className="text-xs font-semibold text-green-600 uppercase flex items-center justify-end gap-1">
                                Reviewed <ExternalLink className="w-3 h-3"/>
                              </span>
                            ) : (
                              <button 
                                onClick={() => { setReviewOpp(opp); setFeedbackTier(opp.tier); setFeedbackReason(""); }}
                                className="text-sponsor-blue hover:text-blue-800 text-sm font-medium bg-blue-50 hover:bg-blue-100 px-3 py-1.5 rounded transition"
                              >
                                Review
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Slide-over Feedback Modal */}
      {reviewOpp && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm transition-opacity" onClick={() => setReviewOpp(null)} />
          <div className="fixed inset-y-0 right-0 w-full max-w-md bg-white shadow-2xl flex flex-col transform transition-transform border-l border-slate-200">
            <div className="px-6 py-5 border-b border-slate-100 flex justify-between items-center bg-slate-50">
              <h2 className="text-lg font-bold text-slate-900">Review Opportunity</h2>
              <button onClick={() => setReviewOpp(null)} className="text-slate-400 hover:text-slate-600 transition bg-white p-1 rounded-full shadow-sm">
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Target</p>
                <p className="text-xl font-bold text-slate-800">{reviewOpp.supplier_name || 'New Requirement'}</p>
                <p className="text-sm font-mono text-slate-500">{reviewOpp.contract_id || reviewOpp.request_id}</p>
              </div>

              <div className="bg-blue-50/50 p-4 rounded-lg border border-blue-100">
                <div className="flex justify-between items-end mb-3">
                  <p className="text-sm font-semibold text-slate-700">Agentic Score</p>
                  <p className="text-2xl font-bold text-sponsor-blue">{reviewOpp.total_score?.toFixed(1)}/10</p>
                </div>
                <p className="text-sm text-slate-600 leading-relaxed italic border-l-2 border-sponsor-blue pl-3">"{reviewOpp.justification_summary}"</p>
              </div>

              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">Override Tier (Optional)</label>
                <select 
                  className="w-full border border-slate-300 rounded-md shadow-sm py-2 px-3 text-sm focus:ring-sponsor-blue focus:border-sponsor-blue"
                  value={feedbackTier} 
                  onChange={(e) => setFeedbackTier(e.target.value)}
                >
                  <option value="T1">T1 - Critical</option>
                  <option value="T2">T2 - Immediate</option>
                  <option value="T3">T3 - Monitor</option>
                  <option value="T4">T4 - Low Priority</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">Feedback Notes</label>
                <textarea 
                  className="w-full border border-slate-300 rounded-md shadow-sm py-2 px-3 text-sm focus:ring-sponsor-blue focus:border-sponsor-blue min-h-[120px]"
                  placeholder="Provide context for the AI engine (e.g., 'We are sunsetting this supplier next year, reduce priority')"
                  value={feedbackReason}
                  onChange={(e) => setFeedbackReason(e.target.value)}
                />
              </div>
            </div>

            <div className="p-6 border-t border-slate-100 bg-slate-50 flex gap-3">
              <button 
                onClick={() => setReviewOpp(null)}
                className="flex-1 px-4 py-2 border border-slate-300 text-slate-700 bg-white rounded-md font-medium text-sm hover:bg-slate-50 transition"
              >
                Cancel
              </button>
              <button 
                onClick={submitFeedback}
                disabled={feedbackSubmitting}
                className="flex-1 px-4 py-2 bg-sponsor-blue text-white rounded-md font-medium text-sm hover:bg-blue-700 transition shadow-sm disabled:opacity-50"
              >
                {feedbackSubmitting ? 'Submitting...' : 'Approve & Submit'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
