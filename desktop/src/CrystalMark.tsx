import { useId } from "react";

// Six prism faces parallel to c, with an inclined six-sided termination.
// Project the regular basal section, then incline the termination across it.
const endFace = Array.from({ length: 6 }, (_, index) => {
  const angle = (index * Math.PI) / 3;
  const x = 10 * Math.cos(angle);
  return [16 + x, 6 + 10 * Math.sin(angle) * 0.45 + x * 0.22];
});
const alongC = ([x, y]: number[]) => [x - 1.2, y + 26];
const points = (vertices: number[][]) =>
  vertices.map(([x, y]) => `${x.toFixed(3)},${y.toFixed(3)}`).join(" ");

export function CrystalMark() {
  const id = useId();
  const paint = (name: string) => `url(#${id}-${name})`;
  return (
    <svg width="28" height="34" viewBox="0 0 32 40" aria-hidden="true">
      <defs>
        <linearGradient id={`${id}-right`} x1="0" y1="0" x2="1" y2="1">
          <stop stopColor="#087768" />
          <stop offset=".5" stopColor="#003b35" />
          <stop offset="1" stopColor="#001e1c" />
        </linearGradient>
        <linearGradient id={`${id}-front`} x1="0" y1="0" x2="1" y2="1">
          <stop stopColor="#075b4a" />
          <stop offset=".45" stopColor="#003e32" />
          <stop offset="1" stopColor="#00241f" />
        </linearGradient>
        <linearGradient id={`${id}-left`} x1="0" y1="0" x2="1" y2="1">
          <stop stopColor="#238e79" />
          <stop offset=".4" stopColor="#075447" />
          <stop offset="1" stopColor="#002c25" />
        </linearGradient>
        <linearGradient id={`${id}-termination`} x1="0" y1="0" x2="1" y2="1">
          <stop stopColor="#8dc9c1" />
          <stop offset=".32" stopColor="#328e7f" />
          <stop offset=".6" stopColor="#005c4e" />
          <stop offset="1" stopColor="#00382e" />
        </linearGradient>
        <linearGradient id={`${id}-reflection`} x1="0" y1="0" x2=".25" y2="1">
          <stop stopColor="#d3eeea" stopOpacity=".85" />
          <stop offset=".4" stopColor="#9ed8cd" stopOpacity=".6" />
          <stop offset="1" stopColor="#56b9a1" stopOpacity="0" />
        </linearGradient>
      </defs>
      <g stroke="#176954" strokeWidth=".45" strokeLinejoin="round">
        {["right", "front", "left"].map((face, index) => (
          <polygon
            key={face}
            points={points([
              endFace[index],
              endFace[index + 1],
              alongC(endFace[index + 1]),
              alongC(endFace[index]),
            ])}
            fill={paint(face)}
          />
        ))}
        <polygon points={points(endFace)} fill={paint("termination")} />
      </g>
      {/* Narrow reflections follow the long faces rather than outlining a box. */}
      <path
        d="M12.5 10.4 13.9 10.8 13 28.4 12.1 30.2Z"
        fill={paint("reflection")}
      />
      <path
        d="M7.2 5.8 8.3 6.8 7.5 23.5 6.8 21.8Z"
        fill={paint("reflection")}
      />
      <path
        d="M7.2 3.8 11.2 1.8 17 3.1 12.6 5.6 10 6Z"
        fill="#c4e6e2"
        fillOpacity=".85"
      />
      <path
        d="M6 3.8 4.8 29.8 M21 11.0 19.8 37"
        fill="none"
        stroke="#7ac5b4"
        strokeOpacity=".65"
        strokeWidth=".55"
      />
      <path
        d="M11 8.8 9.8 34.8 M4.8 29.8 9.8 34.8 19.8 37 24.8 34.2"
        fill="none"
        stroke="#21a688"
        strokeOpacity=".8"
        strokeWidth=".5"
      />
    </svg>
  );
}
