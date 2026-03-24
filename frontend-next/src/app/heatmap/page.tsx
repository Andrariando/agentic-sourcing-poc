import React from "react";

export default function HeatmapPriorityPage() {
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
            <p className="text-3xl font-bold text-slate-800">124</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h3 className="text-sm font-medium text-slate-500 mb-1">Tier 1 Opportunities</h3>
            <p className="text-3xl font-bold text-mit-red">8</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h3 className="text-sm font-medium text-slate-500 mb-1">Pending Review</h3>
            <p className="text-3xl font-bold text-sponsor-orange">12</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h3 className="text-sm font-medium text-slate-500 mb-1">Avg Score (IT Infra)</h3>
            <p className="text-3xl font-bold text-slate-800">5.4</p>
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
                {/* Mock Row 1 */}
                <tr className="hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-4"><input type="checkbox" className="rounded border-slate-300" /></td>
                  <td className="px-6 py-4">
                    <div className="font-semibold text-slate-900">TechGlobal Inc</div>
                    <div className="text-xs text-slate-500">CNT-2026-104</div>
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-600">IT Infrastructure<br/><span className="text-xs text-slate-400">Cloud Hosting</span></td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-mit-red ring-1 ring-inset ring-red-100 border border-mit-red/20">
                      T1
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex gap-2 text-xs">
                      <span title="Expiry Urgency Score" className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 font-mono">EUS:9.5</span>
                      <span title="Financial Impact Score" className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 font-mono">FIS:8.0</span>
                      <span title="Supplier Risk Score" className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 font-mono">RSS:7.2</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-lg font-bold text-slate-900">8.4<span className="text-xs text-slate-500 font-normal">/10</span></div>
                  </td>
                  <td className="px-6 py-4 text-sm font-medium text-sponsor-orange">{"Critical (≤ 90 days)"}</td>
                  <td className="px-6 py-4 text-right">
                    <button className="text-sponsor-blue hover:text-blue-800 text-sm font-medium">Review</button>
                  </td>
                </tr>
                
                {/* Mock Row 2 */}
                <tr className="hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-4"><input type="checkbox" className="rounded border-slate-300" /></td>
                  <td className="px-6 py-4">
                    <div className="font-semibold text-slate-900">New Requirement: AWS Expansion</div>
                    <div className="text-xs text-slate-500">REQ-2026-901</div>
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-600">IT Infrastructure<br/><span className="text-xs text-slate-400">Cloud Hosting</span></td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-sponsor-blue border border-sponsor-blue/20">
                      T2
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex gap-2 text-xs">
                      <span title="Implement Urgency Score" className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 font-mono">IUS:8.0</span>
                      <span title="Estimated Spend Score" className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 font-mono">ES:6.5</span>
                      <span title="Category Spend Importance" className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 font-mono">CSIS:7.0</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-lg font-bold text-slate-900">7.2<span className="text-xs text-slate-500 font-normal">/10</span></div>
                  </td>
                  <td className="px-6 py-4 text-sm font-medium text-slate-700">Immediate</td>
                  <td className="px-6 py-4 text-right">
                    <button className="text-sponsor-blue hover:text-blue-800 text-sm font-medium">Review</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
