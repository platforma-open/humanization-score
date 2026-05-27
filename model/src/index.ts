import type {
  PlDataTableStateV2,
  PlRef,
} from '@platforma-sdk/model';
import {
  BlockModelV3,
  DataModelBuilder,
  createPlDataTableStateV2,
  createPlDataTableV2,
} from '@platforma-sdk/model';
export type * from '@milaboratories/helpers';

export type Modality = 'antibody' | 'peptide';

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
  modality?: Modality;
  mem?: number;
  tableState: PlDataTableStateV2;
};

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
      customBlockLabel: data.customBlockLabel,
      inputAnchor: data.inputAnchor,
      mem: data.mem,
    };
  })

  .output('inputOptions', (ctx) =>
    ctx.resultPool.getOptions([{
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
    }, {
      axes: [
        { name: 'pl7.app/sampleId' },
        { name: 'pl7.app/variantKey' },
      ],
      annotations: { 'pl7.app/isAnchor': 'true' },
    }]),
  )

  .output('modality', (ctx) => {
    const ref = ctx.data.inputAnchor;
    if (ref === undefined) return undefined;
    const spec = ctx.resultPool.getPColumnSpecByRef(ref);
    if (!spec) return undefined;
    return spec.axesSpec[1]?.name === 'pl7.app/variantKey' ? 'peptide' : 'antibody';
  }, { retentive: true })

  .outputWithStatus('pt', (ctx) => {
    const pCols = ctx.outputs?.resolve('outputLiabilities')?.getPColumns();
    if (pCols === undefined) {
      return undefined;
    }
    return createPlDataTableV2(
      ctx,
      pCols,
      ctx.data.tableState,
    );
  })

  .output('isRunning', (ctx) => ctx.outputs?.getIsReadyOrError() === false)

  .title(() => 'Humanness Score')

  .subtitle((ctx) => ctx.data.customBlockLabel || 'Humanness Score')

  .sections((_) => [
    { type: 'link', href: '/', label: 'Table' },
  ])

  .done();
