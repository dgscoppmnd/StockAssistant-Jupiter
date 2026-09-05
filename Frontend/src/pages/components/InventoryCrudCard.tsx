import type { FormEvent, ReactNode } from "react";
import BootstrapTable from "react-bootstrap-table-next";
import paginationFactory from "react-bootstrap-table2-paginator";

type InventoryCrudCardProps<T extends Record<string, unknown>> = {
  sectionLabel: string;
  title: string;
  titleIcon?: ReactNode;
  description?: string;
  className?: string;
  formClassName?: string;
  children?: ReactNode;
  footer?: ReactNode;
  onSubmit?: (event: FormEvent<HTMLFormElement>) => void | Promise<void>;
  table?: {
    keyField: string;
    data: T[];
    columns: any[];
    noDataIndication: string;
    totalLabel: string;
    minWidth?: number;
  };
};

export default function InventoryCrudCard<T extends Record<string, unknown>>({
  sectionLabel,
  title,
  titleIcon,
  description,
  className = "",
  formClassName = "stack",
  children,
  footer,
  onSubmit,
  table,
}: InventoryCrudCardProps<T>) {
  return (
    <article className={`card inventory-crud-card ${className}`.trim()}>
      <div className="inventory-crud-header">
        <p className="section-label">{sectionLabel}</p>
        <h3>{titleIcon}{title}</h3>
        {description ? <p className="muted inventory-crud-description">{description}</p> : null}
      </div>

      {table ? (
        <div className="inventory-crud-table users-table-wrapper">
          <div style={{ minWidth: table.minWidth ?? 760 }}>
            <BootstrapTable
              keyField={table.keyField}
              data={table.data}
              columns={table.columns}
              classes="users-table inventory-bootstrap-table"
              headerClasses="users-table"
              bordered={false}
              noDataIndication={table.noDataIndication}
              pagination={paginationFactory({
                page: 1,
                pageStartIndex: 1,
                sizePerPage: 5,
                sizePerPageList: [
                  { text: "5", value: 5 },
                  { text: "10", value: 10 },
                  { text: "25", value: 25 },
                ],
                showTotal: true,
                paginationTotalRenderer: (from: number, to: number, size: number) =>
                  `${from} - ${to} de ${size} ${table.totalLabel}`,
              })}
            />
          </div>
        </div>
      ) : null}

      {onSubmit ? (
        <form className={formClassName} onSubmit={onSubmit}>
          {children}
          {footer}
        </form>
      ) : (
        <>
          {children}
          {footer}
        </>
      )}
    </article>
  );
}
