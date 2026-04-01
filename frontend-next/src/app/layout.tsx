import type { Metadata } from 'next';
import { Syne, DM_Sans } from 'next/font/google';
import './globals.css';
import Link from 'next/link';
import SidebarNav from './SidebarNav';

const syne = Syne({ subsets: ['latin'], variable: '--font-syne', weight: ['400', '600', '700', '800'] });
const dmSans = DM_Sans({ subsets: ['latin'], variable: '--font-dm-sans', weight: ['400', '500', '700'] });

export const metadata: Metadata = {
  title: 'Agentic Sourcing Heatmap',
  description: 'IT Infrastructure Sourcing Prioritization',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${syne.variable} ${dmSans.variable}`}>
      <body className="antialiased flex h-screen overflow-hidden bg-canvas text-ink font-sans">
        {/* Sidebar Navigation */}
        <aside className="w-64 bg-slate-900/95 backdrop-blur-md text-slate-300 flex flex-col shadow-2xl z-20 shrink-0 border-r border-white/5">
          <div className="h-16 flex items-center px-6 border-b border-white/10 shrink-0">
            <Link href="/" className="font-bold text-base text-white tracking-wide leading-tight mt-2 font-syne hover:opacity-90 transition">
              <span className="text-mit-red block text-[10px] uppercase tracking-widest mb-0.5 font-bold">Procurement</span>
              Agentic System
            </Link>
          </div>
          
          <SidebarNav />

          <div className="p-4 border-t border-white/10 shrink-0">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-sponsor-blue flex items-center justify-center text-white font-bold text-xs">
                DR
              </div>
              <div>
                <p className="text-sm font-medium text-white">Sourcing Mgr</p>
                <p className="text-xs text-slate-400">IT Infrastructure</p>
              </div>
            </div>
          </div>
        </aside>

        {/* Main Application Area */}
        <main className="flex-1 flex flex-col min-w-0 bg-background overflow-y-auto">
          {children}
        </main>
      </body>
    </html>
  );
}
