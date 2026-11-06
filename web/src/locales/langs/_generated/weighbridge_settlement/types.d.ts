// 自动生成（cli-gen-web）— 模块 weighbridge_settlement 的 i18n 类型扩展。
// 通过 interface declaration merging 注入 App.I18n.GeneratedPages。

declare global {
  namespace App.I18n {
    interface GeneratedPages {
      weighbridge_settlement: {
        settlement: {
          details: string;
          lines: string;
          partNo: string;
          orderNo: string;
          name: string;
          netWeight: string;
          grossWeight: string;
          quantity: string;
          theoreticalWeight: string;
          allocatedWeight: string;
          amount: string;
          taxUnitPrice: string;
          source: string;
          matched: string;
          manual: string;
          searchOrders: string;
          addLine: string;
          settle: string;
          settleConfirm: string;
          settled: string;
          unsettled: string;
          preview: string;
          totalTheoreticalWeight: string;
          refreshPrice: string;
          requiredLines: string;
          previewFailed: string;
          loadFailed: string;
          noOrders: string;
          retry: string;
        };
        common: {
          status: string;
          form: { status: string };
        };
        settlement_rate: {
          pageTitle: string;
          processName: string;
          price: string;
          enabled: string;
          form: {
            processName: string;
            price: string;
            enabled: string;
          };
          addSettlementRate: string;
          editSettlementRate: string;
        };
        weighing_ticket: {
          pageTitle: string;
          images: string;
          ticketNo: string;
          weighingDate: string;
          weight: string;
          process: string;
          price: string;
          totalAmount: string;
          isSettled: string;
          revision: string;
          rate: string;
          form: {
            ticketNo: string;
            weighingDate: string;
            weight: string;
            process: string;
            price: string;
            totalAmount: string;
            isSettled: string;
            revision: string;
            rate: string;
          };
          addWeighingTicket: string;
          editWeighingTicket: string;
        };
      };
    }
  }
}

export {};
