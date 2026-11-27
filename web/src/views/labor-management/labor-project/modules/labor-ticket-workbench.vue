<script setup lang="tsx">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import type { DataTableColumns } from 'naive-ui';
import { NButton, NTag } from 'naive-ui';
import { useAppStore } from '@/store/modules/app';
import { useAuth } from '@/hooks/business/auth';
import { $t } from '@/locales';
import LaborTicketWorkbenchPanel from './labor-ticket-workbench-panel.vue';
import {
  buildWorkbenchRows,
  currentMonthValue,
  filterWorkbenchRows,
  formatHours,
  summarizeWorkbench,
  type WorkbenchRow,
  type WorkbenchStatus
} from './ticket-workbench';
import { useTicketWorkbenchData } from './use-ticket-workbench-data';

defineOptions({ name: 'LaborTicketWorkbench' });

interface Emits {
  (e: 'manageProjects'): void;
}

const emit = defineEmits<Emits>();
const appStore = useAppStore();
const { hasAuth } = useAuth();
const {
  projects,
  orders,
  ticketsByOrder,
  workerOptions,
  loading,
  failed,
  workersLoading,
  workersFailed,
  loadWorkers,
  loadAll,
  reloadOrderTickets
} = useTicketWorkbenchData();

const canCreate = computed(() => hasAuth('B_LABOR_MANAGEMENT_LABOR_WORK_HOUR_CREATE'));
const canAssign = computed(() => hasAuth('B_LABOR_MANAGEMENT_LABOR_WORK_HOUR_EDIT'));
const canDelete = computed(() => hasAuth('B_LABOR_MANAGEMENT_LABOR_WORK_HOUR_DELETE'));

const importMonth = ref<string | null>(currentMonthValue());
const statsMonth = ref<string | null>(currentMonthValue());
const statsMonthTouched = ref(false);
const statsMonthModel = computed({
  get: () => statsMonth.value,
  set: (value: string | null) => {
    statsMonthTouched.value = true;
    statsMonth.value = value;
  }
});
const statsMonthKey = computed(() => statsMonth.value ?? currentMonthValue());
const keyword = ref('');
const statusFilter = ref<WorkbenchStatus>('pending');
const statusValue = computed({
  get: () => statusFilter.value,
  set: (value: string | number | null) => {
    statusFilter.value = value === 'completed' || value === 'all' ? value : 'pending';
  }
});
const statusOptions = computed(() => [
  { label: $t('page.labor_management.labor_project.statusPending'), value: 'pending' },
  { label: $t('page.labor_management.labor_project.statusCompleted'), value: 'completed' },
  { label: $t('page.labor_management.labor_project.statusAll'), value: 'all' }
]);

const expandedRowKeys = ref<string[]>([]);

const projectsByPartNo = computed(() => new Map(projects.value.map(project => [project.partNo, project])));
const rows = computed(() =>
  buildWorkbenchRows(orders.value, ticketsByOrder.value, projectsByPartNo.value, statsMonthKey.value)
);
const filteredRows = computed(() => filterWorkbenchRows(rows.value, statusFilter.value, keyword.value));
const stats = computed(() => summarizeWorkbench(rows.value, statsMonthKey.value));
const unmatchedProjects = computed(() => {
  const matched = new Set(orders.value.map(order => order.partNo));
  return projects.value.filter(project => !matched.has(project.partNo));
});
const emptyDescription = computed(() => {
  if (!projects.value.length && importMonth.value) {
    return $t('page.labor_management.labor_project.emptyMonthHint');
  }
  return statusFilter.value === 'pending'
    ? $t('page.labor_management.labor_project.noPendingOrders')
    : $t('page.labor_management.labor_project.noMatchedOrders');
});

const pagination = reactive({
  page: 1,
  pageSize: 20,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  prefix: (info: { itemCount?: number }) => $t('datatable.itemCount', { total: info.itemCount ?? 0 }),
  onUpdatePage: (page: number) => {
    pagination.page = page;
  },
  onUpdatePageSize: (pageSize: number) => {
    pagination.page = 1;
    pagination.pageSize = pageSize;
  }
});

watch(filteredRows, () => {
  const maxPage = Math.max(1, Math.ceil(filteredRows.value.length / pagination.pageSize));
  if (pagination.page > maxPage) pagination.page = 1;
});

watch(importMonth, value => {
  if (!statsMonthTouched.value && value) statsMonth.value = value;
  expandedRowKeys.value = [];
  void loadAll(value);
});

watch(orders, nextOrders => {
  const orderIds = new Set(nextOrders.map(order => order.id));
  expandedRowKeys.value = expandedRowKeys.value.filter(key => orderIds.has(key));
});

function refresh() {
  void loadAll(importMonth.value);
}

