// 自动生成（cli-gen-web）— 模块 order_management 的 i18n 类型扩展。
// 通过 interface declaration merging 注入 App.I18n.GeneratedPages。

declare global {
  namespace App.I18n {
    interface GeneratedPages {
      order_management: {
        common: {
          status: string;
          form: { status: string };
        };
        order: {
          pageTitle: string;
          orderNo: string;
          partNo: string;
          name: string;
          unitWeight: string;
          unit: string;
          quantity: string;
          receivedQuantity: string;
          totalWeight: string;
          orderDueDate: string;
          completedDate: string;
          processRoute: string;
          customer: string;
          form: {
            orderNo: string;
            partNo: string;
            name: string;
            unitWeight: string;
            unit: string;
            quantity: string;
            receivedQuantity: string;
            totalWeight: string;
            orderDueDate: string;
            completedDate: string;
            processRoute: string;
            customer: string;
          };
          addOrder: string;
          editOrder: string;
        };
      };
    }
  }
}

export {};
