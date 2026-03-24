"use client";

import React, { useEffect, useState } from "react";

export default function HeatmapPriorityPage() {
  const [opportunities, setOpportunities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const url = process.env.NEXT_PUBLIC_API_URL 
          ? `${process.env.NEXT_PUBLIC_API_URL}/api/heatmap/opportunities`
          : "http://localhost:8000/api/heatmap/opportunities";
        
        console.log("Fetching heatmap opportunities from:", url);
        const res = await fetch(url);
        const data = await res.json();
        
        if (data.opportunities) {
          // Sort by highest score first
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

  const totalMonitored = opportunities.length;
  const tier1 = opportunities.filter((o) => o.tier === "T1").length;
  const pending = opportunities.filter((o) => o.status === "Pending").length;
  const avgScore = totalMonitored > 0 
    ? (opportunities.reduce((acc, curr) => acc + curr.total_score, 0) / totalMonitored).toFixed(1) 
    : "0.0";

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-slate-50 min-h-full">
      <div className="max-w-7xl mx-auto space-y-6">
        <header className="flex justify-between items-end mb-8">
          <div>
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Sourcing Priority Heatmap</h1>
            <p className="text-slate-500 mt-2 text-sm">Agentic continuous evaluation of existing contracts and new requests.</p>
          </div>
          <div className="flex gap-3">
            <button className="px-4 py-2 bg-white border border-slate-200 shadow-sm rounded-md text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors">
              Refresh Scores
            </button>
            <button className="px-4 py-2 bg-sponsor-blue text-white shadow-md rounded-md text-sm font-medium hover:bg-blue-700 transition-colors">
              Approve Selected (Run DTP01)
            </button>
          </div>
        </header>

        {/* Dashboard Stats */}
        <div className="grid grid-cols-4 gap-4">
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
            <h3 className="text-sm font-medium text-slate-500 mb-1">Avg Score (IT Infra)</h3>
            <p className="text-3xl font-bold text-slate-800">{loading ? "..." : avgScore}</p>
          </div>
        </div>

        {/* The Data Table */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
            <h2 className="font-semibold text-slate-800">Prioritized Opportunities</h2>
            <div className="relative">
              <input 
                type="text" 
                placeholder="Search suppliers..." 
                className="pl-3 pr-4 py-1.5 border border-slate-300 rounded-md text-sm w-64 focus:outline-none focus:ring-1 focus:ring-sponsor-blue"
              />
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider border-b border-slate-200 text-left">
                  <th className="px-6 py-4 font-medium"><input type="checkbox" className="rounded" /></th>
                  <th className="px-6 py-4 font-medium">Supplier / Request</th>
                  <th className="px-6 py-4 font-medium">Category</th>
                  <th className="px-6 py-4 font-medium">Tier</th>
                  <th className="px-6 py-4 font-medium">Score Breakdown</th>
                  <th className="px-6 py-4 font-medium">Total Score</th>
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
                  opportunities.map((opp) => (
                    <tr key={opp.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-6 py-4"><input type="checkbox" className="rounded border-slate-300" /></td>
                      <td className="px-6 py-4">
                        <div className="font-semibold text-slate-900">{opp.supplier_name || 'New Requirement'}</div>
                        <div className="text-xs text-slate-500">{opp.contract_id || opp.request_id}</div>
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-600">
                        {opp.category}<br/>
                        <span className="text-xs text-slate-400">{opp.subcategory || 'General'}</span>
                      </td>
                      <td className="px-6 py-4">
                        {opp.tier === 'T1' && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-mit-red ring-1 ring-inset ring-red-100 border border-mit-red/20">
                            T1
                          </span>
                        )}
                        {opp.tier === 'T2' && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-700 ring-1 ring-inset ring-orange-100 border border-orange-200">
                            T2
                          </span>
                        )}
                        {opp.tier === 'T3' && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-sponsor-blue border border-sponsor-blue/20">
                            T3
                          </span>
                        )}
                        {opp.tier === 'T4' && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
                            T4
                          </span>
                        )}
                        {!['T1', 'T2', 'T3', 'T4'].includes(opp.tier) && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
                            {opp.tier || 'T4'}
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex flex-wrap gap-2 text-xs">
                          {opp.eus_score !== null && <span title="Expiry Urgency Score" className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 font-mono">EUS:{opp.eus_score?.toFixed(1)}</span>}
                          {opp.ius_score !== null && <span title="Implement Urgency Score" className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 font-mono">IUS:{opp.ius_score?.toFixed(1)}</span>}
                          {opp.fis_score !== null && <span title="Financial Impact Score" className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 font-mono">FIS:{opp.fis_score?.toFixed(1)}</span>}
                          {opp.es_score !== null && <span title="Estimated Spend Score" className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 font-mono">ES:{opp.es_score?.toFixed(1)}</span>}
                          {opp.rss_score !== null && <span title="Supplier Risk Score" className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 font-mono">RSS:{opp.rss_score?.toFixed(1)}</span>}
                          {opp.csis_score !== null && <span title="Category Spend Importance" className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 font-mono">CSIS:{opp.csis_score?.toFixed(1)}</span>}
                          {opp.sas_score !== null && <span title="Strategic Alignment Score" className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 font-mono">SAS:{opp.sas_score?.toFixed(1)}</span>}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-lg font-bold text-slate-900">{opp.total_score?.toFixed(1)}<span className="text-xs text-slate-500 font-normal">/10</span></div>
                      </td>
                      <td className="px-6 py-4 text-sm font-medium text-slate-700">
                        {opp.recommended_action_window || (opp.tier === 'T1' ? 'Critical' : opp.tier === 'T2' ? 'Immediate' : 'Monitor')}
                      </td>
                      <td className="px-6 py-4 text-right flex gap-3 justify-end items-center">
                        <span className={`text-xs font-semibold uppercase ${opp.status === 'Pending' ? 'text-sponsor-orange' : opp.status === 'Approved' ? 'text-green-600' : 'text-slate-400'}`}>
                          {opp.status}
                        </span>
                        <button className="text-sponsor-blue hover:text-blue-800 text-sm font-medium">Review</button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
