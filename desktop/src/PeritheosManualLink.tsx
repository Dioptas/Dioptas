import { isTauri, invoke } from "@tauri-apps/api/core";
import { useState } from "react";

/** Native help opens the system browser; the editor and its drafts stay open. */
export function PeritheosManualLink({
  href,
  label = "PeriTheos manual",
}: {
  href: string;
  label?: string;
}) {
  const [error, setError] = useState("");
  return (
    <>
      <a
        href={href}
        target="_blank"
        rel="noreferrer"
        onClick={(event) => {
          if (!isTauri()) return;
          event.preventDefault();
          setError("");
          void invoke("open_peritheos_manual", { url: href }).catch((e) =>
            setError(String(e)),
          );
        }}
      >
        {label} ↗
      </a>
      {error && <span role="alert">{error}</span>}
    </>
  );
}
