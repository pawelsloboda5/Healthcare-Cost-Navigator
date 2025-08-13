import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://healthcare-cost-navigator.example.com";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "Healthcare Cost Navigator",
    template: "%s | Healthcare Cost Navigator",
  },
  applicationName: "Healthcare Cost Navigator",
  description:
    "Search and compare U.S. hospital procedure costs and quality. Natural language to SQL, provider lookup, and cost analytics in one place.",
  keywords: [
    "healthcare costs",
    "hospital prices",
    "DRG",
    "provider search",
    "medical procedure cost",
    "price transparency",
    "analytics",
  ],
  authors: [{ name: "Better Health" }],
  creator: "Better Health",
  publisher: "Better Health",
  themeColor: "#0ea5e9",
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  openGraph: {
    type: "website",
    url: siteUrl,
    title: "Healthcare Cost Navigator",
    description:
      "Search and compare hospital procedure costs and quality ratings across the U.S.",
    siteName: "Healthcare Cost Navigator",
    images: [
      {
        url: "/better-health.png",
        width: 512,
        height: 512,
        alt: "Healthcare Cost Navigator",
      },
    ],
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "Healthcare Cost Navigator",
    description:
      "Compare procedure costs and quality ratings. Ask questions in plain English.",
    images: ["/better-health.png"],
    creator: "@betterhealth",
  },
  icons: {
    icon: "/better-health.png",
    apple: "/better-health.png",
    shortcut: "/better-health.png",
  },
  alternates: {
    canonical: "/",
  },
  category: "Healthcare",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="min-h-full">
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "WebSite",
              name: "Healthcare Cost Navigator",
              url: siteUrl,
              description:
                "Search and compare U.S. hospital procedure costs and quality ratings.",
              inLanguage: "en-US",
            }),
          }}
        />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-background text-foreground`}
      >
        <div className="min-h-screen">
          {children}
        </div>
      </body>
    </html>
  );
}
