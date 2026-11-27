import { onBeforeUnmount, ref } from 'vue';
import { fetchGetLaborWorkerList } from '@/service/api';
import { $t } from '@/locales';
import {
  fetchLaborProjectsForImportRange,
  fetchMatchingOrdersForProjects,
  fetchTicketsForOrders
} from './matching-orders';
import { monthImportRange } from './ticket-workbench';

type LaborProject = Api.LaborManagementManage.LaborProject;
type LaborWorkHour = Api.LaborManagementManage.LaborWorkHour;
type Order = Api.OrderManagementManage.Order;

export type WorkerOption = { label: string; value: string };

/**
 * Server orchestration for the ticket workbench: load the imported projects,
 * their exact matching orders, and the tickets of every matched order.
 */
export function useTicketWorkbenchData() {
  const projects = ref<LaborProject[]>([]);
  const orders = ref<Order[]>([]);
  const ticketsByOrder = ref<Record<string, LaborWorkHour[]>>({});
  const workerOptions = ref<WorkerOption[]>([]);
  const loading = ref(false);
  const failed = ref(false);
  const workersLoading = ref(false);
  const workersFailed = ref(false);

  let requestSequence = 0;
  let workerRequestSequence = 0;
  const orderRequestSequences = new Map<string, number>();

  async function loadWorkers() {
    const sequence = ++workerRequestSequence;
    workersLoading.value = true;
    workersFailed.value = false;
    try {
      const options: WorkerOption[] = [];
      let page = 1;
      let total = 0;
      do {
        const { data, error } = await fetchGetLaborWorkerList({ current: page, size: 1000 });
        if (sequence !== workerRequestSequence) return;
        if (error || !data) throw new Error('Worker lookup failed');
        options.push(
          ...data.records.map(worker => ({ label: `${worker.name}（${worker.employeeNo}）`, value: worker.id }))
        );
        total = data.total;
        if (!data.records.length) break;
        page += 1;
      } while (options.length < total);
      workerOptions.value = options;
    } catch {
      if (sequence === workerRequestSequence) workersFailed.value = true;
    } finally {
      if (sequence === workerRequestSequence) workersLoading.value = false;
    }
  }

  async function loadAll(importMonth: string | null) {
    const sequence = ++requestSequence;
    const isCurrent = () => sequence === requestSequence;
    loading.value = true;
    failed.value = false;
    try {
      const projectList = await fetchLaborProjectsForImportRange(monthImportRange(importMonth), isCurrent);
      if (!projectList || !isCurrent()) return;
      const groupedOrders = await fetchMatchingOrdersForProjects(
        projectList.map(project => project.partNo),
        isCurrent
      );
      if (!groupedOrders || !isCurrent()) return;
      const flatOrders = [...groupedOrders.values()].flat();
      const orderNos = [...new Set(flatOrders.map(order => order.orderNo))];
      const groupedTickets = orderNos.length
        ? await fetchTicketsForOrders(orderNos, isCurrent)
        : new Map<string, LaborWorkHour[]>();
      if (!groupedTickets || !isCurrent()) return;

      const ticketRecord: Record<string, LaborWorkHour[]> = {};
      for (const [orderNo, tickets] of groupedTickets) ticketRecord[orderNo] = tickets;

      projects.value = projectList;
      orders.value = flatOrders;
      ticketsByOrder.value = ticketRecord;
      orderRequestSequences.clear();
    } catch {
      if (isCurrent()) failed.value = true;
    } finally {
      if (isCurrent()) loading.value = false;
    }
  }

  async function reloadOrderTickets(orderNo: string) {
    const sequence = (orderRequestSequences.get(orderNo) ?? 0) + 1;
    orderRequestSequences.set(orderNo, sequence);
    try {
      const grouped = await fetchTicketsForOrders([orderNo], () => orderRequestSequences.get(orderNo) === sequence);
      if (!grouped) return;
      ticketsByOrder.value = { ...ticketsByOrder.value, [orderNo]: grouped.get(orderNo) ?? [] };
    } catch {
      if (orderRequestSequences.get(orderNo) === sequence) {
        window.$message?.error($t('page.labor_management.labor_project.reloadOrderTicketsFailed'));
      }
    }
  }

  function dispose() {
    requestSequence += 1;
    workerRequestSequence += 1;
    orderRequestSequences.clear();
  }

  onBeforeUnmount(dispose);

  return {
    projects,
    orders,
    ticketsByOrder,
    workerOptions,
    loading,
    failed,
    workersLoading,
    workersFailed,
    loadWorkers,
    loadAll,
    reloadOrderTickets
  };
}
