// Directions follow Crystal::set_poni (lab x along detector rows, lab y along
// columns) and RasterView, which draws increasing rows upward and columns
// rightward: axis [±1,0,0] is vertical in the image, [0,±1,0] horizontal.
// The DAC shadow enters the image across the rotation axis.
const panels = [
  {
    title: "vertical",
    axis: { x1: 45, y1: 8, x2: 45, y2: 82 },
    shadow: { x: 58, y: 18, width: 17, height: 54 },
    sweep: { x1: 50, y1: 45, x2: 66, y2: 45 },
    caption: "shadow ↔",
  },
  {
    title: "horizontal",
    axis: { x1: 8, y1: 45, x2: 82, y2: 45 },
    shadow: { x: 15, y: 58, width: 60, height: 14 },
    sweep: { x1: 45, y1: 50, x2: 45, y2: 66 },
    caption: "shadow ↕",
  },
] as const;

export function RotationAxisDiagram() {
  return (
    <svg
      className="sc-axis-diagram"
      viewBox="0 0 200 116"
      role="img"
      aria-label="A vertical rotation axis runs up and down the image and the DAC shadow moves sideways. A horizontal axis runs left to right and the shadow moves up and down."
    >
      <defs>
        <marker
          id="sc-axis-arrowhead"
          viewBox="0 0 8 8"
          refX="7"
          refY="4"
          markerWidth="5"
          markerHeight="5"
          orient="auto-start-reverse"
        >
          <path d="M0 0 8 4 0 8z" fill="currentColor" />
        </marker>
      </defs>
      {panels.map((p, i) => (
        <g key={p.title} transform={`translate(${i * 105} 0)`}>
          <rect
            x="15"
            y="18"
            width="60"
            height="54"
            rx="2"
            className="sc-axis-frame"
          />
          <rect {...p.shadow} className="sc-axis-shadow" />
          <line {...p.axis} className="sc-axis-line" />
          <line
            {...p.sweep}
            stroke="currentColor"
            strokeWidth="1.2"
            markerStart="url(#sc-axis-arrowhead)"
            markerEnd="url(#sc-axis-arrowhead)"
          />
          <text x="45" y="96" textAnchor="middle" className="sc-axis-title">
            {p.title}
          </text>
          <text x="45" y="109" textAnchor="middle">
            {p.caption}
          </text>
        </g>
      ))}
    </svg>
  );
}

/**
 * A tilted circle around the rotation axis with an arrow on its near side.
 * `sign` is the sign of the axis vector: the sample turns right-handed about
 * it (PhaseSmith reciprocal::Geometry::convert), which is counterclockwise
 * seen from above for a vertical axis and from the right for a horizontal one.
 * The horizontal icon is the vertical one turned by a quarter.
 */
export function RotationDirectionIcon({
  sign,
  horizontal,
}: {
  sign: 1 | -1;
  horizontal: boolean;
}) {
  return (
    <svg
      className="sc-direction-icon"
      viewBox="0 0 32 32"
      width="34"
      height="34"
      aria-hidden="true"
    >
      <g transform={horizontal ? "rotate(90 16 16)" : undefined}>
        <line x1="16" y1="2" x2="16" y2="30" className="sc-axis-line" />
        {/* An open ring ending in an arrowhead on its near side, right of the
            axis for counterclockwise and mirrored to the left for clockwise. */}
        <g transform={sign > 0 ? undefined : "translate(32 0) scale(-1 1)"}>
          <path d="M22 10.8A12 6 0 0 0 4 16" className="sc-direction-back" />
          <path d="M4 16A12 6 0 0 0 26.4 19" className="sc-direction-front" />
          <path d="M29.6 16.2 27.6 23.4 22.2 17.2z" fill="currentColor" />
        </g>
      </g>
    </svg>
  );
}