async function copyOrderNo(value: string) {
  try {
    await navigator.clipboard.writeText(value);
    window.$message?.success($t('page.labor_management.labor_project.copied'));
  } catch {
    window.$message?.error($t('page.labor_management.labor_project.copyFailed'));
  }
}

function toggleRow(row: WorkbenchRow) {
  expandedRowKeys.value = expandedRowKeys.value.includes(row.id)
    ? expandedRowKeys.value.filter(key => key !== row.id)
    : [...expandedRowKeys.value, row.id];
}

const columns = computed<DataTableColumns<WorkbenchRow>>(() => {
  const workers = workerOptions.value;
  const defaultMonth = statsMonthKey.value;
  const allowCreate = canCreate.value;
  const allowAssign = canAssign.value;
  const allowDelete = canDelete.value;
  return [
  {
    type: 'expand',
    expandable: () => true,
    renderExpand: row => (
      <LaborTicketWorkbenchPanel
        order={row.order}
        tickets={row.tickets}
        workerOptions={workers}
        defaultMonth={defaultMonth}
        canCreate={allowCreate && !row.noPainting}
        canAssign={allowAssign}
        canDelete={allowDelete}
        onChanged={() => void reloadOrderTickets(row.order.orderNo)}
      />
    )
  },
  {
    key: 'index',
    title: $t('common.index'),
    width: 64,
    align: 'center',
    render: (_, index) => (pagination.page - 1) * pagination.pageSize + index + 1
  },
  {
    key: 'partNo',
    title: $t('page.labor_management.labor_project.partNo'),
    align: 'center',
    minWidth: 120,
    render: row => row.order.partNo
  },
  {
    key: 'orderNo',
    title: $t('page.order_management.order.orderNo'),
    align: 'center',
    minWidth: 170,
    render: row => (
      <div class="flex-center gap-4px">
        <span class="font-medium">{row.order.orderNo}</span>
        <NButton
          quaternary
          size="tiny"
          aria-label={$t('page.labor_management.labor_project.copy')}
          onClick={(event: MouseEvent) => {
            event.stopPropagation();
            void copyOrderNo(row.order.orderNo);
          }}
        >
          <icon-ic-round-content-copy class="text-14px" />
        </NButton>
      </div>
    )
  },
  {
    key: 'name',
    title: $t('page.order_management.order.name'),
    align: 'center',
    minWidth: 160,
    render: row => row.order.name || '—'
  },
  {
    key: 'quantity',
    title: `${$t('page.order_management.order.receivedQuantity')} / ${$t('page.order_management.order.quantity')}`,
    align: 'center',
    minWidth: 150,
    render: row =>
      `${row.order.receivedQuantity ?? '—'} / ${row.order.quantity ?? '—'}${row.order.unit ? ` ${row.order.unit}` : ''}`
  },
  {
    key: 'orderDueDate',
    title: $t('page.order_management.order.orderDueDate'),
    align: 'center',
    minWidth: 120,
    render: row => row.order.orderDueDate ?? '—'
  },
  {
    key: 'ticketStatus',
    title: $t('page.labor_management.labor_project.ticketStatus'),
    align: 'center',
    minWidth: 120,
    render: row => {
      if (row.noPainting) return <NTag size="small">{$t('page.labor_management.labor_project.noPaintingOrder')}</NTag>;
      if (!row.tickets.length) {
        return <NTag size="small" type="warning">{$t('page.labor_management.labor_project.statusToGenerate')}</NTag>;
      }
      if (row.unassignedTickets.length) {
        return (
          <NTag size="small" type="warning">
            {$t('page.labor_management.labor_project.statusUnassigned', { count: row.unassignedTickets.length })}
          </NTag>
        );
      }
      return <NTag size="small" type="success">{$t('page.labor_management.labor_project.statusDone')}</NTag>;
    }
  },
  {
    key: 'monthHours',
    title: $t('page.labor_management.labor_project.monthHours'),
    align: 'center',
    minWidth: 110,
    render: row => (row.monthHours ? formatHours(row.monthHours) : '—')
  },
  {
    key: 'operate',
    title: $t('common.operate'),
    align: 'center',
    width: 120,
    render: row => (
      <NButton size="small" ghost type={row.pending ? 'primary' : 'default'} onClick={() => toggleRow(row)}>
        {!row.noPainting && !row.tickets.length
          ? $t('page.labor_management.labor_project.generateTickets')
          : row.unassignedTickets.length
            ? $t('page.labor_management.labor_project.assignTickets')
            : $t('page.labor_management.labor_project.viewTickets')}
      </NButton>
    )
  }
  ];
});

onMounted(() => {
  void loadWorkers();
  void loadAll(importMonth.value);
});
</script>

