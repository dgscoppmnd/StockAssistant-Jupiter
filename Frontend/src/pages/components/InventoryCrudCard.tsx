import type { FormEvent, ReactNode } from "react";
import BootstrapTable from "react-bootstrap-table-next";
import paginationFactory from "react-bootstrap-table2-paginator";

type InventoryCrudCardProps<T extends Record<string, unknown>> = {
  sectionLabel: string;
  title: string;
  titleIcon?: ReactNode;
  titleInfo?: ReactNode;
  description?: string;
  headerAction?: ReactNode;
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
    onSelectRow?: (row: T) => void;
    selectedKey?: string | number;
  };
};

export default function InventoryCrudCard<T extends Record<string, unknown>>({
  sectionLabel,
  title,
  titleIcon,
  titleInfo,
  description,
  headerAction,
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
        <div className="inventory-crud-header-main">
          <p className="section-label">{sectionLabel}</p>
          {titleInfo ? <div className="routing-info-heading"><h3>{titleIcon}{title}</h3>{titleInfo}</div> : <h3>{titleIcon}{title}</h3>}
          {description ? <p className="muted inventory-crud-description">{description}</p> : null}
        </div>
        {headerAction ? <div className="inventory-crud-action">{headerAction}</div> : null}
      </div>

      {table ? (
        <div className="inventory-crud-table users-table-wrapper">
          <div style={{ minWidth: table.minWidth ?? 760 }}>
            <BootstrapTable
              keyField={table.keyField}
              data={table.data}
              columns={table.columns}
              classes={`users-table inventory-bootstrap-table${table.onSelectRow ? ' inventory-selectable-table' : ''}`}
              rowClasses={(row: T) => table.selectedKey === row[table.keyField] ? 'inventory-row-selected' : ''}
              rowAttrs={(row: T) => table.onSelectRow ? {tabIndex: 0, 'aria-selected': table.selectedKey === row[table.keyField]} : {}}
              rowEvents={table.onSelectRow ? {
                onClick: (event: React.MouseEvent<HTMLElement>, row: T) => {
                  if (!(event.target as HTMLElement).closest('button,a,input,select,textarea')) table.onSelectRow?.(row);
                },
                onKeyDown: (event: React.KeyboardEvent<HTMLElement>, row: T) => {
                  if (event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) {
                    event.preventDefault();table.onSelectRow?.(row);
                  }
                },
              } : undefined}
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
