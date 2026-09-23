import { useState } from "react";

import type { ReportingFilterState } from "./rules";
import { defaultReportingRange, reportingQueryOf } from "./rules";

export const DEFAULT_PAGE_SIZE = 10;
const FIRST_PAGE = 1;

const initialFilters = (now: Date): ReportingFilterState => ({
  countries: "",
  products: "",
  senderIds: "",
  userIds: "",
  ...defaultReportingRange(now),
});

export function useReportingControls(now: Date) {
  const [filters, setFilters] = useState(() => initialFilters(now));
  const [page, setPage] = useState(FIRST_PAGE);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);

  const changeFilters = (next: ReportingFilterState) => {
    setFilters(next);
    setPage(FIRST_PAGE);
  };

  const changePageSize = (next: number) => {
    setPageSize(next);
    setPage(FIRST_PAGE);
  };

  return {
    changeFilters,
    changePageSize,
    filters,
    page,
    pageSize,
    query: reportingQueryOf(filters, page, pageSize),
    setPage,
  };
}
