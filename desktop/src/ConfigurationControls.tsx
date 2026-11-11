import { operationPayload, type OperationCall } from "./commandDispatch";
import type { CommandPayload } from "./commandContracts";
import { Button, Input, Select } from "./ui";
import { useEffect, useState } from "react";
import type { State } from "./types";
import type { IntegrationRun } from "./integration";
import { ConfigurationNavigationControls } from "./ConfigurationNavigationControls";
import { ConfigurationCombinationControls } from "./ConfigurationCombinationControls";

export function ConfigurationControls({
  state,
  ready,
  run,
}: {
  state: State;
  ready: boolean;
  run: IntegrationRun;
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
  const action = (...call: OperationCall<CommandPayload<"configuration">>) =>
    run(
      "configuration",
      operationPayload<CommandPayload<"configuration">>(call),
      "Updating configurations…",
    );
  return (
    <div
      className="configuration-controls"
      role="group"
      aria-label="Project configurations"
    >
      <label>
        Configuration{" "}
        <Select
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
        </Select>
      </label>
      {editing ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) void action("rename", { name: name.trim() });
            setEditing(false);
          }}
        >
          <Input
            aria-label="Configuration name"
            value={name}
            maxLength={250}
            onChange={(e) => setName(e.target.value)}
            autoFocus
          />
          <Button disabled={!ready || !name.trim()} type="submit">
            Apply
          </Button>
          <Button type="button" onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </form>
      ) : (
        <>
          <Button
            disabled={!ready}
            onClick={() => action("add")}
            title="Start with the current processed image and calibration, using default settings"
          >
            Add
          </Button>
          <Button
            disabled={!ready}
            onClick={() => action("duplicate")}
            title="Copy this configuration, including its masks and processing settings"
          >
            Duplicate
          </Button>
          <Button
            disabled={!ready}
            onClick={() => {
              setName(label);
              setEditing(true);
            }}
          >
            Rename
          </Button>
          <Button
            disabled={!ready || labels.length < 2}
            onClick={() => action("remove")}
            title="Remove the selected configuration"
          >
            Remove
          </Button>
        </>
      )}
      <ConfigurationNavigationControls ready={ready} run={run} />
      <ConfigurationCombinationControls
        state={state}
        ready={ready}
        run={run}
        showSelector={false}
      />
    </div>
  );
}
