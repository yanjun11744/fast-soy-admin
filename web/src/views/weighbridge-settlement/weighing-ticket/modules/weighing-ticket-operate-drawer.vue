<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { jsonClone } from '@sa/utils';
import { fetchAddWeighingTicket, fetchUpdateWeighingTicket } from '@/service/api';
import { useFormRules, useNaiveForm } from '@/hooks/common/form';
import { $t } from '@/locales';


defineOptions({ name: 'WeighingTicketOperateDrawer' });

type SelectOptionItem = { label: string; value: string | number };

interface Props {
  operateType: NaiveUI.TableOperateType;
  rowData?: Api.WeighbridgeSettlementManage.WeighingTicket | null;
  rateOptions?: SelectOptionItem[];
}

const props = withDefaults(defineProps<Props>(), {
  rateOptions: () => [],
});

interface Emits {
  (e: 'submitted'): void;
}

const emit = defineEmits<Emits>();
const visible = defineModel<boolean>('visible', { default: false });
const { formRef, validate, restoreValidation } = useNaiveForm();
const { defaultRequiredRule } = useFormRules();

const title = computed(() => {
  const titles: Record<NaiveUI.TableOperateType, string> = {
    add: $t('page.weighbridge_settlement.weighing_ticket.addWeighingTicket'),
    edit: $t('page.weighbridge_settlement.weighing_ticket.editWeighingTicket')
  };
  return titles[props.operateType];
});

const model = ref(createDefaultModel());

function createDefaultModel(): Api.WeighbridgeSettlementManage.WeighingTicketAddParams {
  return {
    ticketNo: '',
    weighingDate: null,
    weight: null,
    process: '',
    price: null,
    totalAmount: null,
    isSettled: false,
    revision: null,
    rateId: null
  } as unknown as Api.WeighbridgeSettlementManage.WeighingTicketAddParams;
}

const rules: Record<string, App.Global.FormRule> = {
  ticketNo: defaultRequiredRule,
  weighingDate: defaultRequiredRule,
  weight: defaultRequiredRule,
  process: defaultRequiredRule,
  price: defaultRequiredRule,
  totalAmount: defaultRequiredRule,
  rateId: defaultRequiredRule
};


function handleInitModel() {
  model.value = createDefaultModel();
  if (props.operateType === 'edit' && props.rowData) {
    Object.assign(model.value, jsonClone(props.rowData));
  }
}

function closeDrawer() {
  visible.value = false;
}

async function handleSubmit() {
  await validate();
  if (props.operateType === 'add') {
    const { error } = await fetchAddWeighingTicket(model.value);
    if (error) return;
    window.$message?.success($t('common.addSuccess'));
  } else {
    const { error } = await fetchUpdateWeighingTicket({ id: props.rowData?.id, ...model.value });
    if (error) return;
    window.$message?.success($t('common.updateSuccess'));
  }
  closeDrawer();
  emit('submitted');
}

watch(visible, () => {
  if (visible.value) {
    handleInitModel();
    restoreValidation();
  }
});
</script>

<template>
  <NDrawer v-model:show="visible" display-directive="show" :width="420">
    <NDrawerContent :title="title" :native-scrollbar="false" closable>
      <NForm ref="formRef" :model="model" :rules="rules">
        <NFormItem :label="$t('page.weighbridge_settlement.weighing_ticket.ticketNo')" path="ticketNo">
          <NInput v-model:value="model.ticketNo" :placeholder="$t('page.weighbridge_settlement.weighing_ticket.form.ticketNo')" />
        </NFormItem>
        <NFormItem :label="$t('page.weighbridge_settlement.weighing_ticket.weighingDate')" path="weighingDate">
          <NDatePicker
            v-model:formatted-value="model.weighingDate"
            type="date"
            value-format="yyyy-MM-dd"
            clearable
            class="w-full"
          />
        </NFormItem>
        <NFormItem :label="$t('page.weighbridge_settlement.weighing_ticket.weight')" path="weight">
          <NInputNumber v-model:value="model.weight" :precision="2" :placeholder="$t('page.weighbridge_settlement.weighing_ticket.form.weight')" class="w-full" />
        </NFormItem>
        <NFormItem :label="$t('page.weighbridge_settlement.weighing_ticket.process')" path="process">
          <NInput v-model:value="model.process" :placeholder="$t('page.weighbridge_settlement.weighing_ticket.form.process')" />
        </NFormItem>
        <NFormItem :label="$t('page.weighbridge_settlement.weighing_ticket.price')" path="price">
          <NInputNumber v-model:value="model.price" :precision="2" :placeholder="$t('page.weighbridge_settlement.weighing_ticket.form.price')" class="w-full" />
        </NFormItem>
        <NFormItem :label="$t('page.weighbridge_settlement.weighing_ticket.totalAmount')" path="totalAmount">
          <NInputNumber v-model:value="model.totalAmount" :precision="2" :placeholder="$t('page.weighbridge_settlement.weighing_ticket.form.totalAmount')" class="w-full" />
        </NFormItem>
        <NFormItem :label="$t('page.weighbridge_settlement.weighing_ticket.isSettled')" path="isSettled">
          <NSwitch
            :value="Boolean(model.isSettled)"
            @update:value="value => (model.isSettled = value)"
          />
        </NFormItem>
        <NFormItem :label="$t('page.weighbridge_settlement.weighing_ticket.revision')" path="revision">
          <NInputNumber v-model:value="model.revision" :placeholder="$t('page.weighbridge_settlement.weighing_ticket.form.revision')" class="w-full" />
        </NFormItem>
        <NFormItem :label="$t('page.weighbridge_settlement.weighing_ticket.rate')" path="rateId">
          <NSelect
            v-model:value="model.rateId"
            :options="props.rateOptions"
            clearable
            filterable
            :placeholder="$t('page.weighbridge_settlement.weighing_ticket.form.rate')"
          />
        </NFormItem>
      </NForm>
      <template #footer>
        <NSpace :size="16">
          <NButton @click="closeDrawer">{{ $t('common.cancel') }}</NButton>
          <NButton type="primary" @click="handleSubmit">{{ $t('common.confirm') }}</NButton>
        </NSpace>
      </template>
    </NDrawerContent>
  </NDrawer>
</template>
