"use client";

import React from "react";

type DecisionActionBarProps = {
  statusText: string;
  primaryLabel: string;
  primaryBusy?: boolean;
  primaryDisabled?: boolean;
  onPrimary: () => void;
  secondaryLabel?: string;
  onSecondary?: () => void;
  secondaryDisabled?: boolean;
  tertiaryLabel?: string;
  onTertiary?: () => void;
  tertiaryDisabled?: boolean;
};

export default function DecisionActionBar({
  statusText,
  primaryLabel,
  primaryBusy = false,
  primaryDisabled = false,
  onPrimary,
  secondaryLabel,
  onSecondary,
  secondaryDisabled = false,
  tertiaryLabel,
  onTertiary,
  tertiaryDisabled = false,
}: DecisionActionBarProps) {
  return (
    <div className="sticky bottom-0 z-20 border-t border-slate-200 bg-white/95 backdrop-blur px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-slate-500">{statusText}</p>
        <div className="flex flex-wrap items-center gap-2">
          {tertiaryLabel && onTertiary && (
            <button
              type="button"
              onClick={onTertiary}
              disabled={tertiaryDisabled}
              className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 disabled:opacity-50"
            >
              {tertiaryLabel}
            </button>
          )}
          {secondaryLabel && onSecondary && (
            <button
              type="button"
              onClick={onSecondary}
              disabled={secondaryDisabled}
              className="rounded-md border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-800 disabled:opacity-50"
            >
              {secondaryLabel}
            </button>
          )}
          <button
            type="button"
            onClick={onPrimary}
            disabled={primaryDisabled || primaryBusy}
            className="rounded-md bg-sponsor-blue px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
          >
            {primaryBusy ? "Saving..." : primaryLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
