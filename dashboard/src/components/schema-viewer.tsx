import { useState } from "react";
import { ChevronRight, ChevronDown, Code, List } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface JsonSchemaProperty {
  type?: string;
  description?: string;
  items?: JsonSchemaProperty;
  properties?: Record<string, JsonSchemaProperty>;
  required?: string[];
  enum?: string[];
  default?: unknown;
}

interface JsonSchema {
  type?: string;
  properties?: Record<string, JsonSchemaProperty>;
  required?: string[];
  items?: JsonSchemaProperty;
  description?: string;
}

const TYPE_COLORS: Record<string, string> = {
  string: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
  number: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
  integer: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
  boolean: "bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20",
  object: "bg-violet-500/10 text-violet-600 dark:text-violet-400 border-violet-500/20",
  array: "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/20",
};

function getTypeLabel(prop: JsonSchemaProperty): string {
  if (prop.type === "array" && prop.items?.type) {
    return `${prop.items.type}[]`;
  }
  return prop.type ?? "unknown";
}

function PropertyRow({
  name,
  prop,
  isRequired,
  depth,
}: {
  name: string;
  prop: JsonSchemaProperty;
  isRequired: boolean;
  depth: number;
}) {
  const [expanded, setExpanded] = useState(depth < 1);
  const hasChildren =
    (prop.type === "object" && prop.properties && Object.keys(prop.properties).length > 0) ||
    (prop.type === "array" && prop.items?.type === "object" && prop.items?.properties);

  const nestedProperties =
    prop.type === "object"
      ? prop.properties
      : prop.type === "array" && prop.items?.type === "object"
        ? prop.items.properties
        : undefined;

  const nestedRequired =
    prop.type === "object"
      ? prop.required
      : prop.type === "array" && prop.items?.type === "object"
        ? prop.items.required
        : undefined;

  return (
    <div>
      <div
        className={cn(
          "flex items-center gap-2 py-1.5 px-2 rounded-md transition-colors",
          hasChildren && "cursor-pointer hover:bg-muted/30"
        )}
        onClick={hasChildren ? () => setExpanded(!expanded) : undefined}
      >
        {hasChildren ? (
          expanded ? (
            <ChevronDown className="size-3 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="size-3 shrink-0 text-muted-foreground" />
          )
        ) : (
          <span className="w-3 shrink-0" />
        )}

        <span className="text-sm font-medium font-mono">{name}</span>
        {isRequired && (
          <span className="text-xs text-destructive font-bold">*</span>
        )}

        <Badge
          variant="outline"
          className={cn(
            "text-[10px] ml-1",
            TYPE_COLORS[prop.type ?? ""] ?? "bg-muted text-muted-foreground border-border"
          )}
        >
          {getTypeLabel(prop)}
        </Badge>

        {prop.default !== undefined && (
          <span className="text-[10px] text-muted-foreground ml-auto font-mono">
            = {JSON.stringify(prop.default)}
          </span>
        )}
      </div>

      {prop.description && (
        <p className="text-xs text-muted-foreground ml-7 -mt-0.5 mb-1">
          {prop.description}
        </p>
      )}

      {prop.enum && prop.enum.length > 0 && (
        <div className="flex flex-wrap gap-1 ml-7 mb-1">
          {prop.enum.map((value) => (
            <span
              key={value}
              className="inline-flex items-center rounded-md bg-muted/60 px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground ring-1 ring-inset ring-border/50"
            >
              {value}
            </span>
          ))}
        </div>
      )}

      {expanded && hasChildren && nestedProperties && (
        <div className="ml-4 border-l-2 border-border/40 pl-2">
          {Object.entries(nestedProperties).map(([childName, childProp]) => (
            <PropertyRow
              key={childName}
              name={childName}
              prop={childProp}
              isRequired={nestedRequired?.includes(childName) ?? false}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function SchemaViewer({ schema }: { schema: Record<string, unknown> }) {
  const [showRaw, setShowRaw] = useState(false);
  const typedSchema = schema as JsonSchema;
  const hasProperties =
    typedSchema.properties && Object.keys(typedSchema.properties).length > 0;
  const isEmpty = Object.keys(schema).length === 0;

  if (isEmpty) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <Code className="size-6 text-muted-foreground/50 mb-2" />
        <p className="text-xs text-muted-foreground">No schema defined for this tool</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* View toggle */}
      <div className="flex items-center gap-1 rounded-md bg-muted/40 p-0.5 w-fit">
        <button
          onClick={() => setShowRaw(false)}
          className={cn(
            "flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors",
            !showRaw
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          <List className="size-3" />
          Form
        </button>
        <button
          onClick={() => setShowRaw(true)}
          className={cn(
            "flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors",
            showRaw
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          <Code className="size-3" />
          Raw JSON
        </button>
      </div>

      {showRaw ? (
        <pre className="overflow-x-auto rounded-md bg-muted/50 p-3 font-mono text-xs leading-relaxed">
          {JSON.stringify(schema, null, 2)}
        </pre>
      ) : hasProperties ? (
        <div className="space-y-0.5">
          {typedSchema.description && (
            <p className="text-xs text-muted-foreground mb-3">{typedSchema.description}</p>
          )}
          {Object.entries(typedSchema.properties!).map(([name, prop]) => (
            <PropertyRow
              key={name}
              name={name}
              prop={prop}
              isRequired={typedSchema.required?.includes(name) ?? false}
              depth={0}
            />
          ))}
        </div>
      ) : (
        <pre className="overflow-x-auto rounded-md bg-muted/50 p-3 font-mono text-xs leading-relaxed">
          {JSON.stringify(schema, null, 2)}
        </pre>
      )}
    </div>
  );
}
