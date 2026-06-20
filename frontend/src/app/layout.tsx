import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'AegisOne XDR | AI-Powered Threat Detection & Response',
  description:
    'Enterprise AI-powered autonomous detection, investigation, and response platform powered by Band multi-agent orchestration.',
  icons: {
    icon: '/favicon.ico',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="font-sans bg-aegis-bg text-aegis-text antialiased">
        {children}
      </body>
    </html>
  );
}
