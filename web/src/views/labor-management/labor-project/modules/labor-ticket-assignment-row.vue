<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { fetchDeleteLaborWorkHour, fetchUpdateLaborWorkHour } from '@/service/api';
import { $t } from '@/locales';
import { formatHours } from './ticket-workbench';

defineOptions({ name: 'LaborTicketAssignmentRow' });

type SelectOptionItem = { label: string; value: string };

interface Props {
  ticket: Api.LaborManagementManage.LaborWorkHour;
  workerOptions: SelectOptionItem[];
  defaultMonth: string;
  canAssign: boolean;
  canDelete: boolean;
}

const props = defineProps<Props>();

interface Emits {
  (e: 'changed'): void;
}

const emit = defineEmits<Emits>();

const workerId = ref<string | null>(props.ticket.workerId ?? null);
const allocationMonth = ref<string | null>(props.ticket.allocationMonth ?? props.defaultMonth);
const monthTouched = ref(Boolean(props.ticket.allocationMonth));
const saving = ref(false);
const deleting = ref(false);

const monthModel = computed({
  get: () => allocationMonth.value,
  set: (value: string | null) => {
    monthTouched.value = true;
    allocationMonth.value = value;
  }
});

watch(
  () => props.defaultMonth,
  value => {
    if (!monthTouched.value) allocationMonth.value = value;
  }
);

async function assign() {
  if (saving.value) return;
  if (!workerId.value || !allocationMonth.value) {
    window.$message?.warning($t('page.labor_management.labor_project.assignWorkerMonthRequired'));
    return;
  }
  saving.value = true;
  try {
    const { error } = await fetchUpdateLaborWorkHour({
      id: props.ticket.id,
      workerId: workerId.value,
      allocationMonth: allocationMonth.value
    });
    if (error) {
      window.$message?.error($t('page.labor_management.labor_project.assignFailed'));
      return;
    }
    window.$message?.success($t('page.labor_management.labor_project.assignSuccess'));
    emit('changed');
  } catch {
    window.$message?.error($t('page.labor_management.labor_project.assignFailed'));
  } finally {
    saving.value = false;
  }
}

async function remove() {
  if (deleting.value) return;
  deleting.value = true;
  try {
    const { error } = await fetchDeleteLaborWorkHour({ id: props.ticket.id });
    if (error) {
      window.$message?.error($t('page.labor_management.labor_project.deleteTicketFailed'));
      return;
    }
    window.$message?.success($t('page.labor_management.labor_project.ticketDeleted'));
    emit('changed');
  } catch {
    window.$message?.error($t('page.labor_management.labor_project.deleteTicketFailed'));
  } finally {
    deleting.value = false;
  }
}
</script>

<template>
  <div
    class="flex flex-wrap items-center gap-12px border-b border-gray-100 py-8px last:border-b-0 dark:border-gray-700"
  >
    <div class="min-w-140px">
      <div class="text-12px text-gray-400">{{ $t('page.labor_management.labor_work_hour.ticketCode') }}</div>
      <div class="font-medium">{{ ticket.ticketCode }}</div>
    </div>
    <div class="min-w-80px">
      <div class="text-12px text-gray-400">{{ $t('page.labor_management.labor_work_hour.workHours') }}</div>
      <div>{{ formatHours(Number(ticket.workHours)) }}</div>
    </div>
    <template v-if="canAssign">
      <NSelect
        v-model:value="workerId"
        :options="workerOptions"
        clearable
        filterable
        class="w-180px"
        :placeholder="$t('page.labor_management.labor_project.selectWorker')"
      />
      <NDatePicker
        v-model:formatted-value="monthModel"
        type="month"
        value-format="yyyy-MM-dd"
        :clearable="false"
        class="w-130px"
      />
      <NButton type="primary" size="small" :loading="saving" :disabled="!workerId || !allocationMonth" @click="assign">
        {{ $t('page.labor_management.labor_project.assign') }}
      </NButton>
    </template>
    <NPopconfirm v-if="canDelete" @positive-click="remove">
      <template #trigger>
        <NButton type="error" ghost size="small" :loading="deleting">{{ $t('common.delete') }}</NButton>
      </template>
      {{ $t('common.confirmDelete') }}
    </NPopconfirm>
  </div>
</template>
