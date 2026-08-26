import "./globals.css";
import type { Metadata } from "next";
import { Nav } from "@/components/Nav";

export const metadata: Metadata = {
  title: "VAJRA — Verified Adversarial Rail Archive",
  description: "Red-team / blue-team payment-fraud closed loop",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Nav />
        <div className="wrap">{children}</div>
      </body>
    </html>
  );
}
