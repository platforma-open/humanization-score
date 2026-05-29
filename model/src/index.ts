import type {
  PlDataTableStateV2,
  PlRef,
} from '@platforma-sdk/model';
import {
  ArrayColumnProvider,
  BlockModelV3,
  DataModelBuilder,
  createPlDataTableStateV2,
  createPlDataTableV3,
  plRefsEqual,
} from '@platforma-sdk/model';
export type * from '@milaboratories/helpers';

type OldArgs = {
  customBlockLabel: string;
  inputAnchor?: PlRef;
  mem?: number;
};

type OldUiState = {
  tableState: PlDataTableStateV2;
};

export type BlockData = {
  customBlockLabel: string;
  inputAnchor?: PlRef;
  mem?: number;
  tableState: PlDataTableStateV2;
};

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
  }))
  .init(() => ({
    customBlockLabel: '',
    tableState: createPlDataTableStateV2(),
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

  .output('isRunning', (ctx) => ctx.outputs?.getIsReadyOrError() === false)

  .title(() => 'Humanization Score')

  .subtitle((ctx) => {
    // An explicit, user-set label always wins.
    if (ctx.data.customBlockLabel) return ctx.data.customBlockLabel;
    // Otherwise default to the selected input dataset's name, so the subtitle
    // carries context instead of duplicating the "Humanization Score" title.
    if (ctx.data.inputAnchor) {
      const selected = ctx.resultPool
        .getOptions(inputSelectors)
        ?.find((opt) => plRefsEqual(opt.ref, ctx.data.inputAnchor!, true));
      if (selected?.label) return selected.label;
    }
    return 'Humanization Score';
  })

  .sections((_) => [
    { type: 'link', href: '/', label: 'Table' },
  ])

  .done();
