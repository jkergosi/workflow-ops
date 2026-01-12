import * as React from "react"
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"

export interface PaginationControlsProps {
  /**
   * Current page number (1-indexed)
   */
  currentPage: number

  /**
   * Total number of pages
   */
  totalPages: number

  /**
   * Total number of items across all pages
   */
  total: number

  /**
   * Current page size (items per page)
   */
  pageSize: number

  /**
   * Available page size options
   * @default [10, 25, 50, 100]
   */
  pageSizeOptions?: number[]

  /**
   * Callback when page changes
   */
  onPageChange: (page: number) => void

  /**
   * Callback when page size changes
   */
  onPageSizeChange: (pageSize: number) => void

  /**
   * Whether data is currently loading
   * @default false
   */
  isLoading?: boolean

  /**
   * Label for the items being paginated (e.g., "items", "executions", "workflows")
   * @default "items"
   */
  itemLabel?: string

  /**
   * Additional CSS classes for the container
   */
  className?: string
}

/**
 * Reusable pagination controls component with First/Previous/Next/Last buttons,
 * page size selector, and item count display.
 *
 * @example
 * ```tsx
 * <PaginationControls
 *   currentPage={currentPage}
 *   totalPages={totalPages}
 *   total={totalItems}
 *   pageSize={pageSize}
 *   onPageChange={setCurrentPage}
 *   onPageSizeChange={(size) => {
 *     setPageSize(size);
 *     setCurrentPage(1);
 *   }}
 *   isLoading={isFetching}
 *   itemLabel="executions"
 * />
 * ```
 */
export const PaginationControls = React.forwardRef<
  HTMLDivElement,
  PaginationControlsProps
>(
  (
    {
      currentPage,
      totalPages,
      total,
      pageSize,
      pageSizeOptions = [10, 25, 50, 100],
      onPageChange,
      onPageSizeChange,
      isLoading = false,
      itemLabel = "items",
      className,
    },
    ref
  ) => {
    // Calculate display range
    const startItem = total > 0 ? (currentPage - 1) * pageSize + 1 : 0
    const endItem = Math.min(currentPage * pageSize, total)

    // Normalize totalPages to be at least 1
    const normalizedTotalPages = totalPages || 1

    // Determine if navigation buttons should be disabled
    const isFirstPage = currentPage === 1
    const isLastPage = currentPage >= normalizedTotalPages
    const disablePrev = isFirstPage || isLoading
    const disableNext = isLastPage || isLoading

    return (
      <div
        ref={ref}
        className={cn(
          "flex items-center justify-between border-t pt-4",
          className
        )}
      >
        {/* Left side: Page size selector and item count */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Label
              htmlFor="pageSize"
              className="text-sm text-muted-foreground whitespace-nowrap"
            >
              Rows per page:
            </Label>
            <Select
              value={pageSize.toString()}
              onValueChange={(value) => onPageSizeChange(Number(value))}
              disabled={isLoading}
            >
              <SelectTrigger
                id="pageSize"
                className="h-8 w-20"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {pageSizeOptions.map((option) => (
                  <SelectItem key={option} value={option.toString()}>
                    {option}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="text-sm text-muted-foreground whitespace-nowrap">
            Showing {startItem} to {endItem} of {total} {itemLabel}
          </div>
        </div>

        {/* Right side: Navigation buttons */}
        <div className="flex items-center gap-2">
          {isLoading && (
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          )}

          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(1)}
            disabled={disablePrev}
            title="First page"
            aria-label="Go to first page"
          >
            <ChevronsLeft className="h-4 w-4" />
            First
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(currentPage - 1)}
            disabled={disablePrev}
            title="Previous page"
            aria-label="Go to previous page"
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </Button>

          <div className="flex items-center gap-1 px-2">
            <span className="text-sm whitespace-nowrap">
              Page {currentPage} of {normalizedTotalPages}
            </span>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(currentPage + 1)}
            disabled={disableNext}
            title="Next page"
            aria-label="Go to next page"
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(normalizedTotalPages)}
            disabled={disableNext}
            title="Last page"
            aria-label="Go to last page"
          >
            Last
            <ChevronsRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    )
  }
)

PaginationControls.displayName = "PaginationControls"
