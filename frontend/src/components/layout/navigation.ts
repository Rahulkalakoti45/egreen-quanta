export interface NavItem {
  to: string;
  label: string;
  /** Inline SVG path data (Lucide-style, 24x24, stroke). */
  icon: string;
  /** Build module that fills this area — shown as a hint until then. */
  module?: string;
}

export const NAV_ITEMS: NavItem[] = [
  {
    to: "/",
    label: "Overview",
    icon: "M3 13h8V3H3v10Zm0 8h8v-6H3v6Zm10 0h8V11h-8v10Zm0-18v6h8V3h-8Z",
  },
  {
    to: "/signatures",
    label: "Signatures",
    icon: "M4 20h16M6 16l4-8 4 8M9 12h2M14 16l3-6 3 6M17 12h1",
    module: "M2",
  },
  {
    to: "/certificates",
    label: "Certificates",
    icon: "M12 15a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-2 1v6l2-1 2 1v-6M6 5h12v6H6z",
    module: "M2",
  },
  {
    to: "/threats",
    label: "Threats",
    icon: "M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7l8-4Zm0 5v5m0 3h.01",
    module: "M3",
  },
  {
    to: "/quantum",
    label: "Quantum Lab",
    icon: "M12 12m-2 0a2 2 0 1 0 4 0 2 2 0 1 0-4 0M12 12c6-6 9-6 9-6M12 12c-6 6-9 6-9 6M12 12c6 6 9 6 9 6M12 12c-6-6-9-6-9-6",
    module: "M4",
  },
  {
    to: "/audit",
    label: "Audit Log",
    icon: "M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 4 0M9 5a2 2 0 0 1 4 0m-4 8 2 2 4-4",
    module: "M6",
  },
  {
    to: "/admin",
    label: "Admin",
    icon: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm7.4-3a7.4 7.4 0 0 0-.1-1.3l2-1.6-2-3.4-2.4 1a7.3 7.3 0 0 0-2.2-1.3l-.4-2.5h-3.8l-.4 2.5a7.3 7.3 0 0 0-2.2 1.3l-2.4-1-2 3.4 2 1.6a7.4 7.4 0 0 0 0 2.6l-2 1.6 2 3.4 2.4-1a7.3 7.3 0 0 0 2.2 1.3l.4 2.5h3.8l.4-2.5a7.3 7.3 0 0 0 2.2-1.3l2.4 1 2-3.4-2-1.6c.1-.4.1-.9.1-1.3Z",
    module: "M1",
  },
];
