import { defineComponent } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import { downloadExcel } from '@/utils/excel';
import ExcelTransfer from '../excel-transfer.vue';

vi.mock('@/locales', () => ({
  $t: (key: string, params?: { count: number }) => `${key}${params ? `:${params.count}` : ''}`
}));
vi.mock('@/utils/excel', () => ({ downloadExcel: vi.fn() }));

const container = defineComponent({ template: '<div><slot /></div>' });
const button = defineComponent({
  props: ['disabled'],
  emits: ['click'],
  template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>'
});
const dropdown = defineComponent({
  name: 'NDropdown',
  props: ['options', 'disabled'],
  emits: ['select'],
  template: `<div><slot /><button v-for="option in options" :key="option.key"
    :disabled="disabled || option.disabled" @click="$emit('select', option.key)">{{ option.label }}</button></div>`
});

function setup(selectedIds: string[] = [], legacy = false) {
  const file = { filename: 'items.xlsx', content: 'test' };
  const exportApi = vi.fn().mockResolvedValue({ data: file, error: null });
  const exportSelectedApi = vi.fn().mockResolvedValue({ data: file, error: null });
  const wrapper = mount(ExcelTransfer, {
    props: {
      importApi: vi.fn(),
      templateApi: vi.fn(),
      exportApi,
      ...(legacy ? {} : { exportSelectedApi }),
      selectedIds,
      canImport: false
    },
    global: { stubs: { NSpace: container, NButton: button, NDropdown: dropdown, ExcelImportPreview: true } }
  });
  return { wrapper, exportApi, exportSelectedApi };
}

describe('Excel export selection', () => {
  it('exports selected IDs separately from filtered results and reacts to selection changes', async () => {
    const { wrapper, exportApi, exportSelectedApi } = setup(['first', 'second']);
    const selected = () =>
      wrapper.findAll('button').find(node => node.text().startsWith('common.excelExportSelected'))!;
    expect(selected().text()).toBe('common.excelExportSelected:2');
    await selected().trigger('click');
    await flushPromises();
    expect(exportSelectedApi).toHaveBeenCalledWith(['first', 'second']);
    expect(exportApi).not.toHaveBeenCalled();
    expect(downloadExcel).toHaveBeenCalled();
    await wrapper.setProps({ selectedIds: ['third'] });
    expect(selected().text()).toBe('common.excelExportSelected:1');
    await selected().trigger('click');
    await flushPromises();
    expect(exportSelectedApi).toHaveBeenLastCalledWith(['third']);
    await wrapper
      .findAll('button')
      .find(node => node.text() === 'common.excelExportFiltered')!
      .trigger('click');
    await flushPromises();
    expect(exportApi).toHaveBeenCalledOnce();
  });

  it('disables empty selection and guards programmatic empty exports', async () => {
    const { wrapper, exportApi, exportSelectedApi } = setup();
    expect(
      wrapper
        .findAll('button')
        .find(node => node.text() === 'common.excelExportSelected:0')!
        .attributes('disabled')
    ).toBeDefined();
    wrapper.findComponent(dropdown).vm.$emit('select', 'selected');
    await flushPromises();
    expect(exportApi).not.toHaveBeenCalled();
    expect(exportSelectedApi).not.toHaveBeenCalled();
  });

  it('preserves legacy export and respects export permission', async () => {
    const { wrapper, exportApi } = setup([], true);
    expect(wrapper.findComponent(dropdown).exists()).toBe(false);
    await wrapper.get('button').trigger('click');
    await flushPromises();
    expect(exportApi).toHaveBeenCalledOnce();
    await wrapper.setProps({ canExport: false });
    expect(wrapper.find('button').exists()).toBe(false);
  });
});
