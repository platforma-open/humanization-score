<script setup lang="ts">
import strings from '@milaboratories/strings';
import type { PlRef } from '@platforma-sdk/model';
import {
  PlAccordionSection,
  PlAgDataTableV2,
  PlAlert,
  PlBlockPage,
  PlBtnGhost,
  PlDropdownRef,
  PlMaskIcon24,
  PlNumberField,
  PlSlideModal,
  usePlDataTableSettingsV2,
} from '@platforma-sdk/ui-vue';
import { computed, ref, watch } from 'vue';
import { useApp } from '../app';

const app = useApp();

function setInput(inputRef?: PlRef) {
  if (!inputRef) return;
  app.model.data.inputAnchor = inputRef;
}

const tableSettings = usePlDataTableSettingsV2({
  model: () => app.model.outputs.pt,
});

// Coverage warnings (computed up front, also block the run) plus any non-fatal
// warnings the workflow emitted (e.g. no assemblable variable region).
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
    <PlDropdownRef
      v-model="app.model.data.inputAnchor"
      :options="app.model.outputs.inputOptions ?? []"
      :label="strings.titles.dataset"
      required
      @update:model-value="setInput"
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
          Sets the amount of memory available for the humanness score calculation. Increase for large datasets (&gt;10M sequences).
        </template>
      </PlNumberField>
    </PlAccordionSection>
  </PlSlideModal>
</template>
