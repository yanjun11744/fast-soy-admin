import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, h } from 'vue';
import { expect, it, vi } from 'vitest';
import {
  fetchAddLaborWorkHour,
  fetchDeleteLaborWorkHour,
  fetchOcrRecognize,
  fetchUpdateLaborWorkHour
} from '@/service/api';
import AssignmentRow from '../labor-ticket-assignment-row.vue';
import Panel from '../labor-ticket-workbench-panel.vue';

vi.mock('@/locales', () => ({ $t: (key: string) => key }));
vi.mock('@/service/api', () => ({
  fetchAddLaborWorkHour: vi.fn(),
  fetchUpdateLaborWorkHour: vi.fn(),
  fetchDeleteLaborWorkHour: vi.fn(),
  fetchOcrRecognize: vi.fn()
}));

const NInput = defineComponent({
  name: 'NInput',
  props: ['value'],
  emits: ['update:value'],
  setup(props, { emit }) {
    return () =>
      h('input', {
        'data-code': true,
        value: props.value,
        onInput: (event: Event) => emit('update:value', (event.target as HTMLInputElement).value)
      });
  }
});
const NInputNumber = defineComponent({
  name: 'NInputNumber',
  props: ['value'],
  emits: ['update:value'],
  setup(props, { emit }) {
    return () =>
      h('input', {
        'data-hours': true,
        type: 'number',
        value: props.value,
        onInput: (event: Event) => emit('update:value', Number((event.target as HTMLInputElement).value))
      });
  }
});
const NSelect = defineComponent({
  name: 'NSelect',
  props: ['value', 'options'],
  emits: ['update:value'],
  setup: () => () => h('div')
});
const NDatePicker = defineComponent({
  name: 'NDatePicker',
  props: ['formattedValue'],
  emits: ['update:formatted-value'],
  setup: () => () => h('div')
});
const NButton = defineComponent({
  name: 'NButton',
  props: ['disabled'],
  emits: ['click'],
  setup:
    (_, { slots, emit }) =>
    () =>
      h('button', { onClick: () => emit('click') }, slots.default?.())
});
const NEmpty = defineComponent({
  name: 'NEmpty',
  props: ['description'],
  setup: props => () => h('div', { 'data-empty': true }, props.description)
});
const NPopconfirm = defineComponent({
  name: 'NPopconfirm',
  emits: ['positive-click'],
  setup(_, { slots, emit }) {
    return () =>
      h('div', [
        slots.trigger?.(),
        h('button', { 'data-confirm-delete': true, onClick: () => emit('positive-click') })
      ]);
  }
});
const AssignmentRowStub = defineComponent({
  name: 'LaborTicketAssignmentRow',
  props: ['ticket'],
  setup(props) {
    return () => h('div', { 'data-ticket': (props.ticket as Api.LaborManagementManage.LaborWorkHour).id });
  }
});

const stubs = {
  NInput,
  NInputNumber,
  NSelect,
  NDatePicker,
  NButton,
  NEmpty,
  NPopconfirm,
  LaborTicketAssignmentRow: AssignmentRowStub
};

const order = { id: 'o1', orderNo: 'O1', partNo: 'P1', name: 'Part' } as Api.OrderManagementManage.Order;
const tickets = [
  { id: 't1', ticketCode: 'T1', workHours: 2, orderNo: 'O1', workerId: 'w1', allocationMonth: '2026-11-01' },
  { id: 't2', ticketCode: 'T2', workHours: 3, orderNo: 'O1', workerId: null, allocationMonth: null }
] as Api.LaborManagementManage.LaborWorkHour[];
const workerOptions = [{ label: '张三（001）', value: 'w1' }];

function pasteEvent(items: { kind: string; type: string; file?: File }[]): ClipboardEvent {
  const event = new Event('paste', { bubbles: true, cancelable: true }) as ClipboardEvent;
  Object.defineProperty(event, 'clipboardData', {
    value: {
      items: items.map(item => ({
        kind: item.kind,
        type: item.type,
        getAsFile: () => item.file ?? null
      }))
    }
  });
  return event;
}

