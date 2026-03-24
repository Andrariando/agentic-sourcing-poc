import React from "react";

export default function KPIDashboardPage() {
  return (
    <div className="flex-1 overflow-y-auto p-8 bg-slate-50 min-h-full">
      <div className="max-w-7xl mx-auto space-y-6">
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Agentic Heatmap KLI Dashboard</h1>
          <p className="text-slate-500 mt-2 text-sm">Key Learning Indicators tracking the health of the Heatmap agents and human-in-the-loop feedback.</p>
        </header>

        {/* Top KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-2">Platform Cycle Time</h3>
            <div className="flex items-end gap-3 mb-1">
              <span className="text-4xl font-bold text-slate-900">4.2</span>
              <span className="text-slate-500 font-medium mb-1">Days</span>
            </div>
            <p className="text-sm text-green-600 font-medium flex items-center">
              <span className="mr-1">↓</span> 38% vs Manual Process
            </p>
          </div>
          
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-2">Agent Reliability</h3>
            <div className="flex items-end gap-3 mb-1">
              <span className="text-4xl font-bold text-sponsor-blue">91.5%</span>
            </div>
            <p className="text-sm text-slate-500 font-medium flex items-center">
              Scores accepted without human override
            </p>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-2">Edit Density</h3>
            <div className="flex items-end gap-3 mb-1">
              <span className="text-4xl font-bold text-slate-900">0.8</span>
              <span className="text-slate-500 font-medium mb-1">Per Case</span>
            </div>
            <p className="text-sm text-red-500 font-medium flex items-center">
              <span className="mr-1">↑</span> Feedback frequency increasing
            </p>
          </div>
        </div>

        {/* Charts Mock Area */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 min-h-64 flex flex-col">
            <h3 className="text-sm font-semibold text-slate-800 mb-4">Historical Approvals & Funnel (Last 6 Months)</h3>
            <div className="flex-1 flex items-center justify-center bg-slate-50 rounded-lg border border-slate-200 border-dashed">
              <span className="text-slate-400 text-sm">Bar Chart View Placeholder</span>
            </div>
          </div>
          
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 min-h-64 flex flex-col">
            <h3 className="text-sm font-semibold text-slate-800 mb-4">Weight Recalibrations</h3>
            <div className="flex-1 flex items-center justify-center bg-slate-50 rounded-lg border border-slate-200 border-dashed">
              <span className="text-slate-400 text-sm">Line Chart measuring weight drift over time.</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
