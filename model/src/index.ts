import type { GraphMakerState } from '@milaboratories/graph-maker';
import type {
  PColumnIdAndSpec,
  PFrameHandle,
  PlDataTableStateV2,
  PlRef,
} from '@platforma-sdk/model';
import {
  BlockModelV3,
  DataModelBuilder, createPFrameForGraphs,
  createPlDataTableStateV2,
  createPlDataTableV3,
} from '@platforma-sdk/model';
export type * from '@milaboratories/helpers';

type OldArgs = {
  customBlockLabel: string;
  inputAnchor?: PlRef;
  mem?: number;
};

type OldUiState = {
  tableState: PlDataTableStateV2;
  graphStateHistogram?: GraphMakerState;
};

export type BlockData = {
  customBlockLabel: string;
  inputAnchor?: PlRef;
  mem?: number;
  tableState: PlDataTableStateV2;
  // Distribution of the per-clonotype humanness score across the whole dataset.
  graphStateHistogram: GraphMakerState;
};

// Humanness score column name emitted by `clonotype-process.tpl.tengo`.
// All per-chain score columns share this name; single-cell chains are
// distinguished only by the `CHAIN_DOMAIN` domain entry below.
export const HUMANNESS_SCORE_COLUMN = 'pl7.app/humannessScore';

// Domain key carried by single-cell per-chain score columns. Value is the
// chain TYPE: 'A' = Heavy, 'B' = Light (matches the upstream producer's
// `pl7.app/vdj/scClonotypeChain` convention). Bulk columns have no
// scClonotypeChain domain key (they still carry pl7.app/contentTag).
export const CHAIN_DOMAIN = 'pl7.app/vdj/scClonotypeChain';
export const CHAIN_HEAVY = 'A';
export const CHAIN_LIGHT = 'B';

export const defaultGraphStateHistogram = (): GraphMakerState => ({
  title: 'Humanness Score Distribution',
  template: 'bins',
  currentTab: null,
  axesSettings: {
    other: { binsCount: 20 },
  },
  // Give the bars a solid fill instead of the default white — colour values
  // taken from graph-maker's fixed palette ("Blue").
  layersSettings: {
    bins: { fillColor: '#2D93FA' },
  },
});

// Selectors for the input dataset anchor — shared between `inputOptions`
// (the dropdown) and `subtitle` (so the default label matches the dataset name).
//
// Humanness scoring applies to ANTIBODIES only, so we offer Ig datasets only:
//   - bulk: the clonotypeKey axis carries `pl7.app/vdj/chain` set to the
//           producer's chainInfos KEYS — IG = {IGHeavy, IGLight} (NOT the mixcr
//           filter values IGH/IGK/IGL). Axis-domain matching can't express a
//           value set, so we emit one selector per allowed chain (OR-ed).
//   - single-cell: the scClonotypeKey axis carries `pl7.app/vdj/receptor == 'IG'`.
// TCR datasets (TR* / TCRAB / TCRGD) are therefore never offered. The workflow
// guard (main.tpl.tengo) is the backstop (hard-fail ll.panic) if a TCR dataset
// is forced — TCR is a hard reject per spec R5.
//
// NOTE: we cannot express "has a VDJRegionInFrame sequence column" here because
// that lives on the sequence columns, not the anchor axis. CDR3-assembled
// (no full VDJRegion) Ig datasets are therefore still OFFERED by these
// selectors. They are NO LONGER hard-rejected: per spec §3a/§7 such datasets are
// now ACCEPTED and produce a NULL/empty humanness result plus a non-fatal
// warning (instructing the user to re-run clonotyping assembled by VDJRegion);
// the run completes without crashing. Only TCR input is hard-rejected. The
// selectors stay Ig-only and never filtered on VDJRegion availability.
const BULK_CHAINS = ['IGHeavy', 'IGLight'];
const inputSelectors = [
  ...BULK_CHAINS.map((chain) => ({
    axes: [
      { name: 'pl7.app/sampleId' },
      { name: 'pl7.app/vdj/clonotypeKey', domain: { 'pl7.app/vdj/chain': chain } },
    ],
    annotations: { 'pl7.app/isAnchor': 'true' },
  })),
  {
    axes: [
      { name: 'pl7.app/sampleId' },
      { name: 'pl7.app/vdj/scClonotypeKey', domain: { 'pl7.app/vdj/receptor': 'IG' } },
    ],
    annotations: { 'pl7.app/isAnchor': 'true' },
  },
];

const dataModel = new DataModelBuilder()
  .from<BlockData>('v1')
  .upgradeLegacy<OldArgs, OldUiState>(({ args, uiState }) => ({
    ...args,
    tableState: uiState.tableState,
    graphStateHistogram: uiState.graphStateHistogram ?? defaultGraphStateHistogram(),
  }))
  .init(() => ({
    customBlockLabel: '',
    tableState: createPlDataTableStateV2(),
    graphStateHistogram: defaultGraphStateHistogram(),
  }));

export const platforma = BlockModelV3.create(dataModel)

  .args((data) => {
    if (!data.inputAnchor) throw new Error('Input anchor is required');

    return {
      // Empty when unset; the workflow falls back to the input dataset name so
      // the provenance trace label matches the block subtitle.
      customBlockLabel: data.customBlockLabel || '',
      inputAnchor: data.inputAnchor,
      mem: data.mem,
    };
  })

  .output('inputOptions', (ctx) =>
    ctx.resultPool.getOptions(inputSelectors),
  )

  .outputWithStatus('pt', (ctx) => {
    const pCols = ctx.outputs?.resolve('outputHumanness')?.getPColumns();
    if (pCols === undefined) {
      return undefined;
    }

    const anchorCol
      = pCols.find((c) => c.spec.domain?.[CHAIN_DOMAIN] === CHAIN_HEAVY)
        ?? pCols[0];

    if (anchorCol === undefined) {
      return undefined;
    }

    return createPlDataTableV3(ctx, {
      tableState: ctx.data.tableState,
      columns: {
        anchors: { main: anchorCol.spec },
        selector: { mode: 'enrichment' },
      },
    });
  })

  .outputWithStatus('histogramPf', (ctx): PFrameHandle | undefined => {
    const pCols = ctx.outputs?.resolve('outputHumanness')?.getPColumns();
    if (pCols === undefined) return undefined;
    return createPFrameForGraphs(ctx, pCols);
  })

  .output('histogramPfPcols', (ctx): PColumnIdAndSpec[] | undefined => {
    const pCols = ctx.outputs?.resolve('outputHumanness')?.getPColumns();
    if (pCols === undefined || pCols.length === 0) return undefined;
    return pCols.map((c) => ({ columnId: c.id, spec: c.spec }));
  })

  // Non-fatal warnings emitted by the workflow (e.g. "no full variable region
  // available" for CDR3-assembled datasets). Empty array when scoring succeeded.
  // The UI renders these as a non-blocking banner; the run still completes.
  .output('warnings', (ctx) =>
    ctx.outputs?.resolve('warnings')?.getDataAsJson<string[]>() ?? [],
  )

  .output('isRunning', (ctx) => ctx.outputs?.getIsReadyOrError() === false)

  .title(() => 'Humanness Score')

  .subtitle((ctx) => {
    if (ctx.data.customBlockLabel) return ctx.data.customBlockLabel;
    return 'Humanness Score';
  })

  .sections((_) => [
    { type: 'link', href: '/', label: 'Table' },
    { type: 'link', href: '/histogram', label: 'Score Distribution' },
  ])

  .done();
