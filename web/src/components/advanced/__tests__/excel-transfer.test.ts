import { defineComponent } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import { downloadExcel } from '@/utils/excel';
import { $t } from '@/locales';
import ExcelTransfer from '../excel-transfer.vue';

vi.mock('@/locales', () => ({
  $t: vi.fn((key: string, params?: { count: number }) => `${key}${params ? `:${params.count}` : ''}`)
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
const modal = defineComponent({
  name: 'NModal',
  template: '<section><slot /><slot name="footer" /></section>'
});
const checkboxGroup = defineComponent({
  name: 'NCheckboxGroup',
  props: ['value', 'disabled'],
  emits: ['update:value'],
  template: '<div><slot /></div>'
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
    global: {
      stubs: {
        NSpace: container,
        NButton: button,
        NDropdown: dropdown,
        ExcelImportPreview: true,
        NModal: modal,
        NFormItem: container,
        NCheckboxGroup: checkboxGroup,
        NCheckbox: true
      }
    }
  });
  return { wrapper, exportApi, exportSelectedApi };
}

describe('Excel export selection', () => {
  it('selects parent fields at export time and keeps a snapshot of selected IDs', async () => {
    const { wrapper, exportApi, exportSelectedApi } = setup(['original']);
    await wrapper.setProps({
      exportParentFields: [
        { name: 'number', label: 'Number' },
        { name: 'date', label: 'Date' }
      ]
    });
    wrapper.findComponent(dropdown).vm.$emit('select', 'selected');
    await flushPromises();
    expect(exportSelectedApi).not.toHaveBeenCalled();
    const group = wrapper.findComponent(checkboxGroup);
    expect(group.props('value')).toEqual(['number', 'date']);
    group.vm.$emit('update:value', ['number']);
    await wrapper.setProps({ selectedIds: ['changed'] });
    await wrapper
      .findComponent(modal)
      .findAll('button')
      .find(node => node.text() === 'common.excelExport')!
      .trigger('click');
    await flushPromises();
    expect(exportSelectedApi).toHaveBeenCalledWith(['original'], ['number']);
    expect(exportApi).not.toHaveBeenCalled();
    expect(wrapper.findComponent(modal).exists()).toBe(false);

    wrapper.findComponent(dropdown).vm.$emit('select', 'filtered');
    await flushPromises();
    wrapper.findComponent(checkboxGroup).vm.$emit('update:value', []);
    await flushPromises();
    await wrapper
      .findComponent(modal)
      .findAll('button')
      .find(node => node.text() === 'common.excelExport')!
      .trigger('click');
    await flushPromises();
    expect(exportApi).toHaveBeenCalledWith([]);
    wrapper.unmount();
  });

  it('cancels parent field selection without downloading and guards revoked export permission', async () => {
    const { wrapper, exportApi } = setup([], true);
    await wrapper.setProps({ exportParentFields: [{ name: 'number', label: 'Number' }] });
    await wrapper.get('button').trigger('click');
    await flushPromises();
    await wrapper
      .findComponent(modal)
      .findAll('button')
      .find(node => node.text() === 'common.cancel')!
      .trigger('click');
    expect(exportApi).not.toHaveBeenCalled();
    await wrapper.get('button').trigger('click');
    await wrapper.setProps({ canExport: false });
    const confirm = wrapper
      .findComponent(modal)
      .findAllComponents(button)
      .find(node => node.text() === 'common.excelExport')!;
    expect(confirm.props('disabled')).toBe(true);
    confirm.vm.$emit('click');
    await flushPromises();
    expect(exportApi).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it.each([
    [
      { importedCount: 5, createdCount: 2, updatedCount: 3 },
      { created: 2, updated: 3 }
    ],
    [{ importedCount: 5 }, { created: 5, updated: 0 }]
  ])('shows import counts without the preview flow', async (result, counts) => {
    const upload = defineComponent({ name: 'NUpload', props: ['customRequest'], template: '<div />' });
    window.$message = { success: vi.fn() } as never;
    const wrapper = mount(ExcelTransfer, {
      props: {
        importApi: vi.fn().mockResolvedValue({ data: result, error: null }),
        templateApi: vi.fn(),
        exportApi: vi.fn()
      },
      global: { stubs: { NSpace: container, NButton: button, NUpload: upload, NDropdown: dropdown } }
    });
    const onFinish = vi.fn();
    vi.mocked($t).mockClear();
    await wrapper.findComponent(upload).props('customRequest')({
      file: { file: new File(['test'], 'test.xlsx') },
      onFinish,
      onError: vi.fn()
    });
    expect($t).toHaveBeenCalledWith('common.excelImportSuccess', counts);
    expect(onFinish).toHaveBeenCalled();
    expect(wrapper.emitted('imported')).toHaveLength(1);
    wrapper.unmount();
  });
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
