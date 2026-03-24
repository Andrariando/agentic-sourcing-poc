import { redirect } from 'next/navigation';

export default function Home() {
  // Redirect root URL immediately to the Heatmap Priority List
  redirect('/heatmap');
}
