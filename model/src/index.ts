import type { GraphMakerState } from '@milaboratories/graph-maker';
import type {
  PColumnIdAndSpec,
  PFrameHandle,
  PlDataTableStateV2,
  PlRef,
} from '@platforma-sdk/model';
import {
  ArrayColumnProvider,
  BlockModelV3,
  DataModelBuilder,
  createPFrameForGraphs,
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
  graphStateBoxplot?: GraphMakerState;
};

export type BlockData = {
  customBlockLabel: string;
  inputAnchor?: PlRef;
  mem?: number;
  tableState: PlDataTableStateV2;
  // Distribution of the per-clonotype humanness score across the whole dataset.
  graphStateHistogram: GraphMakerState;
  // Per-sample distribution of humanness (box/violin), grouped by sampleId.
  graphStateBoxplot: GraphMakerState;
};

// Humanness score column name emitted by `clonotype-process.tpl.tengo`.
export const HUMANNESS_SCORE_COLUMN = 'pl7.app/humannessScore';

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

export const defaultGraphStateBoxplot = (): GraphMakerState => ({
  title: 'Humanness by Sample',
  template: 'box',
  currentTab: null,
  // Solid fill for the boxes (graph-maker fixed palette, "Teal") so the
  // per-sample plot isn't drawn in white.
  layersSettings: {
    box: { fillColor: '#27C2C2' },
  },
});

// Selectors for the input dataset anchor — shared between `inputOptions`
// (the dropdown) and `subtitle` (so the default label matches the dataset name).
const inputSelectors = [{
  axes: [
    { name: 'pl7.app/sampleId' },
    { name: 'pl7.app/vdj/clonotypeKey' },
  ],
  annotations: { 'pl7.app/isAnchor': 'true' },
}, {
  axes: [
    { name: 'pl7.app/sampleId' },
    { name: 'pl7.app/vdj/scClonotypeKey' },
  ],
  annotations: { 'pl7.app/isAnchor': 'true' },
}];

const dataModel = new DataModelBuilder()
  .from<BlockData>('v1')
  .upgradeLegacy<OldArgs, OldUiState>(({ args, uiState }) => ({
    ...args,
    tableState: uiState.tableState,
    graphStateHistogram: uiState.graphStateHistogram ?? defaultGraphStateHistogram(),
    graphStateBoxplot: uiState.graphStateBoxplot ?? defaultGraphStateBoxplot(),
  }))
  .init(() => ({
    customBlockLabel: '',
    tableState: createPlDataTableStateV2(),
    graphStateHistogram: defaultGraphStateHistogram(),
    graphStateBoxplot: defaultGraphStateBoxplot(),
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
    return createPlDataTableV3(ctx, {
      tableState: ctx.data.tableState,
      columns: new ArrayColumnProvider(pCols)
        .getAllColumns()
        .map((column) => ({ column, isPrimary: true })),
    });
  })

  // --- Score distribution (histogram) ---------------------------------------
  // One row per clonotype, so the histogram counts UNIQUE clonotypes by humanness
  // score — it is deliberately NOT weighted by clonotype abundance. The question it
  // answers is "how many distinct candidates sit below/above a humanness level"
  // (i.e. how much humanization work is there), not "how human is the repertoire by
  // read mass". No human-like threshold line is drawn: this score is a 9-mer
  // fraction rescaled to 0..100, not a cutoff validated against therapeutic mAbs.
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

  // --- Per-sample distribution (box / violin) --------------------------------
  // The humanness column is keyed by clonotypeKey only (sample-agnostic). To get
  // a per-sample view we join it with the input dataset's primary abundance
  // column, which carries the [sampleId, clonotypeKey] axes. graph-maker joins on
  // the shared clonotypeKey axis, so each (sample, clonotype) pair contributes the
  // clonotype's score — grouping by sampleId then yields a distribution per sample.
  // This is a box/violin (median + spread + tails) on purpose, not a per-sample
  // mean: the spread is exactly what a single mean would hide.
  // Degrades gracefully: if the dataset has no primary-abundance column the join
  // adds nothing, the sampleId axis is absent, and the page simply can't preselect
  // a grouping (the chart still opens). VDJ datasets almost always carry abundance.
  .outputWithStatus('perSamplePf', (ctx): PFrameHandle | undefined => {
    const humanness = ctx.outputs?.resolve('outputHumanness')?.getPColumns();
    if (humanness === undefined) return undefined;

    const ref = ctx.data.inputAnchor;
    if (ref === undefined) return undefined;

    const abundance = ctx.resultPool.getAnchoredPColumns({ main: ref }, [{
      axes: [{ anchor: 'main', idx: 0 }, { anchor: 'main', idx: 1 }],
      annotations: {
        'pl7.app/isAbundance': 'true',
        'pl7.app/abundance/normalized': 'false',
        'pl7.app/abundance/isPrimary': 'true',
      },
    }]);

    return createPFrameForGraphs(ctx, [...humanness, ...(abundance ?? [])]);
  })

  .output('perSamplePfPcols', (ctx): PColumnIdAndSpec[] | undefined => {
    const humanness = ctx.outputs?.resolve('outputHumanness')?.getPColumns();
    if (humanness === undefined || humanness.length === 0) return undefined;

    const ref = ctx.data.inputAnchor;
    if (ref === undefined) return undefined;

    const abundance = ctx.resultPool.getAnchoredPColumns({ main: ref }, [{
      axes: [{ anchor: 'main', idx: 0 }, { anchor: 'main', idx: 1 }],
      annotations: {
        'pl7.app/isAbundance': 'true',
        'pl7.app/abundance/normalized': 'false',
        'pl7.app/abundance/isPrimary': 'true',
      },
    }]);

    return [...humanness, ...(abundance ?? [])].map((c) => ({ columnId: c.id, spec: c.spec }));
  })

  .output('isRunning', (ctx) => ctx.outputs?.getIsReadyOrError() === false)

  .title(() => 'Humanization Score')

  .subtitle((ctx) => {
    if (ctx.data.customBlockLabel) return ctx.data.customBlockLabel;
    return 'Humanization Score';
  })

  .sections((_) => [
    { type: 'link', href: '/', label: 'Table' },
    { type: 'link', href: '/histogram', label: 'Score Distribution' },
    { type: 'link', href: '/by-sample', label: 'By Sample' },
  ])

  .done();
