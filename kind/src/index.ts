import { assertParamsObject, defineBlockKind } from "@platforma-sdk/block-kind";
import type { PlRef } from "@platforma-sdk/model";
import { isPlRef } from "@platforma-sdk/model";
import { name, version } from "../package.json" with { type: "json" };

/**
 * This block's init-params contract — everything a user sets by hand: the
 * upstream dataset to score, the subtitle they type, and the memory override.
 *
 * Left out: `coverageWarnings`, which the UI mirrors from the block's own
 * output and is not user input, and the table / histogram view state.
 *
 * Every field is optional because the projection hands live state back
 * untouched, and a block whose input is not picked yet holds `undefined` there.
 * Requiring one would make the block export a file its own kind refuses to
 * apply, so export and apply would stop being inverses.
 */
export type BlockParams = {
  inputAnchor?: PlRef;
  customBlockLabel?: string;
  mem?: number;
};

/** The same contract at runtime, for params arriving from a template file rather than typed code. */
function parseInitializationParams(value: unknown): BlockParams {
  assertParamsObject(value);

  const { inputAnchor, customBlockLabel, mem } = value;

  if (inputAnchor !== undefined && !isPlRef(inputAnchor)) {
    throw new Error(
      "'inputAnchor' must be a reference to an upstream column, written as { block, name }.",
    );
  }
  if (customBlockLabel !== undefined && typeof customBlockLabel !== "string") {
    throw new Error("'customBlockLabel' must be a string.");
  }
  if (mem !== undefined && typeof mem !== "number") {
    throw new Error("'mem' must be a number (gigabytes of memory for the score calculation).");
  }

  return { inputAnchor, customBlockLabel, mem };
}

// Identity (`name`/`version`) comes from this package's own `package.json`, so
// the on-wire `{name}@{version}` reference can never drift from what npm
// publishes; the bundler inlines the JSON import.
export const kind = defineBlockKind<BlockParams>({ name, version, parseInitializationParams });
