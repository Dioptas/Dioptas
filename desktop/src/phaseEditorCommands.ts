import type {
  PhaseEditorInvocation,
  PhaseEditorRunInvocation,
} from "./phaseEditorTypes";
/** Every supported native editor command accepts these same target fields.
 * Adding them preserves the operation/payload pair and avoids component casts. */
export function phaseEditorInvocation(
  call: PhaseEditorRunInvocation,
  uid: string,
): PhaseEditorInvocation {
  return [
    call[0],
    { ...call[1], editor_uid: uid, editor_only: true },
  ] as PhaseEditorInvocation;
}
