<script setup lang="tsx">
import { reactive, ref } from 'vue';
import { NButton, NPopconfirm } from 'naive-ui';
import ExcelTransfer from '@/components/advanced/excel-transfer.vue';
import {
  fetchBatchDeleteWeighingTicket, fetchDeleteWeighingTicket, fetchGetWeighingTicketList,
  fetchExportWeighingTicket, fetchImportWeighingTicket, fetchPreviewImportWeighingTicket, fetchWeighingTicketImportTemplate
} from '@/service/api';
import { useAppStore } from '@/store/modules/app';
import { defaultTransform, useNaivePaginatedTable, useTableOperate } from '@/hooks/common/table';

import { $t } from '@/locales';
import WeighingTicketOperateDrawer from './modules/weighing-ticket-operate-drawer.vue';
import WeighingTicketSearch from './modules/weighing-ticket-search.vue';

const appStore = useAppStore();


type SelectOptionItem = { label: string; value: string | number };

const rateOptions = ref<SelectOptionItem[]>([]);

// TODO: 在这里加载真实 options 数据源，并传给搜索区和抽屉。


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
    { key: 'weighingDate', title: $t('page.weighbridge_settlement.weighing_ticket.weighingDate'), align: 'center', minWidth: 120 },
    { key: 'weight', title: $t('page.weighbridge_settlement.weighing_ticket.weight'), align: 'center', minWidth: 120 },
    { key: 'process', title: $t('page.weighbridge_settlement.weighing_ticket.process'), align: 'center', minWidth: 120 },
    { key: 'price', title: $t('page.weighbridge_settlement.weighing_ticket.price'), align: 'center', minWidth: 120 },
    { key: 'totalAmount', title: $t('page.weighbridge_settlement.weighing_ticket.totalAmount'), align: 'center', minWidth: 120 },
    { key: 'rateId', title: $t('page.weighbridge_settlement.weighing_ticket.rate'), align: 'center', minWidth: 120 },
    {
      key: 'operate',
      title: $t('common.operate'),
      align: 'center',
      width: 130,
      render: row => (
        <div class="flex-center gap-8px">
          <NButton type="primary" ghost size="small" onClick={() => edit(row.id)}>
              {$t('common.edit')}
            </NButton>
          <NPopconfirm onPositiveClick={() => handleDelete(row.id)}>
              {{
                default: () => $t('common.confirmDelete'),
                trigger: () => (
                  <NButton type="error" ghost size="small">
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
    <NCard :title="$t('page.weighbridge_settlement.weighing_ticket.pageTitle')" :bordered="false" size="small" class="card-wrapper sm:flex-1-hidden">
      <template #header-extra>
        <NSpace align="center" wrap>
          <ExcelTransfer
            :import-api="fetchImportWeighingTicket"
            :preview-api="fetchPreviewImportWeighingTicket"
            :export-api="() => fetchExportWeighingTicket(searchParams)"
            :export-selected-api="ids => fetchExportWeighingTicket({ ...searchParams, ids })"
            :selected-ids="checkedRowKeys"
            :template-api="fetchWeighingTicketImportTemplate"
            
            @imported="getDataByPage(1)"
          />
          <TableHeaderOperation
            v-model:columns="columnChecks"
            :disabled-delete="checkedRowKeys.length === 0"
            :loading="loading"
            @add="handleAdd"
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
        :scroll-x="600"
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
        :rate-options="rateOptions"
        @submitted="getDataByPage"
      />
    </NCard>
  </div>
</template>
