import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface VersionEntry {
  version: string;
  date: string;
  author: string;
}

interface VersionSelectorProps {
  label: string;
  versions: VersionEntry[];
  selected: string;
  onChange: (version: string) => void;
  className?: string;
}

export function VersionSelector({
  label,
  versions,
  selected,
  onChange,
  className,
}: VersionSelectorProps) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <span className="text-xs font-medium text-muted-foreground shrink-0">
        {label}
      </span>
      <div className="relative">
        <select
          value={selected}
          onChange={(e) => onChange(e.target.value)}
          className={cn(
            "appearance-none rounded-md border border-border bg-background px-3 py-1.5 pr-8",
            "text-xs font-medium text-foreground",
            "outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1",
            "cursor-pointer transition-colors hover:bg-muted/50"
          )}
        >
          {versions.map((v) => (
            <option key={v.version} value={v.version}>
              v{v.version} — {v.author} ({v.date})
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-2 top-1/2 size-3 -translate-y-1/2 text-muted-foreground" />
      </div>
    </div>
  );
}
