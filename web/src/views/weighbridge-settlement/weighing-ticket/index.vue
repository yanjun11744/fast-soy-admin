<script setup lang="tsx">
import { onMounted, reactive, ref } from 'vue';
import { NButton, NPopconfirm } from 'naive-ui';
import ImagePreview from '@/components/advanced/image-preview.vue';
import {
  fetchBatchDeleteWeighingTicket, fetchDeleteWeighingTicket, fetchGetWeighingTicketList,
  fetchExportWeighingTicket, fetchSettlementRateOptions, fetchSettleWeighingTicket
} from '@/service/api';
import { useAppStore } from '@/store/modules/app';
import { defaultTransform, useNaivePaginatedTable, useTableOperate } from '@/hooks/common/table';

import { $t } from '@/locales';
import { downloadExcel } from '@/utils/excel';
import WeighingTicketOperateDrawer from './modules/weighing-ticket-operate-drawer.vue';
import WeighingTicketSearch from './modules/weighing-ticket-search.vue';

const appStore = useAppStore();


type SelectOptionItem = { label: string; value: string | number };

const rateOptions = ref<SelectOptionItem[]>([]);

const detailMode = ref(false);
onMounted(async () => {
  const { data: options } = await fetchSettlementRateOptions();
  rateOptions.value = (options ?? []).map(rate => ({ label: rate.processName, value: rate.id }));
});
const defaultSearchParams: Api.WeighbridgeSettlementManage.WeighingTicketSearchParams = {
  current: 1,
  size: 10,
  weighingDateStart: null,
  weighingDateEnd: null,
  ticketNo: null,
  process: null,
  isSettled: null,
  rateId: null,
};

const searchParams: Api.WeighbridgeSettlementManage.WeighingTicketSearchParams = reactive({ ...defaultSearchParams });

const { columns, columnChecks, data, loading, getData, getDataByPage, mobilePagination } = useNaivePaginatedTable({
  api: () => fetchGetWeighingTicketList(searchParams),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.current = params.page;
    searchParams.size = params.pageSize;
  },
  columns: () => [
    { type: 'selection', align: 'center', width: 48 },
    { key: 'index', title: $t('common.index'), width: 64, align: 'center', render: (_, index) => index + 1 },
    { key: 'ticketNo', title: $t('page.weighbridge_settlement.weighing_ticket.ticketNo'), align: 'center', minWidth: 120 },
    { key: 'images', title: $t('page.weighbridge_settlement.weighing_ticket.images'), align: 'center', minWidth: 160, render: row => <ImagePreview value={row.images} width={48} height={48} /> },
    { key: 'weighingDate', title: $t('page.weighbridge_settlement.weighing_ticket.weighingDate'), align: 'center', minWidth: 120 },
    { key: 'weight', title: $t('page.weighbridge_settlement.weighing_ticket.weight'), align: 'center', minWidth: 120 },
    { key: 'process', title: $t('page.weighbridge_settlement.weighing_ticket.process'), align: 'center', minWidth: 120 },
    { key: 'price', title: $t('page.weighbridge_settlement.weighing_ticket.price'), align: 'center', minWidth: 120 },
    { key: 'totalAmount', title: $t('page.weighbridge_settlement.weighing_ticket.totalAmount'), align: 'center', minWidth: 120 },
    { key: 'isSettled', title: $t('page.weighbridge_settlement.weighing_ticket.isSettled'), align: 'center', minWidth: 100, render: row => row.isSettled ? $t('page.weighbridge_settlement.settlement.settled') : $t('page.weighbridge_settlement.settlement.unsettled') },
    {
      key: 'operate',
      title: $t('common.operate'),
      align: 'center',
      width: 340,
      render: row => (
        <div class="flex-center gap-8px">
          <NButton size="small" onClick={() => showDetail(row.id)}>{$t('page.weighbridge_settlement.settlement.details')}</NButton>
          {!row.isSettled && <NPopconfirm onPositiveClick={() => settle(row)}>{{ default: () => $t('page.weighbridge_settlement.settlement.settleConfirm'), trigger: () => <NButton size="small" type="success">{$t('page.weighbridge_settlement.settlement.settle')}</NButton> }}</NPopconfirm>}
          <NButton disabled={Boolean(row.isSettled)} type="primary" ghost size="small" onClick={() => edit(row.id)}>
              {$t('common.edit')}
            </NButton>
          <NPopconfirm onPositiveClick={() => handleDelete(row.id)}>
              {{
                default: () => $t('common.confirmDelete'),
                trigger: () => (
                  <NButton disabled={Boolean(row.isSettled)} type="error" ghost size="small">
                    {$t('common.delete')}
                  </NButton>
                )
              }}
            </NPopconfirm>
        </div>
      )
    }
  ]
});

