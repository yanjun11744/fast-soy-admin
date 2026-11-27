<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { fetchAddLaborWorkHour } from '@/service/api';
import { $t } from '@/locales';
import LaborTicketAssignmentRow from './labor-ticket-assignment-row.vue';
import { isTicketAssigned } from './ticket-workbench';
import { useTicketCodeOcr } from './use-ticket-code-ocr';

defineOptions({ name: 'LaborTicketWorkbenchPanel' });

type SelectOptionItem = { label: string; value: string };

interface Props {
  order: Api.OrderManagementManage.Order;
  tickets: Api.LaborManagementManage.LaborWorkHour[];
  workerOptions: SelectOptionItem[];
  defaultMonth: string;
  canCreate: boolean;
  canAssign: boolean;
  canDelete: boolean;
}

const props = defineProps<Props>();

interface Emits {
  (e: 'changed'): void;
}

const emit = defineEmits<Emits>();

const ticketCode = ref('');
const workHours = ref<number | null>(null);
const workerId = ref<string | null>(null);
const allocationMonth = ref<string | null>(props.defaultMonth);
const monthTouched = ref(false);
const creating = ref(false);
const ticketImageInput = ref<HTMLInputElement | null>(null);
const ticketCodeInput = ref<{ focus?: () => void } | null>(null);
const supportsKeyboard = window.matchMedia?.('(pointer: fine)')?.matches ?? true;

const {
  options: ocrOptions,
  loading: ocrLoading,
  dragging: ticketDragging,
  handleChange,
  handleDrop,
  handlePaste,
  reset: resetOcr
} = useTicketCodeOcr(value => {
  ticketCode.value = value;
});

const monthModel = computed({
  get: () => allocationMonth.value,
  set: (value: string | null) => {
    monthTouched.value = true;
    allocationMonth.value = value;
  }
});

const unassignedTickets = computed(() => props.tickets.filter(ticket => !isTicketAssigned(ticket)));
const assignedCount = computed(() => props.tickets.length - unassignedTickets.value.length);

watch(
  () => props.defaultMonth,
  value => {
    if (!monthTouched.value) allocationMonth.value = value;
  }
);

onMounted(() => {
  // Put the cursor in the ticket-code field so a copied screenshot can be pasted at once.
  if (props.canCreate && supportsKeyboard) ticketCodeInput.value?.focus?.();
});

function handlePanelPaste(event: ClipboardEvent) {
  if (!props.canCreate) return;
  handlePaste(event);
}

async function createTicket() {
  if (creating.value || !props.canCreate) return;
  const code = ticketCode.value.trim();
  if (!code || code.length > 100) {
    window.$message?.warning($t('page.labor_management.labor_project.ticketCodeRequired'));
    return;
  }
  if (workHours.value === null || !Number.isFinite(workHours.value) || workHours.value < 0) {
    window.$message?.warning($t('page.labor_management.labor_project.workHoursRequired'));
    return;
  }
  if (workerId.value && !allocationMonth.value) {
    window.$message?.warning($t('page.labor_management.labor_project.selectMonth'));
    return;
  }
  creating.value = true;
  try {
    const { error } = await fetchAddLaborWorkHour({
      ticketCode: code,
      workHours: workHours.value,
      orderNo: props.order.orderNo,
      workerId: workerId.value,
      allocationMonth: allocationMonth.value
    });
    if (error) return;
    ticketCode.value = '';
    workHours.value = null;
    resetOcr();
    if (supportsKeyboard) ticketCodeInput.value?.focus?.();
    window.$message?.success(
      workerId.value && allocationMonth.value
        ? $t('page.labor_management.labor_project.createAndAssignSuccess')
        : $t('common.addSuccess')
    );
    emit('changed');
  } catch {
    window.$message?.error($t('page.labor_management.labor_project.createWorkHourFailed'));
  } finally {
    creating.value = false;
  }
}
</script>

