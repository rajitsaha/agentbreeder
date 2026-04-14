/**
 * NodePalette — sidebar listing draggable node types.
 * Users drag items from here onto the ReactFlow canvas.
 */

import {
  Bot,
  Cpu,
  Wrench,
  Server,
  FileText,
  Brain,
  Database,
  Shield,
  GripVertical,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { type CanvasNodeType, NODE_STYLES } from "./types";

const ICON_MAP: Record<string, typeof Bot> = {
  Bot,
  Cpu,
  Wrench,
  Server,
  FileText,
  Brain,
  Database,
  Shield,
};

interface PaletteEntry {
  type: CanvasNodeType;
  label: string;
  description: string;
}

const PALETTE_ITEMS: PaletteEntry[] = [
  { type: "agent", label: "Agent", description: "Central agent node" },
  { type: "model", label: "Model", description: "LLM model config" },
  { type: "tool", label: "Tool", description: "Tool / function reference" },
  { type: "mcpServer", label: "MCP Server", description: "MCP server endpoint" },
  { type: "prompt", label: "Prompt", description: "System or user prompt" },
  { type: "memory", label: "Memory", description: "Conversation memory" },
  { type: "rag", label: "RAG Index", description: "Knowledge base / RAG" },
  { type: "guardrail", label: "Guardrail", description: "Safety guardrail" },
];

const FRAMEWORK_PALETTE_MAP: Record<string, PaletteEntry[]> = {
  crewai: [
    { type: "agent", label: "Crew Agent", description: "CrewAI role-based agent" },
    { type: "tool", label: "Crew Tool", description: "Tool available to crew members" },
    { type: "prompt", label: "Task Prompt", description: "Task description & expected output" },
    { type: "guardrail", label: "Guardrail", description: "Safety guardrail" },
  ],
  google_adk: [
    { type: "agent", label: "LlmAgent", description: "Google ADK LLM agent" },
    { type: "agent", label: "SequentialAgent", description: "Google ADK sequential multi-agent" },
    { type: "tool", label: "Tool", description: "ADK tool / function" },
    { type: "prompt", label: "Instruction", description: "Agent instruction prompt" },
  ],
  claude_sdk: [
    { type: "agent", label: "Claude Agent", description: "Anthropic Claude async agent" },
    { type: "tool", label: "Tool Block", description: "Claude tool-use block" },
    { type: "prompt", label: "System Prompt", description: "Claude system prompt" },
    { type: "guardrail", label: "Guardrail", description: "Safety guardrail" },
  ],
};

interface NodePaletteProps {
  framework?: string;
}

export function NodePalette({ framework }: NodePaletteProps = {}) {
  const paletteItems =
    framework && FRAMEWORK_PALETTE_MAP[framework]
      ? FRAMEWORK_PALETTE_MAP[framework]
      : PALETTE_ITEMS;
  const onDragStart = (
    event: React.DragEvent<HTMLDivElement>,
    nodeType: CanvasNodeType
  ) => {
    event.dataTransfer.setData("application/reactflow", nodeType);
    event.dataTransfer.effectAllowed = "move";
  };

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="border-b border-border px-3 py-2.5">
        <h3 className="text-xs font-semibold tracking-tight">Node Palette</h3>
        <p className="mt-0.5 text-[10px] text-muted-foreground">
          Drag nodes onto the canvas
        </p>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        <div className="space-y-1.5">
          {paletteItems.map((item, idx) => {
            const style = NODE_STYLES[item.type];
            const IconComp = ICON_MAP[style.icon] ?? Bot;
            return (
              <div
                key={`${item.type}-${idx}`}
                draggable
                onDragStart={(e) => onDragStart(e, item.type)}
                className={cn(
                  "flex cursor-grab items-center gap-2.5 rounded-lg border px-3 py-2 transition-colors active:cursor-grabbing",
                  "border-border hover:border-foreground/20 hover:bg-muted/40",
                  style.bgColor
                )}
              >
                <GripVertical className="size-3 shrink-0 text-muted-foreground/40" />
                <IconComp className={cn("size-4 shrink-0", style.color)} />
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-medium">{item.label}</div>
                  <div className="truncate text-[10px] text-muted-foreground">
                    {item.description}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
