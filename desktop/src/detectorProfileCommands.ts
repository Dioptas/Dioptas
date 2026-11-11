import type { CommandPayload } from "./commandContracts";
import type { Response } from "./types";

export type ProfileCommandName = "cake_profile" | "save_cake_profile";
/** The existing detector callback channel returns profile data or a save
 * acknowledgement; exports do not promise a saved path through this channel. */
export type ProfileReply = Pick<
  Response,
  "ok" | "error" | "cancelled" | "cakeProfile"
>;
export type ProfileInvocation = {
  [C in ProfileCommandName]: [
    command: C,
    payload: CommandPayload<C>,
    message?: string,
  ];
}[ProfileCommandName];
export type ProfileRunInvocation = {
  [C in ProfileCommandName]: [
    command: C,
    payload: CommandPayload<C>,
    message?: string,
    onSuccess?: (reply: ProfileReply) => void,
  ];
}[ProfileCommandName];
export type ProfileRun = (...call: ProfileRunInvocation) => Promise<void>;
