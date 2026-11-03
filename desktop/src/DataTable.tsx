import type { ComponentProps } from "react";
import "./dataTable.css";

/** Native table markup and refs stay available to each view's existing controls. */
export function DataTable({
  className = "",
  layout = "native",
  ...props
}: ComponentProps<"table"> & { layout?: "native" | "grid" }) {
  return (
    <table
      {...props}
      data-layout={layout}
      className={`data-table ${className}`}
    />
  );
}

/** Shared scroll surface for tables, grid rows, and selectable file lists. */
export function TableScroll({
  className = "",
  ...props
}: ComponentProps<"div">) {
  return <div {...props} className={`data-table-scroll ${className}`} />;
}

/** Overlay keeps its original-pattern row pinned outside the scrolling body. */
export function TableBodyScroll({
  className = "",
  ...props
}: ComponentProps<"tbody">) {
  return <tbody {...props} className={`data-table-scroll ${className}`} />;
}

export function TableActions({
  className = "",
  orientation = "horizontal",
  role = "toolbar",
  ...props
}: ComponentProps<"div"> & { orientation?: "horizontal" | "vertical" }) {
  return (
    <div
      {...props}
      role={role}
      aria-orientation={role === "toolbar" ? orientation : undefined}
      data-orientation={orientation}
      className={`data-table-actions ${className}`}
    />
  );
}