it('hides assigned tickets and creates a ticket already assigned to the selected worker', async () => {
  vi.mocked(fetchAddLaborWorkHour).mockResolvedValueOnce({ error: null } as never);
  const wrapper = mount(Panel, {
    props: {
      order,
      tickets,
      workerOptions,
      defaultMonth: '2026-11-01',
      canCreate: true,
      canAssign: true,
      canDelete: true
    },
    global: { stubs }
  });

  expect(wrapper.findAll('[data-ticket]').map(node => node.attributes('data-ticket'))).toEqual(['t2']);
  expect(wrapper.text()).toContain('page.labor_management.labor_project.assignedHidden');

  await wrapper.get('[data-code]').setValue('  T9  ');
  await wrapper.get('[data-hours]').setValue('3');
  wrapper.getComponent({ name: 'NSelect' }).vm.$emit('update:value', 'w1');
  await wrapper.vm.$nextTick();
  const createButton = wrapper.findAll('button').find(button => button.text().includes('createAndAssign'));
  expect(createButton).toBeTruthy();
  await createButton!.trigger('click');
  await flushPromises();

  expect(fetchAddLaborWorkHour).toHaveBeenCalledWith({
    ticketCode: 'T9',
    workHours: 3,
    orderNo: 'O1',
    workerId: 'w1',
    allocationMonth: '2026-11-01'
  });
  expect(wrapper.emitted('changed')).toHaveLength(1);
  wrapper.unmount();
  vi.clearAllMocks();
});

it('recognizes a pasted screenshot but leaves text paste untouched', async () => {
  const image = new File(['image'], 'ticket.png', { type: 'image/png' });
  vi.mocked(fetchOcrRecognize).mockResolvedValueOnce({
    data: { items: [{ text: 'PASTE-1' }] },
    error: null
  } as never);
  const wrapper = mount(Panel, {
    props: {
      order,
      tickets,
      workerOptions,
      defaultMonth: '2026-11-01',
      canCreate: true,
      canAssign: true,
      canDelete: true
    },
    global: { stubs }
  });

  const imageEvent = pasteEvent([{ kind: 'file', type: 'image/png', file: image }]);
  wrapper.get('[data-code]').element.dispatchEvent(imageEvent);
  await flushPromises();

  expect(fetchOcrRecognize).toHaveBeenCalledWith(image, { useCls: true });
  expect(imageEvent.defaultPrevented).toBe(true);
  expect((wrapper.get('[data-code]').element as HTMLInputElement).value).toBe('PASTE-1');

  const textEvent = pasteEvent([{ kind: 'string', type: 'text/plain' }]);
  wrapper.get('[data-code]').element.dispatchEvent(textEvent);
  await flushPromises();

  expect(fetchOcrRecognize).toHaveBeenCalledTimes(1);
  expect(textEvent.defaultPrevented).toBe(false);
  wrapper.unmount();
  vi.clearAllMocks();
});

it('assigns an unassigned ticket and deletes it from the same row', async () => {
  vi.mocked(fetchUpdateLaborWorkHour).mockResolvedValueOnce({ error: null } as never);
  vi.mocked(fetchDeleteLaborWorkHour).mockResolvedValueOnce({ error: null } as never);
  const wrapper = mount(AssignmentRow, {
    props: {
      ticket: tickets[1],
      workerOptions,
      defaultMonth: '2026-11-01',
      canAssign: true,
      canDelete: true
    },
    global: { stubs }
  });

  wrapper.getComponent({ name: 'NSelect' }).vm.$emit('update:value', 'w1');
  const assignButton = wrapper.findAll('button').find(button => button.text().includes('assign'));
  await assignButton!.trigger('click');
  await flushPromises();
  expect(fetchUpdateLaborWorkHour).toHaveBeenCalledWith({
    id: 't2',
    workerId: 'w1',
    allocationMonth: '2026-11-01'
  });
  expect(wrapper.emitted('changed')).toHaveLength(1);

  await wrapper.get('[data-confirm-delete]').trigger('click');
  await flushPromises();
  expect(fetchDeleteLaborWorkHour).toHaveBeenCalledWith({ id: 't2' });
  expect(wrapper.emitted('changed')).toHaveLength(2);
  wrapper.unmount();
  vi.clearAllMocks();
});
