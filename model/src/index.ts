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

    const anchorCol = pCols[0];
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

  .output('isRunning', (ctx) => ctx.outputs?.getIsReadyOrError() === false)

  .title(() => 'Humanization Score')

  .subtitle((ctx) => {
    if (ctx.data.customBlockLabel) return ctx.data.customBlockLabel;
    return 'Humanization Score';
  })

  .sections((_) => [
    { type: 'link', href: '/', label: 'Table' },
    { type: 'link', href: '/histogram', label: 'Score Distribution' },
  ])

  .done();
