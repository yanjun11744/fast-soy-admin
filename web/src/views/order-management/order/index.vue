<script setup lang="tsx">
import { reactive } from 'vue';
import { NButton, NPopconfirm } from 'naive-ui';
import ExcelTransfer from '@/components/advanced/excel-transfer.vue';
import {
  fetchBatchDeleteOrder, fetchDeleteOrder, fetchGetOrderList,
  fetchExportOrder, fetchImportOrder, fetchPreviewImportOrder, fetchOrderImportTemplate
} from '@/service/api';
import { useAppStore } from '@/store/modules/app';
import { defaultTransform, useNaivePaginatedTable, useTableOperate } from '@/hooks/common/table';

import { $t } from '@/locales';
import OrderOperateDrawer from './modules/order-operate-drawer.vue';
import OrderSearch from './modules/order-search.vue';

const appStore = useAppStore();




const defaultSearchParams: Api.OrderManagementManage.OrderSearchParams = {
  current: 1,
  size: 10,
  orderNo: null,
  partNo: null,
  name: null,
  unit: null,
  orderDueDateStart: null,
  orderDueDateEnd: null,
  completedDateStart: null,
  completedDateEnd: null,
};

const searchParams: Api.OrderManagementManage.OrderSearchParams = reactive({ ...defaultSearchParams });

const { columns, columnChecks, data, loading, getData, getDataByPage, mobilePagination } = useNaivePaginatedTable({
  api: () => fetchGetOrderList(searchParams),
  transform: response => defaultTransform(response),
  onPaginationParamsChange: params => {
    searchParams.current = params.page;
    searchParams.size = params.pageSize;
  },
  columns: () => [
    { type: 'selection', align: 'center', width: 48 },
    { key: 'index', title: $t('common.index'), width: 64, align: 'center', render: (_, index) => index + 1 },
    { key: 'orderNo', title: $t('page.order_management.order.orderNo'), align: 'center', minWidth: 120 },
    { key: 'partNo', title: $t('page.order_management.order.partNo'), align: 'center', minWidth: 120 },
    { key: 'name', title: $t('page.order_management.order.name'), align: 'center', minWidth: 120 },
    { key: 'unitWeight', title: $t('page.order_management.order.unitWeight'), align: 'center', minWidth: 120 },
    { key: 'unit', title: $t('page.order_management.order.unit'), align: 'center', minWidth: 120 },
    { key: 'quantity', title: $t('page.order_management.order.quantity'), align: 'center', minWidth: 120 },
    { key: 'totalWeight', title: $t('page.order_management.order.totalWeight'), align: 'center', minWidth: 120 },
    { key: 'orderDueDate', title: $t('page.order_management.order.orderDueDate'), align: 'center', minWidth: 120 },
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
  const { error } = await fetchBatchDeleteOrder({ ids: checkedRowKeys.value as string[] });
  if (!error) onBatchDeleted();
}

async function handleDelete(id: string) {
  const { error } = await fetchDeleteOrder({ id });
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
    <OrderSearch
      v-model:model="searchParams"
      @reset="resetSearchParams"
      @search="getDataByPage"
    />
    <NCard :title="$t('page.order_management.order.pageTitle')" :bordered="false" size="small" class="card-wrapper sm:flex-1-hidden">
      <template #header-extra>
        <NSpace align="center" wrap>
          <ExcelTransfer
            :import-api="fetchImportOrder"
            :preview-api="fetchPreviewImportOrder"
            :export-api="() => fetchExportOrder(searchParams)"
            :export-selected-api="ids => fetchExportOrder({ ...searchParams, ids })"
            :selected-ids="checkedRowKeys"
            :template-api="fetchOrderImportTemplate"
            
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
      <OrderOperateDrawer
        v-model:visible="drawerVisible"
        :operate-type="operateType"
        :row-data="editingData"
        @submitted="getDataByPage"
      />
    </NCard>
  </div>
</template>
