"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

// Nav order mirrors the three-minute demo script: MONEY opens, AUTHOR-AN-ATTACK and LOOP carry the
// loop-lift and external-falsification claims. The three P0 screens are underlined in green so a
// presenter can find them without reading; the rest are P1.
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
      <span className="brand"><span className="dot" />VAJRA</span>
      {LINKS.map((l) => (
        <Link key={l.href} href={l.href}
              className={`${path === l.href ? "active" : ""} ${l.p0 ? "p0" : ""}`}>
          {l.label}
        </Link>
      ))}
      <span className="spacer" />
      {/* The status chip states WHAT the screens are reading. A judge should never have to ask
          whether a number came from a live model or a committed replay bundle. */}
      <span className="status" title="Every screen reads the committed offline replay bundle unless a
badge on the screen says otherwise. Seeded, so two runs agree byte-for-byte.">
        <span className="led" />
        offline replay bundle · seeded
      </span>
    </nav>
  );
}
