import type { Metadata } from 'next';
import { Syne, DM_Sans } from 'next/font/google';
import './globals.css';
import AppShell from './AppShell';

const syne = Syne({ subsets: ['latin'], variable: '--font-syne', weight: ['400', '600', '700', '800'] });
const dmSans = DM_Sans({ subsets: ['latin'], variable: '--font-dm-sans', weight: ['400', '500', '700'] });

export const metadata: Metadata = {
  title: 'Agentic Sourcing — Priority List',
  description: 'Sourcing prioritization, S2C execution, and intake',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${syne.variable} ${dmSans.variable}`}>
      <body>
        <AppShell>
          {children}
        </AppShell>
      </body>
    </html>
  );
}
