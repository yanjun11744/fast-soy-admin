import { expect, it, vi } from 'vitest';
import { fetchGetLaborWorkHourList } from '@/service/api';
import { fetchTicketsForOrders } from '../matching-orders';

vi.mock('@/service/api', () => ({ fetchGetOrderList: vi.fn(), fetchGetLaborWorkHourList: vi.fn() }));

it('groups tickets by order and follows every page of a batch', async () => {
  vi.mocked(fetchGetLaborWorkHourList)
    .mockResolvedValueOnce({
      data: {
        records: [
          { id: '1', orderNo: 'O1' },
          { id: '2', orderNo: 'O2' }
        ],
        total: 3
      },
      error: null
    } as never)
    .mockResolvedValueOnce({
      data: { records: [{ id: '3', orderNo: 'O1' }], total: 3 },
      error: null
    } as never);

  const grouped = await fetchTicketsForOrders(['O1', 'O2'], () => true);

  expect(fetchGetLaborWorkHourList).toHaveBeenCalledWith({ current: 1, size: 1000, orderNos: ['O1', 'O2'] });
  expect(fetchGetLaborWorkHourList).toHaveBeenCalledTimes(2);
  expect(grouped?.get('O1')?.map(ticket => ticket.id)).toEqual(['1', '3']);
  expect(grouped?.get('O2')?.map(ticket => ticket.id)).toEqual(['2']);
  vi.clearAllMocks();
});

it('splits more than one hundred order numbers into exact batches', async () => {
  const orderNos = Array.from({ length: 101 }, (_, index) => `O${index + 1}`);
  vi.mocked(fetchGetLaborWorkHourList).mockResolvedValue({ data: { records: [], total: 0 }, error: null } as never);

  await fetchTicketsForOrders(orderNos, () => true);

  expect(fetchGetLaborWorkHourList).toHaveBeenCalledTimes(2);
  expect(vi.mocked(fetchGetLaborWorkHourList).mock.calls[0]?.[0]?.orderNos).toHaveLength(100);
  expect(vi.mocked(fetchGetLaborWorkHourList).mock.calls[1]?.[0]?.orderNos).toEqual(['O101']);
  vi.clearAllMocks();
});

it('rejects results that ignore the exact order filter', async () => {
  vi.mocked(fetchGetLaborWorkHourList).mockResolvedValueOnce({
    data: { records: [{ id: '1', orderNo: 'O9' }], total: 1 },
    error: null
  } as never);

  await expect(fetchTicketsForOrders(['O1'], () => true)).rejects.toThrow();
  vi.clearAllMocks();
});

it('stops when the request is no longer current', async () => {
  vi.mocked(fetchGetLaborWorkHourList)
    .mockResolvedValueOnce({
      data: { records: [{ id: '1', orderNo: 'O1' }], total: 2 },
      error: null
    } as never)
    .mockResolvedValueOnce({
      data: { records: [{ id: '2', orderNo: 'O1' }], total: 2 },
      error: null
    } as never);
  let checks = 0;
  const isCurrent = () => {
    checks += 1;
    return checks === 1;
  };

  expect(await fetchTicketsForOrders(['O1'], isCurrent)).toBeNull();
  expect(fetchGetLaborWorkHourList).toHaveBeenCalledTimes(2);
  vi.clearAllMocks();
});
