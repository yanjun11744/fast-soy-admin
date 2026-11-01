<script setup lang="ts">
import { $t } from '@/locales';
defineProps<{ lines: Api.WeighbridgeSettlementManage.WeighingLine[] }>();
const fields = [
  'partNo',
  'orderNo',
  'name',
  'unitWeight',
  'quantity',
  'theoreticalWeight',
  'allocatedWeight',
  'amount',
  'taxUnitPrice'
] as const;
</script>

<template>
  <div class="overflow-x-auto">
    <NTable size="small" :single-line="false" class="min-w-1100px">
      <thead>
        <tr>
          <th>{{ $t('common.index') }}</th>
          <th v-for="field in fields" :key="field">{{ $t(`page.weighbridge_settlement.settlement.${field}`) }}</th>
          <th>{{ $t('page.weighbridge_settlement.settlement.source') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="line in lines" :key="line.id">
          <td>{{ line.position }}</td>
          <td v-for="field in fields" :key="field">{{ line[field] ?? '—' }}</td>
          <td>
            {{
              line.orderId
                ? $t('page.weighbridge_settlement.settlement.matched')
                : $t('page.weighbridge_settlement.settlement.manual')
            }}
          </td>
        </tr>
      </tbody>
    </NTable>
  </div>
</template>
