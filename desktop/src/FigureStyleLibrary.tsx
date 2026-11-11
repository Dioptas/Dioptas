import { useEffect, useState } from "react";
import { Button, Input, Select } from "./ui";
import type {
  PatternFigureSettings,
  PatternFigureSource,
} from "./patternFigure";
import {
  applyPatternFigureStyle,
  capturePatternFigureStyle,
  loadPatternFigureStyles,
  storePatternFigureStyles,
  patternFigureStylesKey,
} from "./patternFigureStyles";

export function FigureStyleLibrary({
  source,
  settings,
  valid,
  onApply,
}: {
  source: PatternFigureSource;
  settings: PatternFigureSettings;
  valid: boolean;
  onApply: (settings: PatternFigureSettings) => void;
}) {
  const [styles, setStyles] = useState(loadPatternFigureStyles);
  const [managing, setManaging] = useState(false);
  const [selected, setSelected] = useState("");
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const current = styles.find((style) => style.id === selected);
  useEffect(() => {
    const refresh = (event: StorageEvent) => {
      if (event.key === patternFigureStylesKey || event.key === null)
        setStyles(loadPatternFigureStyles());
    };
    window.addEventListener("storage", refresh);
    return () => window.removeEventListener("storage", refresh);
  }, []);
  function action(work: () => void) {
    setMessage("");
    setError("");
    try {
      work();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }
  function save(update: boolean) {
    action(() => {
      const style = capturePatternFigureStyle(
        name,
        settings,
        update ? current?.id : undefined,
      );
      const next = update
        ? styles.map((entry) => (entry.id === current?.id ? style : entry))
        : [...styles, style];
      storePatternFigureStyles(next);
      setStyles(next);
      setSelected(style.id);
      setName(style.name);
      setMessage(`${update ? "Updated" : "Saved"} style “${style.name}”.`);
    });
  }
  return (
    <div className="pattern-figure-style-library">
      <h3>Reusable styles</h3>
      <div className="pattern-figure-style-choice">
        <label>
          Saved style
          <Select
            aria-label="Saved figure style"
            value={current?.id ?? ""}
            onChange={(event) => {
              const style = styles.find(
                (entry) => entry.id === event.target.value,
              );
              setSelected(style?.id ?? "");
              setName(style?.name ?? "");
              setMessage("");
              setError("");
            }}
          >
            <option value="">
              {styles.length ? "Choose a style…" : "No saved styles"}
            </option>
            {styles.map((style) => (
              <option key={style.id} value={style.id}>
                {style.name}
              </option>
            ))}
          </Select>
        </label>
        <Button
          type="button"
          disabled={!current}
          onClick={() =>
            action(() => {
              if (!current) return;
              onApply(applyPatternFigureStyle(source, settings, current));
              setMessage(`Applied style “${current.name}”.`);
            })
          }
        >
          Apply style
        </Button>
      </div>
      <Button
        type="button"
        aria-expanded={managing}
        onClick={() => setManaging((value) => !value)}
      >
        {managing
          ? "Hide style controls"
          : styles.length
            ? "Save / manage styles…"
            : "Save current style…"}
      </Button>
      {managing && (
        <>
          <label>
            Style name
            <Input
              aria-label="Figure style name"
              maxLength={80}
              value={name}
              onChange={(event) => {
                setName(event.target.value);
                setMessage("");
                setError("");
              }}
            />
          </label>
          <div className="pattern-figure-style-actions">
            <Button
              type="button"
              disabled={!valid || !name.trim()}
              onClick={() => save(false)}
            >
              Save new style
            </Button>
            <Button
              type="button"
              disabled={!current || !valid || !name.trim()}
              onClick={() => save(true)}
            >
              Update style
            </Button>
            <Button
              type="button"
              disabled={!current}
              onClick={() =>
                action(() => {
                  const next = styles.filter((style) => style.id !== selected);
                  storePatternFigureStyles(next);
                  setStyles(next);
                  setSelected("");
                  setName("");
                  setMessage(`Deleted style “${current?.name}”.`);
                })
              }
            >
              Delete style
            </Button>
          </div>
          <p className="pattern-figure-caption">
            Saved on this computer. Colors and line styles follow the current
            curve and phase order, repeating for additional entries. Labels,
            visibility and ranges stay as set.
          </p>
        </>
      )}
      {(error || message) && (
        <p className="pattern-figure-caption" role={error ? "alert" : "status"}>
          {error || message}
        </p>
      )}
    </div>
  );
}
