import { Dialog, DialogHeader } from "./Dialog";
import { useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { EditorData } from "./phaseEditorTypes";

const rows = [
  [
    [0, "H"],
    [17, "He"],
  ],
  "Li Be . . . . . . . . . . B C N O F Ne".split(" ").map((s, i) => [i, s]),
  "Na Mg . . . . . . . . . . Al Si P S Cl Ar".split(" ").map((s, i) => [i, s]),
  "K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr"
    .split(" ")
    .map((s, i) => [i, s]),
  "Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe"
    .split(" ")
    .map((s, i) => [i, s]),
  "Cs Ba . Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn"
    .split(" ")
    .map((s, i) => [i, s]),
  "Fr Ra . Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og"
    .split(" ")
    .map((s, i) => [i, s]),
  "La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu"
    .split(" ")
    .map((s, i) => [i + 2, s]),
  "Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr"
    .split(" ")
    .map((s, i) => [i + 2, s]),
];

export function PhaseElementPicker({
  elements,
  value,
  onChoose,
  onClose,
}: {
  elements: EditorData["structure"]["elements"];
  value: string;
  onChoose: (symbol: string) => void;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [text, setText] = useState(value);
  const [error, setError] = useState("");
  const choose = (symbol: string) => {
    const item = elements.find(
      (e) => e.symbol.toLowerCase() === symbol.trim().toLowerCase(),
    );
    if (!item?.enabled) {
      setError(
        item
          ? "No X-ray scattering data are available for this element."
          : "Choose a valid element symbol.",
      );
      return;
    }
    onChoose(item.symbol);
    onClose();
  };
  return createPortal(
    <Dialog
      onDismiss={onClose}
      dialogRef={dialog}
      className="phase-dialog pe-element-dialog"
      aria-label="Choose element"
      onCancel={(e) => {
        e.preventDefault();
        e.stopPropagation();
        onClose();
      }}
    >
      <DialogHeader
        title="Choose element"
        closeLabel="Close element picker"
        onClose={onClose}
      />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          e.stopPropagation();
          onClose();
        }}
      >
        <DialogHeader
          title="Choose element"
          closeLabel="Close element picker"
          onClose={onClose}
        />
        <form
          onSubmit={(e) => {
            e.preventDefault();
            choose(text);
          }}
        >
          <Input
            autoFocus
            aria-label="Element symbol"
            placeholder="Symbol, e.g. Fe"
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setError("");
            }}
          />
          <div className="pe-periodic-table">
            {rows.flatMap((row, r) =>
              row
                .filter(([, s]) => s !== ".")
                .map(([c, symbol]) => {
                  const element = elements.find((e) => e.symbol === symbol);
                  return (
                    <Button
                      key={String(symbol)}
                      type="button"
                      disabled={!element?.enabled}
                      aria-label={`Choose ${element?.name || symbol}`}
                      aria-pressed={
                        text.toLowerCase() === String(symbol).toLowerCase()
                      }
                      title={`${element?.number} · ${element?.name}${!element?.enabled ? " · no scattering data" : ""}`}
                      style={{
                        gridColumn: Number(c) + 1,
                        gridRow: r + 1 + (r >= 7 ? 1 : 0),
                      }}
                      onClick={() => choose(String(symbol))}
                    >
                      {String(symbol)}
                    </Button>
                  );
                }),
            )}
          </div>
          {error && (
            <p className="pe-edit-error" role="alert">
              {error}
            </p>
          )}
        </div>
        {error && (
          <p className="pe-edit-error" role="alert">
            {error}
          </p>
        )}
        <footer>
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button className="primary">Use element</button>
        </footer>
      </form>
    </Dialog>,
    document.querySelector(".app") || document.body,
  );
}
