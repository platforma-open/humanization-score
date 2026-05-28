import { platforma } from '@platforma-open/milaboratories.humanization-score.model';
import { defineAppV3 } from '@platforma-sdk/ui-vue';
import MainPage from './pages/MainPage.vue';

export const sdkPlugin = defineAppV3(platforma, (app) => {
  app.model.data.customBlockLabel ??= '';

  return {
    routes: {
      '/': () => MainPage,
    },
  };
});

export const useApp = sdkPlugin.useApp;