<template>
  <div class="labor-ticket-panel" @paste="handlePanelPaste">
    <div class="mb-8px flex flex-wrap items-center justify-between gap-8px">
      <h3 class="labor-ticket-panel-heading">
        {{ $t('page.labor_management.labor_project.unassignedTicketList') }}
        <span v-if="unassignedTickets.length" class="labor-ticket-panel-count">{{ unassignedTickets.length }}</span>
      </h3>
      <span v-if="assignedCount" class="text-12px text-gray-400">
        {{ $t('page.labor_management.labor_project.assignedHidden', { count: assignedCount }) }}
      </span>
    </div>

    <div
      v-if="canCreate"
      class="ticket-create-form mb-12px rounded-6px border border-dashed p-12px transition-colors"
      :class="ticketDragging ? 'border-primary bg-primary/5' : 'border-gray-300 dark:border-gray-600'"
      @dragover.prevent="ticketDragging = true"
      @dragleave.prevent="ticketDragging = false"
      @drop.prevent="handleDrop"
    >
      <div class="flex flex-wrap items-end gap-10px">
        <div class="min-w-240px flex-1">
          <div class="ticket-field-label">{{ $t('page.labor_management.labor_work_hour.ticketCode') }}</div>
          <div class="flex items-stretch gap-8px">
            <NInput
              ref="ticketCodeInput"
              v-model:value="ticketCode"
              class="flex-1"
              :maxlength="100"
              :disabled="creating"
              :placeholder="$t('page.labor_management.labor_work_hour.form.ticketCode')"
            />
            <NButton class="shrink-0" :loading="ocrLoading" :disabled="creating" @click="ticketImageInput?.click()">
              <template #icon>
                <icon-ic-round-image class="text-icon" />
              </template>
              {{ $t('page.labor_management.labor_project.ocrUploadShort') }}
            </NButton>
          </div>
        </div>
        <div class="w-130px">
          <div class="ticket-field-label">{{ $t('page.labor_management.labor_work_hour.workHours') }}</div>
          <NInputNumber
            v-model:value="workHours"
            :min="0"
            :precision="2"
            :disabled="creating"
            :placeholder="$t('page.labor_management.labor_work_hour.form.workHours')"
            class="w-full"
          />
        </div>
        <div class="w-180px">
          <div class="ticket-field-label">{{ $t('page.labor_management.labor_work_hour.worker') }}</div>
          <NSelect
            v-model:value="workerId"
            :options="workerOptions"
            clearable
            filterable
            :disabled="creating"
            :placeholder="$t('page.labor_management.labor_project.selectWorker')"
          />
        </div>
        <div class="w-130px">
          <div class="ticket-field-label">{{ $t('page.labor_management.labor_work_hour.allocationMonth') }}</div>
          <NDatePicker
            v-model:formatted-value="monthModel"
            type="month"
            value-format="yyyy-MM-dd"
            clearable
            class="w-full"
          />
        </div>
        <NButton type="primary" class="shrink-0" :loading="creating" @click="createTicket">
          {{
            workerId && allocationMonth
              ? $t('page.labor_management.labor_project.createAndAssign')
              : $t('page.labor_management.labor_project.createTicket')
          }}
        </NButton>
      </div>
      <div class="mt-8px text-12px text-gray-400">{{ $t('page.labor_management.labor_project.ticketImageHint') }}</div>
      <NSelect
        v-if="ocrOptions.length"
        class="mt-8px"
        :options="ocrOptions"
        :placeholder="$t('page.labor_management.labor_work_hour.ocrSelect')"
        @update:value="value => (ticketCode = value)"
      />
      <input
        ref="ticketImageInput"
        type="file"
        accept="image/*"
        class="hidden"
        :disabled="ocrLoading"
        @change="handleChange"
      />
    </div>

    <NEmpty
      v-if="!unassignedTickets.length"
      :description="$t('page.labor_management.labor_project.noUnassignedTickets')"
    />
    <LaborTicketAssignmentRow
      v-for="ticket in unassignedTickets"
      :key="ticket.id"
      :ticket="ticket"
      :worker-options="workerOptions"
      :default-month="defaultMonth"
      :can-assign="canAssign"
      :can-delete="canDelete"
      @changed="emit('changed')"
    />
  </div>
</template>

<style scoped>
.labor-ticket-panel {
  margin-block: 12px;
  margin-inline: clamp(12px, 2.5vw, 24px) 12px;
  border-inline-start: 2px solid var(--n-merged-border-color, var(--n-border-color));
  padding-inline-start: 12px;
}

.labor-ticket-panel-heading {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 0;
  color: var(--n-th-text-color, var(--n-text-color));
  font-size: 13px;
  font-weight: 600;
}

.labor-ticket-panel-count {
  color: var(--n-td-text-color, var(--n-text-color));
  font-size: 12px;
  font-weight: 400;
  font-variant-numeric: tabular-nums;
}

.ticket-field-label {
  margin-bottom: 4px;
  color: var(--n-text-color-3, rgb(156 163 175));
  font-size: 12px;
  line-height: 1.5;
}
</style>
