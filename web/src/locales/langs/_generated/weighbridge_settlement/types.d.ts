// 自动生成（cli-gen-web）— 模块 weighbridge_settlement 的 i18n 类型扩展。
// 通过 interface declaration merging 注入 App.I18n.GeneratedPages。

declare global {
  namespace App.I18n {
    interface GeneratedPages {
      weighbridge_settlement: {
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
