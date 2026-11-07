import { useEffect, useState } from "react";
import type { State } from "./types";

export function ConfigurationControls({
  state,
  ready,
  run,
}: {
  state: State;
  ready: boolean;
  run: (
    command: string,
    args?: Record<string, unknown>,
    message?: string,
  ) => unknown;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const labels = state.configurationLabels ?? [];
  const label =
    labels[state.configurationIndex] ??
    `Configuration ${state.configurationIndex + 1}`;
  useEffect(() => {
    setEditing(false);
    setName(label);
  }, [state.configurationIndex, state.configurationContext, label]);
  const action = (operation: string, extra: Record<string, unknown> = {}) =>
    run("configuration", { operation, ...extra }, "Updating configurations…");
  return (
    <div
      className="configuration-controls"
      role="group"
      aria-label="Project configurations"
    >
      <label>
        Configuration{" "}
        <select
          aria-label="Active configuration"
          disabled={!ready || editing}
          value={state.configurationIndex}
          onChange={(e) => action("select", { index: Number(e.target.value) })}
        >
          {labels.map((name, index) => (
            <option key={index} value={index}>
              {name}
            </option>
          ))}
        </select>
      </label>
      {editing ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) void action("rename", { name: name.trim() });
            setEditing(false);
          }}
        >
          <input
            aria-label="Configuration name"
            value={name}
            maxLength={250}
            onChange={(e) => setName(e.target.value)}
            autoFocus
          />
          <button disabled={!ready || !name.trim()} type="submit">
            Apply
          </button>
          <button type="button" onClick={() => setEditing(false)}>
            Cancel
          </button>
        </form>
      ) : (
        <>
          <button
            disabled={!ready}
            onClick={() => action("add")}
            title="Start with the current processed image and calibration, using default settings"
          >
            Add
          </button>
          <button
            disabled={!ready}
            onClick={() => action("duplicate")}
            title="Copy this configuration, including its masks and processing settings"
          >
            Duplicate
          </button>
          <button
            disabled={!ready}
            onClick={() => {
              setName(label);
              setEditing(true);
            }}
          >
            Rename
          </button>
          <button
            disabled={!ready || labels.length < 2}
            onClick={() => action("remove")}
            title="Remove the selected configuration"
          >
            Remove
          </button>
        </>
      )}
    </div>
  );
}
