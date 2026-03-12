import { useState } from "react";
import { Columns3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ColumnDefinition {
  key: string;
  label: string;
  /** If true, this column cannot be hidden */
  locked?: boolean;
}

interface ColumnToggleProps {
  columns: ColumnDefinition[];
  visibleKeys: Set<string>;
  onChange: (visibleKeys: Set<string>) => void;
  className?: string;
}

export function ColumnToggle({
  columns,
  visibleKeys,
  onChange,
  className,
}: ColumnToggleProps) {
  const [open, setOpen] = useState(false);

  function toggle(key: string) {
    const next = new Set(visibleKeys);
    if (next.has(key)) {
      next.delete(key);
    } else {
      next.add(key);
    }
    onChange(next);
  }

  return (
    <div className={cn("relative", className)}>
      <Button
        variant="outline"
        size="sm"
        className="h-8 gap-1.5 text-xs"
        onClick={() => setOpen((o) => !o)}
      >
        <Columns3 className="size-3.5" />
        Columns
      </Button>

      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setOpen(false)}
          />
          <div className="absolute right-0 top-full z-20 mt-1 min-w-[160px] rounded-md border border-border bg-popover p-1 shadow-md">
            {columns.map((col) => (
              <button
                key={col.key}
                disabled={col.locked}
                onClick={() => !col.locked && toggle(col.key)}
                className={cn(
                  "flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-xs transition-colors",
                  col.locked
                    ? "cursor-default text-muted-foreground"
                    : "cursor-pointer hover:bg-muted"
                )}
              >
                <span
                  className={cn(
                    "flex size-4 items-center justify-center rounded-sm border",
                    visibleKeys.has(col.key)
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border"
                  )}
                >
                  {visibleKeys.has(col.key) && (
                    <svg
                      viewBox="0 0 12 12"
                      className="size-2.5 stroke-current"
                      fill="none"
                      strokeWidth="2"
                    >
                      <polyline points="1.5,6 4.5,9 10.5,3" />
                    </svg>
                  )}
                </span>
                {col.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
