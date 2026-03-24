"use client";

import React, { useState } from "react";

export default function BusinessIntakePage() {
  const [formData, setFormData] = useState({
    title: "",
    category: "IT Infrastructure",
    subcategory: "",
    justification: "",
    estimated_spend: 0,
    urgency_days: 30,
    strategic_alignment: 5
  });

  // Simple live mock calculation based on User Reference formulas
  const calcMockScore = () => {
    const ius = Math.max(0, 10 - (formData.urgency_days / 10));
    const es = Math.min(10, formData.estimated_spend / 100000);
    const sas = formData.strategic_alignment;
    const csis = 7.0; // static mock
    
    // PS_new = 0.30(IUS) + 0.30(ES) + 0.25(CSIS) + 0.15(SAS)
    return ((0.30 * ius) + (0.30 * es) + (0.25 * csis) + (0.15 * sas)).toFixed(1);
  };

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-slate-50 min-h-full flex justify-center">
      <div className="max-w-4xl w-full grid grid-cols-1 md:grid-cols-3 gap-8">
        
        {/* Left Side Form */}
        <div className="md:col-span-2 space-y-6 bg-white p-8 rounded-xl border border-slate-200 shadow-sm">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">New Business Request</h1>
            <p className="text-slate-500 text-sm mt-1">Submit a new sourcing requirement to the Agentic Heatmap for prioritization.</p>
          </div>
          
          <div className="space-y-4 pt-4 border-t border-slate-100">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Requirement Title</label>
              <input 
                type="text" 
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-1 focus:ring-sponsor-blue outline-none" 
                placeholder="e.g. AWS Multi-Region Expansion"
                value={formData.title}
                onChange={e => setFormData({...formData, title: e.target.value})}
              />
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Category</label>
                <select className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-1 focus:ring-sponsor-blue outline-none bg-white">
                  <option>IT Infrastructure</option>
                  <option>Software</option>
                  <option>Hardware</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Estimated Spend (USD)</label>
                <input 
                  type="number" 
                  className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-1 focus:ring-sponsor-blue outline-none" 
                  value={formData.estimated_spend}
                  onChange={e => setFormData({...formData, estimated_spend: Number(e.target.value)})}
                />
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Implementation Urgency (Days)</label>
              <input 
                type="range" 
                min="1" max="180" 
                className="w-full accent-sponsor-blue"
                value={formData.urgency_days}
                onChange={e => setFormData({...formData, urgency_days: Number(e.target.value)})}
              />
              <div className="flex justify-between text-xs text-slate-400 mt-1">
                <span>Immediate (1 day)</span>
                <span>{formData.urgency_days} days</span>
                <span>Low Priority (+180 days)</span>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Business Justification</label>
              <textarea 
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-1 focus:ring-sponsor-blue outline-none min-h-32" 
                placeholder="Why is this required?"
              ></textarea>
            </div>
            
            <div className="pt-4 flex justify-end">
              <button className="px-6 py-2 bg-sponsor-blue text-white rounded-md font-medium shadow-sm hover:bg-blue-700 transition">
                Submit Requirement
              </button>
            </div>
          </div>
        </div>
        
        {/* Right Side Live Score Preview */}
        <div className="md:col-span-1 space-y-4">
          <div className="bg-slate-900 text-white p-6 rounded-xl shadow-lg sticky top-8">
            <h3 className="text-sm font-semibold uppercase tracking-widest text-slate-400 mb-4">Live Agentic Score</h3>
            
            <div className="flex items-end gap-2 mb-6">
              <span className="text-5xl font-bold">{calcMockScore()}</span>
              <span className="text-slate-400 mb-1">/ 10</span>
            </div>
            
            <div className="space-y-3 pt-4 border-t border-slate-700 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-300">Implement Urgency (IUS)</span>
                <span className="font-mono">{Math.max(0, 10 - (formData.urgency_days / 10)).toFixed(1)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-300">Estimated Spend (ES)</span>
                <span className="font-mono">{Math.min(10, formData.estimated_spend / 100000).toFixed(1)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-300">Category Spend (CSIS)</span>
                <span className="font-mono">7.0</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-300">Strat Alignment (SAS)</span>
                <span className="font-mono">{formData.strategic_alignment.toFixed(1)}</span>
              </div>
            </div>
            
            <div className="mt-8 p-3 bg-slate-800 rounded-lg text-xs leading-relaxed text-slate-300 border border-slate-700">
              <span className="text-sponsor-orange font-semibold block mb-1">Supervisor Insight</span>
              Based on the estimated spend and urgency, this requirement will likely land in 
              Tier {Number(calcMockScore()) >= 8 ? '1' : Number(calcMockScore()) >= 6 ? '2' : '3'} 
              of the sourcing heatmap upon submission.
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
