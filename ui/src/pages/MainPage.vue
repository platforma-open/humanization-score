<script setup lang="ts">
import strings from "@milaboratories/strings";
import type { DatasetSelection } from "@platforma-sdk/model";
import { createDatasetSelection, createPrimaryRef } from "@platforma-sdk/model";
import {
  PlAccordionSection,
  PlAgDataTableV2,
  PlAlert,
  PlBlockPage,
  PlBtnGhost,
  PlDatasetSelector,
  PlMaskIcon24,
  PlNumberField,
  PlSlideModal,
  usePlDataTableSettingsV2,
} from "@platforma-sdk/ui-vue";
import { computed, ref, watch } from "vue";
import { useApp } from "../app";

const app = useApp();

// The selector picks a dataset, or a dataset narrowed by one of its subset columns.
// Stored as two refs so blocks saved before filters existed keep their `inputAnchor`.
const datasetSelection = computed<DatasetSelection | undefined>({
  get: () => {
    const { inputAnchor, filterRef } = app.model.data;
    if (inputAnchor === undefined) return undefined;
    return createDatasetSelection(createPrimaryRef(inputAnchor, filterRef));
  },
  set: (selection) => {
    // Never cleared, as before: the selector is required and not clearable
    if (!selection) return;
    app.model.data.inputAnchor = selection.primary.column;
    app.model.data.filterRef = selection.primary.filter;
  },
});

const tableSettings = usePlDataTableSettingsV2({
  model: () => app.model.outputs.pt,
});

const warnings = computed<string[]>(() => [
  ...(app.model.outputs.coverageWarnings ?? []),
  ...(app.model.outputs.warnings ?? []),
]);

const settingsIsShown = ref(app.model.data.inputAnchor === undefined);

const resourceSectionOpen = ref(false);

watch(
  () => app.model.outputs.isRunning,
  (isRunning, wasRunning) => {
    if (isRunning && !wasRunning) {
      settingsIsShown.value = false;
    }
  },
);
</script>

<template>
  <PlBlockPage
    v-model:subtitle="app.model.data.customBlockLabel"
    subtitle-placeholder="Humanness Score"
    title="Humanness Score"
  >
    <template #append>
      <PlBtnGhost @click.stop="settingsIsShown = true">
        {{ strings.titles.settings }}
        <template #append>
          <PlMaskIcon24 name="settings" />
        </template>
      </PlBtnGhost>
    </template>
    <PlAlert
      v-for="(message, i) in warnings"
      :key="i"
      type="warn"
      label="Humanness score not computed"
    >
      {{ message }}
    </PlAlert>
    <PlAgDataTableV2
      v-model="app.model.data.tableState"
      :settings="tableSettings"
      show-export-button
      :not-ready-text="strings.callToActions.configureSettingsAndRun"
      :no-rows-text="strings.states.noDataAvailable"
    />
  </PlBlockPage>

  <PlSlideModal v-model="settingsIsShown">
    <template #title>{{ strings.titles.settings }}</template>
    <PlDatasetSelector
      v-model="datasetSelection"
      :options="app.model.outputs.inputOptions ?? []"
      :label="strings.titles.dataset"
      required
    />

    <PlAccordionSection v-model="resourceSectionOpen" label="Resource Allocation">
      <PlNumberField
        v-model="app.model.data.mem"
        label="Memory (GiB)"
        :minValue="1"
        :step="1"
        :maxValue="1012"
      >
        <template #tooltip>
          Sets the amount of memory available for the humanness score calculation. Increase for
          large datasets (&gt;10M sequences).
        </template>
      </PlNumberField>
    </PlAccordionSection>
  </PlSlideModal>
</template>
