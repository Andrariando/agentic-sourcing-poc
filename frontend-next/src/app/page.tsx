import { redirect } from 'next/navigation';

export default function Home() {
  // Redirect root URL to the Sourcing Priority List
  redirect('/heatmap');
}
