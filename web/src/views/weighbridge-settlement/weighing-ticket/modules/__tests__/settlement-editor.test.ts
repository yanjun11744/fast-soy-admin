import { defineComponent } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  fetchGetWeighingTicket,
  fetchSettlementOrderOptions,
  fetchSettlementPreview,
  fetchSettlementRateOptions,
  fetchUpdateWeighingTicket
} from '@/service/api';
import Drawer from '../weighing-ticket-operate-drawer.vue';
import LineEditor from '../weighing-line-editor.vue';

vi.mock('@/locales', () => ({ $t: (key: string) => key }));
vi.mock('@/service/api', () => ({
  fetchAddWeighingTicket: vi.fn(),
  fetchGetWeighingTicket: vi.fn(),
  fetchSettlementPreview: vi.fn(),
  fetchSettlementRateOptions: vi.fn(),
  fetchUpdateWeighingTicket: vi.fn(),
  fetchSettlementOrderOptions: vi.fn()
}));
const container = defineComponent({
  template: '<div><slot /><slot name="footer" /><slot name="header-extra" /></div>'
});
const button = defineComponent({
  props: ['disabled'],
  emits: ['click'],
  template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>'
});
const select = defineComponent({
  props: ['value', 'options'],
  emits: ['search', 'update:value'],
  template: '<div><slot /></div>'
});
const input = defineComponent({
  props: ['value', 'disabled'],
  emits: ['update:value'],
  template: '<input :value="value" :disabled="disabled" @input="$emit(\'update:value\', $event.target.value)" />'
});
const stubs = {
  NDrawer: container,
  NDrawerContent: container,
  NSpin: container,
  NAlert: container,
  NForm: container,
  NFormItem: container,
  NInput: input,
  NDatePicker: container,
  NSelect: select,
  NSpace: container,
  NText: container,
  NButton: button,
  NDivider: container,
  NCard: container,
  NDescriptions: container,
  NDescriptionsItem: container,
  NInputNumber: input,
  WeighingLineTable: true
};
const line = {
  id: 'line-id',
  orderId: null,
  orderNo: '',
  partNo: 'MANUAL',
  name: 'Manual item',
  unitWeight: '1.000001',
  quantity: 3,
  position: 1,
  theoreticalWeight: '3.000003',
  allocatedWeight: '10.001',
  amount: '25.00',
  taxUnitPrice: '8.333333'
};
const ticket = {
  id: 'ticket-id',
  ticketNo: 'T1',
  weighingDate: '2026-11-01',
  weight: '10.001',
  rateId: 'rate-id',
  process: 'Old process',
  price: '2.5000',
  totalAmount: '25.00',
  revision: 4,
  isSettled: false,
  lines: [line]
};

function prepare() {
  vi.mocked(fetchGetWeighingTicket).mockResolvedValue({ data: structuredClone(ticket), error: null } as never);
  vi.mocked(fetchSettlementRateOptions).mockResolvedValue({
    data: [{ id: 'rate-id', processName: 'Current process', price: '9.9999' }],
    error: null
  } as never);
  vi.mocked(fetchSettlementPreview).mockResolvedValue({
    data: { totalAmount: '25.00', lines: [line] },
    error: null
  } as never);
  vi.mocked(fetchUpdateWeighingTicket).mockResolvedValue({ data: ticket, error: null } as never);
}
afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe('Ticket aggregate editor', () => {
  it('loads stored lines and preserves the price until explicitly reselected', async () => {
    prepare();
    const wrapper = mount(Drawer, {
      props: {
        operateType: 'edit',
        rowData: ticket as unknown as Api.WeighbridgeSettlementManage.WeighingTicket,
        visible: false
      },
      global: { stubs }
    });
    await wrapper.setProps({ visible: true });
    await flushPromises();
    expect(fetchGetWeighingTicket).toHaveBeenCalledWith('ticket-id');
    expect(wrapper.text()).toContain('2.5000');
    expect(wrapper.findComponent(LineEditor).props('modelValue').partNo).toBe('MANUAL');
    await wrapper
      .findAll('button')
      .find(node => node.text() === 'common.confirm')!
      .trigger('click');
    await flushPromises();
    expect(fetchUpdateWeighingTicket).toHaveBeenLastCalledWith(
      expect.objectContaining({
        revision: 4,
        rateId: undefined,
        lines: [expect.objectContaining({ id: 'line-id', quantity: 3 })]
      })
    );
    expect(wrapper.emitted('submitted')).toHaveLength(1);
    wrapper.unmount();
  });

  it('uses the new rate only after explicit selection and makes settled details read-only', async () => {
    prepare();
    const wrapper = mount(Drawer, {
      props: {
        operateType: 'edit',
        rowData: ticket as unknown as Api.WeighbridgeSettlementManage.WeighingTicket,
        visible: false
      },
      global: { stubs }
    });
    await wrapper.setProps({ visible: true });
    await flushPromises();
    wrapper.findComponent(select).vm.$emit('update:value', 'rate-id');
    await flushPromises();
    expect(wrapper.text()).toContain('9.9999');
    await wrapper
      .findAll('button')
      .find(node => node.text() === 'common.confirm')!
      .trigger('click');
    await flushPromises();
    expect(fetchUpdateWeighingTicket).toHaveBeenLastCalledWith(expect.objectContaining({ rateId: 'rate-id' }));
    wrapper.unmount();
    vi.mocked(fetchGetWeighingTicket).mockResolvedValue({ data: { ...ticket, isSettled: true }, error: null } as never);
    const readonly = mount(Drawer, {
      props: {
        operateType: 'edit',
        rowData: ticket as unknown as Api.WeighbridgeSettlementManage.WeighingTicket,
        visible: false
      },
      global: { stubs }
    });
    await readonly.setProps({ visible: true });
    await flushPromises();
    expect(readonly.findAll('button').some(node => node.text() === 'common.confirm')).toBe(false);
    expect(readonly.findComponent(LineEditor).exists()).toBe(false);
    readonly.unmount();
  });

  it('debounces duplicate part numbers and requires choosing a concrete order without copying order quantity', async () => {
    vi.useFakeTimers();
    const current = { orderId: null, orderNo: '', partNo: '', name: '', unitWeight: '', quantity: 0 };
    vi.mocked(fetchSettlementOrderOptions).mockResolvedValue({
      data: [
        { id: 'one', orderNo: 'O1', partNo: 'P', name: 'First', unitWeight: '1.000001' },
        { id: 'two', orderNo: 'O2', partNo: 'P', name: 'Second', unitWeight: '2.000002' }
      ],
      error: null
    } as never);
    const wrapper = mount(LineEditor, { props: { modelValue: current }, global: { stubs } });
    await wrapper.findAll('button')[0].trigger('click');
    wrapper.findComponent(select).vm.$emit('search', 'P');
    wrapper.findComponent(select).vm.$emit('search', 'P');
    await vi.advanceTimersByTimeAsync(300);
    expect(fetchSettlementOrderOptions).toHaveBeenCalledTimes(1);
    expect(current.orderId).toBeNull();
    wrapper.findComponent(select).vm.$emit('update:value', 'two');
    await flushPromises();
    expect(current).toMatchObject({
      orderId: 'two',
      orderNo: 'O2',
      name: 'Second',
      unitWeight: '2.000002',
      quantity: 0
    });
    await wrapper.findAll('button')[1].trigger('click');
    expect(current.orderId).toBeNull();
    wrapper.unmount();
  });
});
