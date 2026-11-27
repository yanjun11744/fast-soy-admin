<script setup lang="ts">
import { ref } from 'vue';
import { $t } from '@/locales';
import LaborProjectManage from './modules/labor-project-manage.vue';
import LaborTicketWorkbench from './modules/labor-ticket-workbench.vue';

defineOptions({ name: 'LaborProject' });

const activeTab = ref('workbench');
</script>

<template>
  <div class="h-full flex-col-stretch overflow-hidden lt-sm:overflow-auto">
    <NTabs v-model:value="activeTab" :animated="false" class="h-full" pane-class="labor-project-tab-pane flex-1-hidden">
      <NTabPane name="workbench" :tab="$t('page.labor_management.labor_project.workbenchTab')">
        <LaborTicketWorkbench @manage-projects="activeTab = 'projects'" />
      </NTabPane>
      <NTabPane name="projects" :tab="$t('page.labor_management.labor_project.projectsTab')">
        <LaborProjectManage />
      </NTabPane>
    </NTabs>
  </div>
</template>

<style scoped>
:deep(.labor-project-tab-pane) {
  padding: 0;
}
</style>