const { drawerVisible, operateType, editingData, handleAdd, handleEdit, checkedRowKeys, onBatchDeleted, onDeleted } =
  useTableOperate(data, 'id', getData);

async function settle(row: Api.WeighbridgeSettlementManage.WeighingTicket) {
  const { error } = await fetchSettleWeighingTicket(row.id, row.revision ?? 1);
  if (!error) getData();
}
function showDetail(id: string) {
  detailMode.value = true;
  handleEdit(id);
}
function add() {
  detailMode.value = false;
  handleAdd();
}


const exporting = ref(false);
async function exportTickets(selected = false) {
  if (exporting.value || (selected && !checkedRowKeys.value.length)) return;
  exporting.value = true;
  try {
    const { data: file, error } = await fetchExportWeighingTicket({ ...searchParams, ...(selected ? { ids: checkedRowKeys.value as string[] } : {}) });
    if (!error && file) downloadExcel(file);
  } finally { exporting.value = false; }
}

async function handleBatchDelete() {
  const { error } = await fetchBatchDeleteWeighingTicket({ ids: checkedRowKeys.value as string[] });
  if (!error) onBatchDeleted();
}

async function handleDelete(id: string) {
  const { error } = await fetchDeleteWeighingTicket({ id });
  if (!error) onDeleted();
}

function resetSearchParams() {
  Object.assign(searchParams, {
    ...defaultSearchParams
  });
  getDataByPage(1);
}

function edit(id: string) {
  detailMode.value = false;
  handleEdit(id);
}
</script>

<template>
  <div class="min-h-500px flex-col-stretch gap-16px overflow-hidden lt-sm:overflow-auto">
    <WeighingTicketSearch
      v-model:model="searchParams"
      :rate-options="rateOptions"
      @reset="resetSearchParams"
      @search="getDataByPage"
    />
    <NCard
      :title="$t('page.weighbridge_settlement.weighing_ticket.pageTitle')"
      :bordered="false"
      size="small"
      class="card-wrapper sm:flex-1-hidden"
    >
      <template #header-extra>
        <NSpace align="center" wrap>
          <NButton size="small" :loading="exporting" @click="exportTickets()">
            {{ $t('common.excelExportFiltered') }}
          </NButton>
          <NButton size="small" :disabled="!checkedRowKeys.length || exporting" @click="exportTickets(true)">
            {{ $t('common.excelExportSelected', { count: checkedRowKeys.length }) }}
          </NButton>
          <TableHeaderOperation
            v-model:columns="columnChecks"
            :disabled-delete="checkedRowKeys.length === 0"
            :loading="loading"
            @add="add"
            @delete="handleBatchDelete"
            @refresh="getData"
          />
        </NSpace>
      </template>
      <NDataTable
        v-model:checked-row-keys="checkedRowKeys"
        :columns="columns"
        :data="data"
        size="small"
        :flex-height="!appStore.isMobile"
        :scroll-x="1400"
        :loading="loading"
        remote
        :row-key="row => row.id"
        :pagination="mobilePagination"
        class="sm:h-full"
      />
      <WeighingTicketOperateDrawer
        v-model:visible="drawerVisible"
        :operate-type="operateType"
        :row-data="editingData"
        :readonly="detailMode"
        @submitted="getDataByPage"
      />
    </NCard>
  </div>
</template>
