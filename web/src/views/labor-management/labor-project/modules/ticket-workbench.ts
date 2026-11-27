export type WorkbenchStatus = 'pending' | 'completed' | 'all';

type LaborProject = Api.LaborManagementManage.LaborProject;
type LaborWorkHour = Api.LaborManagementManage.LaborWorkHour;
type Order = Api.OrderManagementManage.Order;

export interface WorkbenchRow {
  id: string;
  order: Order;
  project: LaborProject | null;
  tickets: LaborWorkHour[];
  unassignedTickets: LaborWorkHour[];
  assignedTicketCount: number;
  monthHours: number;
  noPainting: boolean;
  pending: boolean;
  completed: boolean;
}

export interface WorkbenchStats {
  pendingOrders: number;
  completedOrders: number;
  unassignedTickets: number;
  monthHours: number;
  monthTickets: number;
}

export function isTicketAssigned(ticket: Pick<LaborWorkHour, 'workerId' | 'allocationMonth'>): boolean {
  return Boolean(ticket.workerId && ticket.allocationMonth);
}

export function assignedHoursInMonth(tickets: LaborWorkHour[], month: string): number {
  const monthKey = month.slice(0, 7);
  return tickets.reduce((total, ticket) => {
    if (!isTicketAssigned(ticket) || ticket.allocationMonth?.slice(0, 7) !== monthKey) return total;
    const hours = Number(ticket.workHours);
    return Number.isFinite(hours) ? total + hours : total;
  }, 0);
}

export function buildWorkbenchRows(
  orders: Order[],
  ticketsByOrder: Record<string, LaborWorkHour[]>,
  projectsByPartNo: Map<string, LaborProject>,
  statsMonth: string
): WorkbenchRow[] {
  const seen = new Set<string>();
  const rows: WorkbenchRow[] = [];
  for (const order of orders) {
    if (seen.has(order.id)) continue;
    seen.add(order.id);
    const project = projectsByPartNo.get(order.partNo) ?? null;
    const tickets = ticketsByOrder[order.orderNo] ?? [];
    const unassignedTickets = tickets.filter(ticket => !isTicketAssigned(ticket));
    const noPainting = Boolean(project?.skipPainting);
    rows.push({
      id: order.id,
      order,
      project,
      tickets,
      unassignedTickets,
      assignedTicketCount: tickets.length - unassignedTickets.length,
      monthHours: assignedHoursInMonth(tickets, statsMonth),
      noPainting,
      pending: !noPainting && (tickets.length === 0 || unassignedTickets.length > 0),
      completed: !noPainting && tickets.length > 0 && unassignedTickets.length === 0
    });
  }
  return rows;
}

export function filterWorkbenchRows(rows: WorkbenchRow[], status: WorkbenchStatus, keyword: string): WorkbenchRow[] {
  const normalizedKeyword = keyword.trim().toLowerCase();
  return rows.filter(row => {
    if (status === 'pending' && !row.pending) return false;
    if (status === 'completed' && !row.completed) return false;
    if (!normalizedKeyword) return true;
    return [row.order.orderNo, row.order.partNo, row.order.name, ...row.tickets.map(ticket => ticket.ticketCode)].some(
      value => value?.toLowerCase().includes(normalizedKeyword)
    );
  });
}

export function summarizeWorkbench(rows: WorkbenchRow[], statsMonth: string): WorkbenchStats {
  const stats: WorkbenchStats = {
    pendingOrders: 0,
    completedOrders: 0,
    unassignedTickets: 0,
    monthHours: 0,
    monthTickets: 0
  };
  const monthKey = statsMonth.slice(0, 7);
  for (const row of rows) {
    if (row.pending) stats.pendingOrders += 1;
    if (row.completed) stats.completedOrders += 1;
    stats.unassignedTickets += row.unassignedTickets.length;
    for (const ticket of row.tickets) {
      if (!isTicketAssigned(ticket) || ticket.allocationMonth?.slice(0, 7) !== monthKey) continue;
      const hours = Number(ticket.workHours);
      if (!Number.isFinite(hours)) continue;
      stats.monthHours += hours;
      stats.monthTickets += 1;
    }
  }
  return stats;
}

export function currentMonthValue(now = new Date()): string {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`;
}

export function monthImportRange(month: string | null): {
  importedAtStart: string | null;
  importedAtEnd: string | null;
} {
  if (!month) return { importedAtStart: null, importedAtEnd: null };
  const [year, monthNumber] = month.split('-').map(Number);
  const start = new Date(year, monthNumber - 1, 1);
  const end = new Date(year, monthNumber, 1);
  return {
    importedAtStart: start.toISOString(),
    importedAtEnd: new Date(end.getTime() - 1).toISOString()
  };
}

export function formatHours(value: number): string {
  if (!Number.isFinite(value)) return '0';
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}
