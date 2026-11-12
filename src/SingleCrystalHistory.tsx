import { Undo2, Redo2 } from "lucide-react";
import { Button } from "./ui";
import type { CrystalData } from "./singleCrystalDomain";
import type { Run } from "./commandContracts";
export function SingleCrystalHistory({
  data,
  ready,
  run,
}: {
  data: CrystalData | null;
  ready: boolean;
  run: Run;
}) {
  return (
    <div
      className="navigation-group navigation-history"
      role="group"
      aria-label="Single-crystal edit history"
    >
      {[false, true].map((redo) => (
        <Button
          key={String(redo)}
          className="workspace-nav"
          aria-label={
            redo ? "Redo single-crystal edit" : "Undo single-crystal edit"
          }
          title={`${redo ? "Redo" : "Undo"}: ${(redo ? data?.redoLabel : data?.undoLabel) ?? "single-crystal edit"} · Last three edits · apply/reset drafts first`}
          disabled={!ready || !(redo ? data?.canRedo : data?.canUndo)}
          onClick={() =>
            void run(
              "scxrd_edit",
              { operation: redo ? "redo" : "undo" },
              "Restoring single-crystal decision…",
            )
          }
        >
          {redo ? <Redo2 size={20} /> : <Undo2 size={20} />}
        </Button>
      ))}
    </div>
  );
}
