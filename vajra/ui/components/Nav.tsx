"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

// Nav order mirrors the three-minute demo script: MONEY opens, AUTHOR-AN-ATTACK and LOOP carry the
// loop-lift and external-falsification claims. The three P0 screens are marked; the rest are P1.
const LINKS = [
  { href: "/", label: "MONEY", p0: true },
  { href: "/author", label: "AUTHOR-AN-ATTACK", p0: true },
  { href: "/loop", label: "LOOP", p0: true },
  { href: "/gate", label: "GATE OPS", p0: false },
  { href: "/archive", label: "ARCHIVE", p0: false },
  { href: "/fidelity", label: "FIDELITY", p0: false },
];

export function Nav() {
  const path = usePathname();
  return (
    <nav className="nav">
      <span className="brand">VAJRA</span>
      {LINKS.map((l) => (
        <Link key={l.href} href={l.href} className={`${path === l.href ? "active" : ""} ${l.p0 ? "p0" : ""}`}>
          {l.label}
        </Link>
      ))}
      <span style={{ marginLeft: "auto", color: "var(--muted)", fontSize: 12 }}>
        offline replay bundle · seeded
      </span>
    </nav>
  );
}
