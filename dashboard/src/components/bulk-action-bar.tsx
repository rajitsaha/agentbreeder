import { useState } from "react";
import { X, Tag, Download, Trash2, Loader2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { exportAsJson } from "@/lib/export";

interface BulkActionBarProps {
  selectedCount: number;
  entityName: string;
  selectedItems: Record<string, unknown>[];
  onClearSelection: () => void;
  onDelete?: (ids: string[]) => void;
}

/**
 * Floating action bar shown at bottom-center when items are selected on list pages.
 * Provides bulk Add Tags, Export, and Delete actions.
 */
export function BulkActionBar({
  selectedCount,
  entityName,
  selectedItems,
  onClearSelection,
  onDelete,
}: BulkActionBarProps) {
  const [showTagDialog, setShowTagDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [tagInput, setTagInput] = useState("");
  const [tagsToAdd, setTagsToAdd] = useState<string[]>([]);

  if (selectedCount === 0) return null;

  const plural = selectedCount === 1 ? entityName : `${entityName}s`;

  const handleAddTag = () => {
    const tag = tagInput.trim().toLowerCase();
    if (tag && !tagsToAdd.includes(tag)) {
      setTagsToAdd([...tagsToAdd, tag]);
    }
    setTagInput("");
  };

  const handleRemoveTag = (tag: string) => {
    setTagsToAdd(tagsToAdd.filter((t) => t !== tag));
  };

  const handleApplyTags = () => {
    // Mock: in a real implementation this would call an API
    setShowTagDialog(false);
    setTagsToAdd([]);
    setTagInput("");
  };

  const handleExport = () => {
    exportAsJson(selectedItems, `${entityName}s-selection`);
  };

  const handleDelete = () => {
    if (onDelete) {
      const ids = selectedItems.map((item) => item.id as string);
      onDelete(ids);
    }
    setShowDeleteDialog(false);
    onClearSelection();
  };

  return (
    <>
      {/* Floating bar */}
      <div
        className={cn(
          "fixed bottom-6 left-1/2 z-50 -translate-x-1/2",
          "animate-in slide-in-from-bottom-4 fade-in duration-200"
        )}
      >
        <div className="flex items-center gap-3 rounded-xl border border-border bg-background px-4 py-2.5 shadow-lg shadow-black/10 dark:shadow-black/30">
          <span className="text-xs font-medium">
            {selectedCount} {plural} selected
          </span>

          <div className="h-4 w-px bg-border" />

          <Button
            variant="outline"
            size="xs"
            onClick={() => setShowTagDialog(true)}
          >
            <Tag className="size-3" data-icon="inline-start" />
            Add Tags
          </Button>

          <Button
            variant="outline"
            size="xs"
            onClick={handleExport}
          >
            <Download className="size-3" data-icon="inline-start" />
            Export
          </Button>

          <Button
            variant="destructive"
            size="xs"
            onClick={() => setShowDeleteDialog(true)}
          >
            <Trash2 className="size-3" data-icon="inline-start" />
            Delete
          </Button>

          <div className="h-4 w-px bg-border" />

          <button
            onClick={onClearSelection}
            className="flex size-5 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <X className="size-3" />
          </button>
        </div>
      </div>

      {/* Add Tags Dialog */}
      <Dialog open={showTagDialog} onOpenChange={setShowTagDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Add Tags</DialogTitle>
            <DialogDescription>
              Add tags to {selectedCount} selected {plural}.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-3">
            <div className="flex items-center gap-1.5">
              <Input
                placeholder="Type a tag..."
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleAddTag();
                  }
                }}
                className="h-8 text-xs"
              />
              <Button
                variant="outline"
                size="sm"
                className="h-8 px-2"
                onClick={handleAddTag}
                disabled={!tagInput.trim()}
              >
                <Plus className="size-3" />
              </Button>
            </div>
            {tagsToAdd.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {tagsToAdd.map((tag) => (
                  <Badge key={tag} variant="outline" className="gap-1 text-[10px]">
                    <Tag className="size-2.5" />
                    {tag}
                    <button
                      onClick={() => handleRemoveTag(tag)}
                      className="ml-0.5 rounded-full hover:bg-muted"
                    >
                      <X className="size-2.5" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
          </div>

          <DialogFooter>
            <DialogClose render={<Button variant="outline" size="sm" />}>
              Cancel
            </DialogClose>
            <Button
              size="sm"
              onClick={handleApplyTags}
              disabled={tagsToAdd.length === 0}
            >
              Apply Tags
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Delete {selectedCount} {plural}?</DialogTitle>
            <DialogDescription>
              This action cannot be undone. The selected {plural} will be
              permanently removed from the registry.
            </DialogDescription>
          </DialogHeader>

          <DialogFooter>
            <DialogClose render={<Button variant="outline" size="sm" />}>
              Cancel
            </DialogClose>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDelete}
            >
              <Trash2 className="size-3" data-icon="inline-start" />
              Delete {selectedCount} {plural}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
