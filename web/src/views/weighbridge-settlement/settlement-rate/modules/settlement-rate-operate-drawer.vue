<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { jsonClone } from '@sa/utils';
import { fetchAddSettlementRate, fetchUpdateSettlementRate } from '@/service/api';
import { useFormRules, useNaiveForm } from '@/hooks/common/form';
import { $t } from '@/locales';

defineOptions({ name: 'SettlementRateOperateDrawer' });

interface Props {
  operateType: NaiveUI.TableOperateType;
  rowData?: Api.WeighbridgeSettlementManage.SettlementRate | null;
}

const props = defineProps<Props>();

interface Emits {
  (e: 'submitted'): void;
}

const emit = defineEmits<Emits>();
const visible = defineModel<boolean>('visible', { default: false });
const { formRef, validate, restoreValidation } = useNaiveForm();
const { defaultRequiredRule } = useFormRules();

const title = computed(() => {
  const titles: Record<NaiveUI.TableOperateType, string> = {
    add: $t('page.weighbridge_settlement.settlement_rate.addSettlementRate'),
    edit: $t('page.weighbridge_settlement.settlement_rate.editSettlementRate')
  };
  return titles[props.operateType];
});

const model = ref(createDefaultModel());

function createDefaultModel(): Api.WeighbridgeSettlementManage.SettlementRateAddParams {
  return {
    processName: '',
    price: null,
    enabled: true
  } as unknown as Api.WeighbridgeSettlementManage.SettlementRateAddParams;
}

const rules: Record<string, App.Global.FormRule> = {
  processName: defaultRequiredRule,
  price: defaultRequiredRule
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
    const { error } = await fetchAddSettlementRate(model.value);
    if (error) return;
    window.$message?.success($t('common.addSuccess'));
  } else {
    const { error } = await fetchUpdateSettlementRate({ id: props.rowData?.id, ...model.value });
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
        <NFormItem :label="$t('page.weighbridge_settlement.settlement_rate.processName')" path="processName">
          <NInput
            v-model:value="model.processName"
            :placeholder="$t('page.weighbridge_settlement.settlement_rate.form.processName')"
          />
        </NFormItem>
        <NFormItem :label="$t('page.weighbridge_settlement.settlement_rate.price')" path="price">
          <NInputNumber
            v-model:value="model.price"
            :precision="4"
            :min="0.0001"
            :placeholder="$t('page.weighbridge_settlement.settlement_rate.form.price')"
            class="w-full"
          />
        </NFormItem>
        <NFormItem :label="$t('page.weighbridge_settlement.settlement_rate.enabled')" path="enabled">
          <NSwitch :value="Boolean(model.enabled)" @update:value="value => (model.enabled = value)" />
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
