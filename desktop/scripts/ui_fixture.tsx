import { useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { flushSync } from "react-dom";
import {
  Button,
  Dialog,
  DialogHeader,
  DialogPanel,
  Input,
  Select,
  TextArea,
  Popover,
  Portal,
} from "../src/ui";
import { ImageIntensity } from "../src/ImageIntensity";
import type { Raster, ImageDisplayPreferences, Palette } from "../src/types";
import { EditorNumber } from "../src/PhaseEditorFields";
import { DataTable } from "../src/DataTable";
import "../src/style.css";
import "../src/surfaces.css";
import "../src/settings.css";
import "../src/calibrationSetup.css";
import "../src/calibrationNavigation.css";
import "../src/integration.css";
import "../src/integrationPhaseControls.css";
import "../src/integrationOverlayControls.css";
import "../src/integrationProcessingControls.css";
import "../src/phaseEditor.css";
import "../src/phaseDatabase.css";
import "../src/map.css";
import "../src/batch.css";
import "../src/customCommands.css";

const report = { submits: 0, cancelled: 0, commits: [] as (number | null)[] };
function Fields({ name }: { name: string }) {
  return (
    <div className="ui-fixture-fields" data-field-set={name}>
      <label>
        Text
        <Input aria-label={`${name} text`} defaultValue="CeO2" />
      </label>
      <label>
        Number
        <Input
          aria-label={`${name} number`}
          type="number"
          defaultValue="12.5"
        />
      </label>
      <label>
        Search
        <Input
          aria-label={`${name} search`}
          type="search"
          placeholder="Search materials"
        />
      </label>
      <label>
        Dropdown
        <Select aria-label={`${name} dropdown`} defaultValue="linear">
          <option value="linear">Linear</option>
          <option value="log">Logarithmic</option>
        </Select>
      </label>
      <label>
        Notes
        <TextArea
          aria-label={`${name} notes`}
          defaultValue="Instrument settings"
          rows={2}
        />
      </label>
      <label>
        Disabled
        <Input
          aria-label={`${name} disabled`}
          disabled
          defaultValue="Unavailable"
        />
      </label>
      <label style={{ display: "flex", alignItems: "center" }}>
        Enabled
        <Input aria-label={`${name} checkbox`} type="checkbox" defaultChecked />
      </label>
    </div>
  );
}
const raster: Raster = {
  width: 2,
  height: 2,
  fullWidth: 2,
  fullHeight: 2,
  step: 1,
  dtype: "f32le",
  data: new Float32Array([0, 25, 50, 100]).buffer,
  limits: [0, 100],
  histogram: { edges: [0, 50, 100], counts: [2, 2], finitePixels: 4 },
};
type HistogramDisplay = "detector" | "cake" | "map" | "batch";
function Histogram({
  display = "detector",
  orientation = "horizontal",
}: {
  display?: HistogramDisplay;
  orientation?: "horizontal" | "vertical";
} = {}) {
  const [limits, setLimits] = useState<[number, number]>([0, 100]);
  const [log, setLog] = useState(false);
  const [palette, setPalette] = useState<Palette>("grey");
  const [preferences, setPreferences] = useState<ImageDisplayPreferences>({
    size: "compact",
    orientation,
    auto: { mode: "percentile", percentile: 0.1, filter_gaps: true },
  });
  return (
    <div
      style={{
        position: "fixed",
        left: 24,
        bottom: 24,
        width: 300,
        height: orientation === "vertical" ? 400 : 80,
      }}
    >
      <ImageIntensity
        display={display}
        raster={raster}
        limits={limits}
        onLimits={setLimits}
        log={log}
        onLog={setLog}
        palette={palette}
        onPalette={setPalette}
        onAuto={() => {}}
        ready
        preferences={preferences}
        onPreferences={setPreferences}
      />
    </div>
  );
}
function Fixture({ large = false }: { large?: boolean }) {
  const [dialog, setDialog] = useState(false),
    [nested, setNested] = useState(false),
    [popup, setPopup] = useState(false);
  const [histogram, setHistogram] = useState(false);
  const [number, setNumber] = useState<number | null>(2);
  const dialogRef = useRef<HTMLDialogElement>(null),
    inputRef = useRef<HTMLInputElement>(null);
  return (
    <div className="app" data-text-size={large ? "large" : "normal"}>
      <main className="ui-fixture">
        <div className="ui-fixture-actions">
          <Button onClick={() => setDialog(true)}>Open dialog</Button>
          <Button onClick={() => setHistogram(true)}>Show histogram</Button>
          <Button onClick={() => setPopup(!popup)}>Open popup</Button>
          <Button onClick={() => inputRef.current?.focus()}>
            Focus input ref
          </Button>
          <Input ref={inputRef} aria-label="Ref target" />
        </div>
        <div className="ui-fixture-grid">
          <section>
            <h2>Panel</h2>
            <Fields name="Panel" />
          </section>
          <DialogPanel
            className="pe-dialog pe-native"
            aria-label="Detached editor"
          >
            <h2>Detached editor</h2>
            <Fields name="Detached" />
          </DialogPanel>
          <section>
            <h2>Table</h2>
            <DataTable>
              <tbody>
                <tr>
                  <td>
                    <Input
                      aria-label="Table number"
                      type="number"
                      defaultValue={3}
                    />
                  </td>
                  <td>
                    <Select aria-label="Table dropdown">
                      <option>Birch–Murnaghan</option>
                    </Select>
                  </td>
                </tr>
                <tr>
                  <td>
                    <Input
                      aria-label="Readonly table value"
                      readOnly
                      value="SiO2"
                    />
                  </td>
                  <td>
                    <Input
                      aria-label="Color swatch"
                      type="color"
                      defaultValue="#ff0000"
                    />
                  </td>
                </tr>
              </tbody>
            </DataTable>
            <div className="ui-fixture-actions">
              <Button variant="primary">Primary</Button>
              <Button variant="secondary">Secondary</Button>
              <Button variant="quiet">Quiet</Button>
              <Button disabled>Disabled action</Button>
            </div>
            <EditorNumber
              label="Validated number"
              value={number}
              min={0}
              max={10}
              onCommit={(value) => {
                report.commits.push(value);
                setNumber(value);
              }}
            />
            <Button
              className="plot-zoom-button"
              aria-label="Rectangle zoom"
              aria-pressed
            >
              ↔
            </Button>
          </section>
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            report.submits++;
          }}
        >
          <Button>Submit native form</Button>
        </form>
      </main>
      {histogram && <Histogram />}
      {popup && (
        <Portal>
          <Popover
            className="ui-fixture-popover"
            role="dialog"
            aria-label="Popup"
          >
            <Fields name="Popup" />
            <Button onClick={() => setPopup(false)}>Close popup</Button>
          </Popover>
        </Portal>
      )}
      {dialog && (
        <Portal>
          <Dialog
            ref={dialogRef}
            open
            className="ui-fixture-dialog"
            aria-label="Fixture dialog"
            dismissOnBackdrop
            onDismiss={() => {
              report.cancelled++;
              setDialog(false);
            }}
          >
            <DialogHeader title="Dialog" onClose={() => setDialog(false)} />
            <Input autoFocus aria-label="Dialog autofocus" />
            <Fields name="Dialog" />
            <div className="ui-fixture-actions">
              <Button onClick={() => setNested(true)}>
                Open nested dialog
              </Button>
              <Button onClick={() => dialogRef.current?.close()}>
                Imperative close
              </Button>
            </div>
            {nested && (
              <Dialog
                open
                className="ui-fixture-dialog"
                aria-label="Nested dialog"
                onDismiss={() => setNested(false)}
              >
                <DialogHeader title="Nested" onClose={() => setNested(false)} />
                <Input autoFocus aria-label="Nested autofocus" />
              </Dialog>
            )}
          </Dialog>
        </Portal>
      )}
    </div>
  );
}
const root = createRoot(document.getElementById("root")!);
Object.assign(window, {
  uiFixture: {
    render: (large = false) =>
      flushSync(() =>
        root.render(<Fixture key={String(large)} large={large} />),
      ),
    report,
    histogram: (
      display: HistogramDisplay,
      orientation: "horizontal" | "vertical",
      large = false,
      detached = false,
    ) =>
      flushSync(() => {
        const histogram = (
          <Histogram
            display={display}
            orientation={orientation}
            key={`${display}-${orientation}-${large}-${detached}`}
          />
        );
        root.render(
          <div className="app" data-text-size={large ? "large" : "normal"}>
            {detached ? histogram : <main>{histogram}</main>}
          </div>,
        );
      }),
    icons: () =>
      flushSync(() =>
        root.render(
          <div className="app">
            <main>
              {[
                "plot-controls",
                "map-toolbar",
                "map-source-actions",
                "calibration-task-panel",
              ].map((context, i) => (
                <div key={context} className={context}>
                  <div className={i === 3 ? "peak-row" : undefined}>
                    <Button
                      aria-label={`${context} icon`}
                      className={
                        i === 1
                          ? "map-icon-button"
                          : i === 2
                            ? "map-source-icon"
                            : "icon-button"
                      }
                      aria-pressed={i === 0}
                      style={i === 3 ? { gridColumn: 5 } : undefined}
                    >
                      <svg
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        aria-hidden="true"
                      >
                        <path d="M4 4h16v16H4z" fill="currentColor" />
                      </svg>
                    </Button>
                  </div>
                </div>
              ))}
            </main>
          </div>,
        ),
      ),
  },
});
(window as any).uiFixture.render();
