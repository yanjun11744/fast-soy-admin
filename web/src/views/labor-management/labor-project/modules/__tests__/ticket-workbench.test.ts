import { expect, it } from 'vitest';
import {
  assignedHoursInMonth,
  buildWorkbenchRows,
  currentMonthValue,
  filterWorkbenchRows,
  monthImportRange,
  summarizeWorkbench
} from '../ticket-workbench';

type Ticket = Api.LaborManagementManage.LaborWorkHour;
type Order = Api.OrderManagementManage.Order;
type Project = Api.LaborManagementManage.LaborProject;

function ticket(overrides: Partial<Ticket> & Pick<Ticket, 'id' | 'orderNo'>): Ticket {
  return {
    ticketCode: `T-${overrides.id}`,
    workHours: 1,
    workerId: null,
    allocationMonth: null,
    ...overrides
  } as Ticket;
}

function order(id: string, orderNo: string, partNo: string): Order {
  return { id, orderNo, partNo, name: `Name ${orderNo}` } as Order;
}

function project(partNo: string, skipPainting = false): Project {
  return { id: partNo, partNo, skipPainting } as Project;
}

it('builds one row per order and only counts truly assigned monthly hours', () => {
  const orders = [order('o1', 'O1', 'P1'), order('o2', 'O2', 'P2'), order('o3', 'O3', 'P3')];
  const tickets: Record<string, Ticket[]> = {
    O1: [
      ticket({ id: 't1', orderNo: 'O1', workerId: 'w1', allocationMonth: '2026-11-01', workHours: 2.5 }),
      ticket({ id: 't2', orderNo: 'O1', workHours: 3 })
    ],
    O2: [],
    O3: [
      ticket({ id: 't3', orderNo: 'O3', workerId: 'w2', allocationMonth: '2026-11-01', workHours: 1 }),
      ticket({ id: 't4', orderNo: 'O3', workerId: 'w2', allocationMonth: '2026-12-01', workHours: 4 })
    ]
  };
  const projects = new Map([
    ['P1', project('P1')],
    ['P2', project('P2', true)],
    ['P3', project('P3')]
  ]);

  const rows = buildWorkbenchRows(orders, tickets, projects, '2026-11-01');
  expect(rows).toHaveLength(3);
  expect(rows[0]).toMatchObject({
    id: 'o1',
    assignedTicketCount: 1,
    monthHours: 2.5,
    pending: true,
    completed: false,
    noPainting: false
  });
  expect(rows[0].unassignedTickets.map(item => item.id)).toEqual(['t2']);
  expect(rows[1]).toMatchObject({ pending: false, completed: false, noPainting: true });
  expect(rows[2]).toMatchObject({ pending: false, completed: true, monthHours: 1 });
});

it('filters the pending queue without hiding unassigned tickets', () => {
  const rows = buildWorkbenchRows(
    [order('o1', 'O1', 'P1'), order('o2', 'O2', 'P2'), order('o3', 'O3', 'P3')],
    {
      O1: [ticket({ id: 't1', orderNo: 'O1', workerId: 'w1', allocationMonth: '2026-11-01' })],
      O2: [ticket({ id: 't2', orderNo: 'O2' })],
      O3: []
    },
    new Map([
      ['P1', project('P1')],
      ['P2', project('P2')],
      ['P3', project('P3', true)]
    ]),
    '2026-11-01'
  );

  expect(filterWorkbenchRows(rows, 'pending', '').map(row => row.id)).toEqual(['o2']);
  expect(filterWorkbenchRows(rows, 'completed', '').map(row => row.id)).toEqual(['o1']);
  expect(filterWorkbenchRows(rows, 'all', '').map(row => row.id)).toEqual(['o1', 'o2', 'o3']);
  expect(filterWorkbenchRows(rows, 'pending', 'o2').map(row => row.id)).toEqual(['o2']);
  expect(filterWorkbenchRows(rows, 'pending', 'T-t2').map(row => row.id)).toEqual(['o2']);
  expect(filterWorkbenchRows(rows, 'pending', 'missing')).toEqual([]);
});

it('summarizes pending work and assigned hours for the selected month', () => {
  const rows = buildWorkbenchRows(
    [order('o1', 'O1', 'P1'), order('o2', 'O2', 'P2'), order('o3', 'O3', 'P3')],
    {
      O1: [
        ticket({ id: 't1', orderNo: 'O1', workerId: 'w1', allocationMonth: '2026-11-01', workHours: 2 }),
        ticket({ id: 't2', orderNo: 'O1' })
      ],
      O2: [ticket({ id: 't3', orderNo: 'O2', allocationMonth: '2026-11-01', workHours: 5 })],
      O3: [ticket({ id: 't4', orderNo: 'O3', workerId: 'w2', allocationMonth: '2026-11-01', workHours: 3 })]
    },
    new Map([
      ['P1', project('P1')],
      ['P2', project('P2')],
      ['P3', project('P3')]
    ]),
    '2026-11-01'
  );

  expect(summarizeWorkbench(rows, '2026-11-01')).toEqual({
    pendingOrders: 2,
    completedOrders: 1,
    unassignedTickets: 2,
    monthHours: 5,
    monthTickets: 2
  });
});

it('computes half-open import month ranges and a fixed current month value', () => {
  const february = monthImportRange('2026-02');
  expect(new Date(february.importedAtStart as string).getMonth()).toBe(1);
  expect(
    new Date(february.importedAtEnd as string).getTime() - new Date(february.importedAtStart as string).getTime()
  ).toBe(28 * 24 * 60 * 60 * 1000 - 1);
  expect(monthImportRange(null)).toEqual({ importedAtStart: null, importedAtEnd: null });
  expect(currentMonthValue(new Date(2026, 10, 27))).toBe('2026-11-01');
});

it('ignores partial assignments and malformed hours when tallying', () => {
  expect(
    assignedHoursInMonth(
      [
        ticket({ id: 't1', orderNo: 'O1', workerId: 'w1', allocationMonth: '2026-11-01', workHours: 1.5 }),
        ticket({ id: 't2', orderNo: 'O1', allocationMonth: '2026-11-01', workHours: 2 }),
        ticket({ id: 't3', orderNo: 'O1', workerId: 'w1', workHours: 2 }),
        ticket({ id: 't4', orderNo: 'O1', workerId: 'w1', allocationMonth: '2026-11-01', workHours: 2 }),
        ticket({ id: 't5', orderNo: 'O1', workerId: 'w1', allocationMonth: '2026-12-01', workHours: 9 })
      ],
      '2026-11-01'
    )
  ).toBe(3.5);
});
