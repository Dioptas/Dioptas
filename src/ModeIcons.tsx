// Match the sidebar's Lucide icons while showing the scientific view directly.
export function IntegrationModeIcon({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M3 20h1.5c1 0 1-7 2-7s1 7 2 7H10c1 0 1-16 2-16s1 16 2 16h1.5c1 0 1-10 2-10s1 10 2 10H21" />
    </svg>
  );
}

export function MaskModeIcon({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M3 21 21 3v16a2 2 0 0 1-2 2Z"
        fill="currentColor"
        fillOpacity={0.12}
        stroke="none"
      />
      <path d="m3 21 18-18" />
      <path d="m9 21 12-12m-6 12 6-6" strokeWidth={1.5} />
      <rect x={3} y={3} width={18} height={18} rx={2} />
    </svg>
  );
}

export function MapModeIcon({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <g fill="currentColor" stroke="none">
        <path d="M3 9h6v6H3Z" fillOpacity={0.2} />
        <path d="M9 3h6v6H9Zm6 12h6v4a2 2 0 0 1-2 2h-4Z" fillOpacity={0.4} />
        <path d="M9 9h6v6H9Z" fillOpacity={0.85} />
        <path d="M15 9h6v6h-6ZM9 15h6v6H9Z" fillOpacity={0.55} />
      </g>
      <rect x={3} y={3} width={18} height={18} rx={2} />
      <path d="M9 3v18M15 3v18M3 9h18M3 15h18" strokeWidth={1.5} />
    </svg>
  );
}
