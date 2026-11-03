import { defineComponent } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import type { ExcelPreview } from '@/utils/excel';
import { $t } from '@/locales';
import ExcelImportPreview from '../excel-import-preview.vue';

vi.mock('@/locales', () => ({ $t: vi.fn((key: string) => key) }));

const container = defineComponent({ template: '<div><slot /></div>' });
const button = defineComponent({
  name: 'NButton',
  props: ['disabled'],
  emits: ['click'],
  template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>'
});
const select = defineComponent({
  name: 'NSelect',
  props: ['value', 'options', 'disabled'],
  emits: ['update:value'],
  template: '<select :disabled="disabled" />'
});
const inputNumber = defineComponent({
  name: 'NInputNumber',
  props: ['value'],
  emits: ['update:value'],
  template: '<input />'
});

function preview(unknown = false): ExcelPreview {
  return {
    sheets: ['Data', 'Other'],
    sheet: 'Data',
    headerRow: 1,
    fields: [{ name: 'name', title: '名称', required: true }],
    columns: [
      { index: 0, header: '名称', field: 'name', samples: ['example'] },
      ...(unknown ? [{ index: 1, header: 'other', field: null, samples: ['value'] }] : [])
    ],
    rowCount: 1,
    errors: []
  };
}

async function setup(data = preview()) {
  const previewApi = vi.fn().mockResolvedValue({ data, error: null });
  const importApi = vi.fn().mockResolvedValue({ data: { importedCount: 1 }, error: null });
  const wrapper = mount(ExcelImportPreview, {
    props: { file: new File(['test'], 'test.xlsx'), previewApi, importApi },
    global: {
      stubs: {
        NModal: container,
        NCard: container,
        NSpace: container,
        NAlert: container,
        NFormItem: container,
        NSpin: container,
        NTable: container,
        NButton: button,
        NSelect: select,
        NInputNumber: inputNumber
      }
    }
  });
  await flushPromises();
  function action(key: string) {
    return wrapper.findAll('button').find(node => node.text() === `common.${key}`)!;
  }
  return { wrapper, previewApi, importApi, action };
}

describe('Excel import preview', () => {
  it.each([
    [
      { importedCount: 5, createdCount: 2, updatedCount: 3 },
      { created: 2, updated: 3 }
    ],
    [
      { importedCount: 5, createdCount: 0, updatedCount: 5 },
      { created: 0, updated: 5 }
    ],
    [{ importedCount: 5 }, { created: 5, updated: 0 }]
  ])('shows separate created and updated counts', async (result, counts) => {
    const success = vi.fn();
    window.$message = { success } as never;
    const { wrapper, importApi, action } = await setup();
    importApi.mockResolvedValue({ data: result, error: null });
    vi.mocked($t).mockClear();
    await action('excelConfirmImport').trigger('click');
    await flushPromises();
    expect($t).toHaveBeenCalledWith('common.excelImportSuccess', counts);
    expect(success).toHaveBeenCalled();
    wrapper.unmount();
  });
  it('submits the validated selection and emits completion', async () => {
    const { wrapper, importApi, action } = await setup();
    expect(action('excelConfirmImport').attributes('disabled')).toBeUndefined();
    await action('excelConfirmImport').trigger('click');
    await flushPromises();
    expect(importApi).toHaveBeenCalledWith(expect.any(File), { sheet: 'Data', headerRow: 1, columns: ['name'] });
    expect(wrapper.emitted('imported')).toHaveLength(1);
    expect(wrapper.emitted('close')).toHaveLength(1);
    wrapper.unmount();
  });

  it('defaults unknown columns to ignore and submits without another validation', async () => {
    const { wrapper, previewApi, importApi, action } = await setup(preview(true));
    expect(wrapper.findAllComponents(select)[2].props('value')).toBe('');
    expect(action('excelConfirmImport').attributes('disabled')).toBeUndefined();
    await action('excelConfirmImport').trigger('click');
    await flushPromises();
    expect(previewApi).toHaveBeenCalledTimes(1);
    expect(importApi).toHaveBeenCalledWith(expect.any(File), {
      sheet: 'Data',
      headerRow: 1,
      columns: ['name', null]
    });
    wrapper.unmount();
  });

  it('requires revalidation when an ignored column is manually mapped', async () => {
    const { wrapper, previewApi, action } = await setup(preview(true));
    wrapper.findAllComponents(select)[2].vm.$emit('update:value', 'name');
    await flushPromises();
    expect(action('excelConfirmImport').attributes('disabled')).toBeDefined();
    previewApi.mockResolvedValue({ data: { ...preview(true), errors: ['duplicate target'] }, error: null });
    await action('excelValidate').trigger('click');
    await flushPromises();
    expect(previewApi).toHaveBeenLastCalledWith(expect.any(File), {
      sheet: 'Data',
      headerRow: 1,
      columns: ['name', 'name']
    });
    expect(action('excelConfirmImport').attributes('disabled')).toBeDefined();
    wrapper.unmount();
  });

  it('invalidates a successful preview when the mapping changes', async () => {
    const { wrapper, action, importApi } = await setup();
    wrapper.findAllComponents(select)[1].vm.$emit('update:value', '');
    await flushPromises();
    expect(action('excelConfirmImport').attributes('disabled')).toBeDefined();
    expect(importApi).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it('redetects the header after selecting a different worksheet', async () => {
    const { wrapper, previewApi, action } = await setup();
    wrapper.findAllComponents(select)[0].vm.$emit('update:value', 'Other');
    await flushPromises();
    expect(action('excelConfirmImport').attributes('disabled')).toBeDefined();
    await action('excelValidate').trigger('click');
    await flushPromises();
    expect(previewApi).toHaveBeenLastCalledWith(expect.any(File), {
      sheet: 'Other',
      headerRow: undefined,
      columns: undefined
    });
    wrapper.unmount();
  });
});
