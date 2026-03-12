import { useState, useMemo, useCallback } from "react";

const DEFAULT_PAGE_SIZE = 25;

interface UsePaginationResult<T> {
  page: number;
  pageSize: number;
  totalPages: number;
  paginatedItems: T[];
  setPage: (page: number) => void;
  setPageSize: (size: number) => void;
}

export function usePagination<T>(
  items: T[],
  initialPageSize: number = DEFAULT_PAGE_SIZE,
): UsePaginationResult<T> {
  const [page, setPageRaw] = useState(1);
  const [pageSize, setPageSizeRaw] = useState(initialPageSize);

  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));

  // Clamp page when items or pageSize change
  const clampedPage = Math.min(page, totalPages);

  const paginatedItems = useMemo(() => {
    const start = (clampedPage - 1) * pageSize;
    return items.slice(start, start + pageSize);
  }, [items, clampedPage, pageSize]);

  const setPage = useCallback(
    (p: number) => {
      setPageRaw(Math.max(1, Math.min(p, totalPages)));
    },
    [totalPages],
  );

  const setPageSize = useCallback((size: number) => {
    setPageSizeRaw(size);
    setPageRaw(1); // Reset to first page on size change
  }, []);

  return {
    page: clampedPage,
    pageSize,
    totalPages,
    paginatedItems,
    setPage,
    setPageSize,
  };
}
