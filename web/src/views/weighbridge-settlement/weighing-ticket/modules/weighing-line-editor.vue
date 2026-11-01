<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue';
import { fetchSettlementOrderOptions } from '@/service/api';
import { $t } from '@/locales';

const line = defineModel<Api.WeighbridgeSettlementManage.LineInput>({ required: true });
defineProps<{ readonly?: boolean }>();
const manual = ref(!line.value.orderId && Boolean(line.value.partNo));
const query = ref('');
const options = ref<Api.WeighbridgeSettlementManage.OrderOption[]>([]);
const searching = ref(false);
const selectOptions = computed(() => {
  const result = options.value.map(order => ({
    value: order.id,
    label: `${order.partNo} | ${order.orderNo} | ${order.name} | ${order.unitWeight} kg`
  }));
  if (line.value.orderId && !result.some(option => option.value === line.value.orderId)) {
    result.push({
      value: line.value.orderId,
      label: `${line.value.partNo} | ${line.value.orderNo ?? ''} | ${line.value.name} | ${line.value.unitWeight} kg`
    });
  }
  return result;
});
let timer: ReturnType<typeof setTimeout> | undefined;
let sequence = 0;
function search(value: string) {
  query.value = value.trim();
  clearTimeout(timer);
  const current = ++sequence;
  if (!value.trim()) {
    options.value = [];
    searching.value = false;
    return;
  }
  searching.value = true;
  timer = setTimeout(async () => {
    const { data, error } = await fetchSettlementOrderOptions(value.trim());
    if (current !== sequence) return;
    searching.value = false;
    options.value = error ? [] : (data ?? []);
  }, 300);
}
function choose(id: string) {
  const order = options.value.find(item => item.id === id);
  if (order)
    Object.assign(line.value, {
      orderId: order.id,
      partNo: order.partNo,
      orderNo: order.orderNo,
      name: order.name,
      unitWeight: order.unitWeight
    });
}
function setManual(value: boolean) {
  manual.value = value;
  if (value) {
    line.value.orderId = null;
    if (!line.value.partNo) line.value.partNo = query.value;
    clearTimeout(timer);
    sequence++;
    searching.value = false;
  }
}
onBeforeUnmount(() => {
  clearTimeout(timer);
  sequence++;
});
</script>

<template>
  <div class="min-w-260px flex-col gap-8px">
    <NSpace v-if="!readonly">
      <NButton :type="!manual ? 'primary' : 'default'" size="small" @click="setManual(false)">
        {{ $t('page.weighbridge_settlement.settlement.matched') }}
      </NButton>
      <NButton :type="manual ? 'primary' : 'default'" size="small" @click="setManual(true)">
        {{ $t('page.weighbridge_settlement.settlement.manual') }}
      </NButton>
    </NSpace>
    <NSelect
      v-if="!manual && !readonly"
      :value="line.orderId"
      remote
      filterable
      :loading="searching"
      :options="selectOptions"
      :placeholder="$t('page.weighbridge_settlement.settlement.searchOrders')"
      @search="search"
      @update:value="choose"
    >
      <template #empty>{{ $t('page.weighbridge_settlement.settlement.noOrders') }}</template>
    </NSelect>
    <div class="grid grid-cols-2 gap-8px">
      <NInput
        v-model:value="line.partNo"
        :disabled="readonly || !manual"
        :placeholder="$t('page.weighbridge_settlement.settlement.partNo')"
        :aria-label="$t('page.weighbridge_settlement.settlement.partNo')"
      />
      <NInput
        v-model:value="line.orderNo"
        :disabled="readonly || !manual"
        :placeholder="$t('page.weighbridge_settlement.settlement.orderNo')"
        :aria-label="$t('page.weighbridge_settlement.settlement.orderNo')"
      />
      <NInput
        v-model:value="line.name"
        :disabled="readonly || !manual"
        :placeholder="$t('page.weighbridge_settlement.settlement.name')"
        :aria-label="$t('page.weighbridge_settlement.settlement.name')"
      />
      <NInput
        v-model:value="line.unitWeight"
        :disabled="readonly || !manual"
        :placeholder="$t('page.weighbridge_settlement.settlement.unitWeight')"
        :aria-label="$t('page.weighbridge_settlement.settlement.unitWeight')"
      />
    </div>
    <NFormItem :label="$t('page.weighbridge_settlement.settlement.quantity')" :show-feedback="false">
      <NInputNumber
        :value="line.quantity"
        :min="1"
        :max="2147483647"
        :precision="0"
        :disabled="readonly"
        class="w-full"
        @update:value="value => (line.quantity = value ?? 0)"
      />
    </NFormItem>
  </div>
</template>
