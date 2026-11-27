import { expect, it, vi } from 'vitest';
import { fetchGetLaborProjectList } from '@/service/api';
import { fetchLaborProjectsForImportRange } from '../matching-orders';

vi.mock('@/service/api', () => ({
  fetchGetLaborProjectList: vi.fn(),
  fetchGetOrderList: vi.fn(),
  fetchGetLaborWorkHourList: vi.fn()
}));

it('loads every project page inside the import range', async () => {
  const start = new Date(2026, 10, 1).toISOString();
  const end = new Date(new Date(2026, 11, 1).getTime() - 1).toISOString();
  const startMs = Date.parse(start);
  const endMs = Date.parse(end);
  vi.mocked(fetchGetLaborProjectList)
    .mockResolvedValueOnce({
      data: {
        records: [{ id: '1', partNo: 'P1', importedAt: startMs }],
        total: 2
      },
      error: null
    } as never)
    .mockResolvedValueOnce({
      data: {
        records: [{ id: '2', partNo: 'P2', importedAt: endMs }],
        total: 2
      },
      error: null
    } as never);

  const result = await fetchLaborProjectsForImportRange({ importedAtStart: start, importedAtEnd: end }, () => true);

  expect(result?.map(project => project.partNo)).toEqual(['P1', 'P2']);
  expect(fetchGetLaborProjectList).toHaveBeenCalledWith({
    current: 1,
    size: 1000,
    importedAtStart: start,
    importedAtEnd: end
  });
  expect(fetchGetLaborProjectList).toHaveBeenCalledTimes(2);
  vi.clearAllMocks();
});

it('rejects projects outside the requested import range', async () => {
  const start = new Date(2026, 10, 1);
  vi.mocked(fetchGetLaborProjectList).mockResolvedValueOnce({
    data: {
      records: [{ id: '1', partNo: 'P1', importedAt: start.getTime() - 1 }],
      total: 1
    },
    error: null
  } as never);

  await expect(
    fetchLaborProjectsForImportRange({ importedAtStart: start.toISOString(), importedAtEnd: null }, () => true)
  ).rejects.toThrow();
  vi.clearAllMocks();
});

it('returns null when the project request is no longer current', async () => {
  vi.mocked(fetchGetLaborProjectList).mockResolvedValueOnce({
    data: { records: [], total: 0 },
    error: null
  } as never);

  expect(
    await fetchLaborProjectsForImportRange({ importedAtStart: null, importedAtEnd: null }, () => false)
  ).toBeNull();
  vi.clearAllMocks();
});
