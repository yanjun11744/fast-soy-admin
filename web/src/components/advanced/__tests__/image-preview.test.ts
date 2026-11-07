import { defineComponent } from 'vue';
import { mount } from '@vue/test-utils';
import { expect, it, vi } from 'vitest';
import ImagePreview from '../image-preview.vue';

vi.mock('@/locales', () => ({ $t: (key: string) => key }));
vi.mock('@/utils/image', () => ({ imageUrls: (value: string[]) => value, imageSrc: (value: string) => value }));
const space = defineComponent({ name: 'NSpace', props: ['justify', 'align'], template: '<div><slot /></div>' });

it.each([['/one'], ['/one', '/two']])('centers image groups including a single image: %j', (...value) => {
  const wrapper = mount(ImagePreview, {
    props: { value },
    global: { stubs: { NImageGroup: { template: '<div><slot /></div>' }, NSpace: space, NImage: true } }
  });
  expect(wrapper.findComponent(space).props()).toMatchObject({ justify: 'center', align: 'center' });
  expect(wrapper.findComponent(space).classes()).toContain('w-full');
  wrapper.unmount();
});
