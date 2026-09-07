type SectionIconKind = "alert" | "cart" | "assistant" | "trend" | "coverage" | "risk" | "supplier" | "executive" | "route" | "approval" | "automation" | "audit" | "warehouse" | "operations" | "movement" | "stock" | "source" | "review" | "market";

const icons: Record<SectionIconKind, JSX.Element> = {
  alert: <path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9m-8.1 12a2.3 2.3 0 0 0 2.2-2h-4.4a2.3 2.3 0 0 0 2.2 2" />,
  cart: <path d="M3 4h2l2.2 10.2a2 2 0 0 0 2 1.6h7.7a2 2 0 0 0 1.9-1.4L20 9H7M10 21a1 1 0 1 1-2 0 1 1 0 0 1 2 0m8 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0" />,
  assistant: <path d="M12 3a7 7 0 0 0-7 7v4a3 3 0 0 0 3 3h1v-6H7v-1a5 5 0 0 1 10 0v1h-2v6h1a3 3 0 0 0 3-3v-4a7 7 0 0 0-7-7m-2 11h4m-2-3v6" />,
  trend: <path d="M4 19V5m0 14h16M7 15l4-4 3 2 5-6M16 7h3v3" />,
  coverage: <path d="M4 20V4h16v16H4Zm4-4v-4m4 4V8m4 8v-6" />,
  risk: <path d="m12 3 8 3v5c0 5-3.4 8.8-8 10-4.6-1.2-8-5-8-10V6l8-3Zm0 5v5m0 3h.01" />,
  supplier: <path d="M4 20V8l8-4 8 4v12M9 20v-5h6v5M8 10h.01M16 10h.01M8 13h.01M16 13h.01" />,
  executive: <path d="M12 3 4 7v5c0 5.2 3.4 8.8 8 10 4.6-1.2 8-4.8 8-10V7l-8-4Zm-3 9 2 2 4-4" />,
  route: <path d="M5 6h6l2 3h6M5 18h6l2-3h6M7 5v2m10 10v2" />,
  approval: <path d="m5 12 4 4L19 6" />,
  automation: <path d="m13 2-8 12h6l-1 8 9-13h-6l0-7Z" />,
  audit: <path d="M3 12a9 9 0 1 0 3-6.7M3 4v5h5m4-5v8l3 2" />,
  warehouse: <path d="m3 10 9-6 9 6v10H3V10Zm4 10v-6h10v6M9 10h.01M12 10h.01M15 10h.01" />,
  operations: <path d="M5 7h14M5 17h14M8 4v6m8 4v6" />,
  movement: <path d="M4 8h13l-3-3m3 3-3 3M20 16H7l3-3m-3 3 3 3" />,
  stock: <path d="M4 8 12 4l8 4-8 4-8-4Zm0 4 8 4 8-4m-16 4 8 4 8-4" />,
  source: <path d="M10 13a5 5 0 0 0 7.1.1l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1M14 11a5 5 0 0 0-7.1-.1l-2 2A5 5 0 0 0 12 20l1.1-1.1" />,
  review: <path d="M5 4h14v12H9l-4 4V4Zm4 5h6m-6 3h4" />,
  market: <path d="M12 21a9 9 0 1 0-9-9 9 9 0 0 0 9 9Zm0-14v5l3 2" />,
};

export default function SectionIcon({ kind }: { kind: SectionIconKind }) {
  return <span aria-hidden="true" className="section-heading-icon"><svg viewBox="0 0 24 24">{icons[kind]}</svg></span>;
}