<template>
  <div class="h-full flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <NCard :bordered="false" size="small" class="card-wrapper">
      <NSpace vertical :size="12">
        <NSpace align="center" wrap justify="space-between">
          <NSpace align="center" wrap :size="8">
            <span class="text-13px text-gray-500">{{ $t('page.labor_management.labor_project.importMonth') }}</span>
            <NDatePicker
              v-model:formatted-value="importMonth"
              type="month"
              value-format="yyyy-MM-dd"
              clearable
              class="w-130px"
              :placeholder="$t('page.labor_management.labor_project.allMonths')"
            />
            <span class="text-13px text-gray-500">{{ $t('page.labor_management.labor_project.statsMonth') }}</span>
            <NDatePicker
              v-model:formatted-value="statsMonthModel"
              type="month"
              value-format="yyyy-MM-dd"
              :clearable="false"
              class="w-130px"
            />
            <NInput
              v-model:value="keyword"
              clearable
              class="w-220px"
              :placeholder="$t('page.labor_management.labor_project.searchOrders')"
            >
              <template #prefix>
                <icon-ic-round-search class="text-icon" />
              </template>
            </NInput>
            <span class="text-13px text-gray-500">{{ $t('page.labor_management.common.status') }}</span>
            <NSelect v-model:value="statusValue" :options="statusOptions" class="w-110px" />
          </NSpace>
          <NSpace align="center" :size="8">
            <NButton size="small" :loading="loading" @click="refresh">
              <template #icon>
                <icon-ic-round-refresh class="text-icon" />
              </template>
              {{ $t('common.refresh') }}
            </NButton>
            <NButton size="small" ghost type="primary" @click="emit('manageProjects')">
              {{ $t('page.labor_management.labor_project.viewProjectManage') }}
            </NButton>
          </NSpace>
        </NSpace>

        <NGrid responsive="screen" item-responsive :x-gap="12" :y-gap="12">
          <NGridItem span="12 s:6">
            <NStatistic :label="$t('page.labor_management.labor_project.pendingOrders')" :value="stats.pendingOrders" />
          </NGridItem>
          <NGridItem span="12 s:6">
            <NStatistic
              :label="$t('page.labor_management.labor_project.unassignedTickets')"
              :value="stats.unassignedTickets"
            />
          </NGridItem>
          <NGridItem span="12 s:6">
            <NStatistic
              :label="$t('page.labor_management.labor_project.monthHours')"
              :value="stats.monthHours"
              :precision="2"
              :suffix="$t('page.labor_management.labor_project.hoursUnit')"
            />
          </NGridItem>
          <NGridItem span="12 s:6">
            <NStatistic
              :label="$t('page.labor_management.labor_project.completedOrders')"
              :value="stats.completedOrders"
            />
          </NGridItem>
        </NGrid>

        <NAlert v-if="workersFailed" type="warning" :show-icon="true">
          {{ $t('page.labor_management.labor_project.workersLoadFailed') }}
          <NButton text type="primary" class="ml-8px" :loading="workersLoading" @click="loadWorkers">
            {{ $t('page.labor_management.labor_project.retryOrders') }}
          </NButton>
        </NAlert>
        <NAlert v-if="unmatchedProjects.length" type="warning" :show-icon="true">
          {{ $t('page.labor_management.labor_project.unmatchedProjectsHint', { count: unmatchedProjects.length }) }}
        </NAlert>
        <NAlert v-if="failed" type="error" :show-icon="true">
          {{ $t('page.labor_management.labor_project.workbenchLoadFailed') }}
          <NButton text type="primary" class="ml-8px" @click="refresh">
            {{ $t('page.labor_management.labor_project.retryOrders') }}
          </NButton>
        </NAlert>
      </NSpace>
    </NCard>

    <NCard
      :title="$t('page.labor_management.labor_project.orderList')"
      :bordered="false"
      size="small"
      class="card-wrapper sm:flex-1-hidden"
    >
      <template #header-extra>
        <span class="text-12px text-gray-400">
          {{ $t('page.labor_management.labor_project.filteredCount', { count: filteredRows.length }) }}
        </span>
      </template>
      <NDataTable
        v-model:expanded-row-keys="expandedRowKeys"
        :columns="columns"
        :data="filteredRows"
        :loading="loading"
        :pagination="pagination"
        :row-key="row => row.id"
        :scroll-x="1200"
        :flex-height="!appStore.isMobile"
        class="labor-workbench-table sm:h-full"
        size="small"
      >
        <template #empty>
          <NEmpty :description="emptyDescription" />
        </template>
      </NDataTable>
    </NCard>
  </div>
</template>

<style scoped>
.labor-workbench-table :deep(.n-data-table-tr--expanded > .n-data-table-td[colspan]) {
  --detail-background: color-mix(in srgb, var(--n-merged-td-color) 96%, var(--n-td-text-color));
  --n-merged-td-color-hover: var(--detail-background);
  padding: 0;
  background-color: var(--detail-background);
}

.labor-workbench-table :deep(.n-data-table-expand-trigger--expanded) {
  color: rgb(var(--primary-color));
}
</style>
