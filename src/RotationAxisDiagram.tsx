// Directions follow Crystal::set_poni (slow = detector rows, fast = columns)
// and RasterView, which draws increasing rows upward and columns rightward.
const arrows = [
  { label: "+slow", x: 80, y: 14, tx: 80, ty: 10, anchor: "middle" },
  { label: "−slow", x: 80, y: 86, tx: 80, ty: 98, anchor: "middle" },
  { label: "+fast", x: 116, y: 50, tx: 120, ty: 54, anchor: "start" },
  { label: "−fast", x: 44, y: 50, tx: 40, ty: 54, anchor: "end" },
] as const;

export function RotationAxisDiagram() {
  return (
    <svg
      className="sc-axis-diagram"
      viewBox="0 0 160 102"
      role="img"
      aria-label="In the image as shown, +slow points up, −slow down, +fast right and −fast left."
    >
      <defs>
        <marker
          id="sc-axis-arrowhead"
          viewBox="0 0 8 8"
          refX="7"
          refY="4"
          markerWidth="6"
          markerHeight="6"
          orient="auto"
        >
          <path d="M0 0 8 4 0 8z" fill="currentColor" />
        </marker>
      </defs>
      <rect
        x="50"
        y="20"
        width="60"
        height="60"
        rx="2"
        className="sc-axis-frame"
      />
      {arrows.map((a) => (
        <g key={a.label}>
          <line
            x1="80"
            y1="50"
            x2={a.x}
            y2={a.y}
            stroke="currentColor"
            strokeWidth="1.5"
            markerEnd="url(#sc-axis-arrowhead)"
          />
          <text x={a.tx} y={a.ty} textAnchor={a.anchor}>
            {a.label}
          </text>
        </g>
      ))}
    </svg>
  );
}
