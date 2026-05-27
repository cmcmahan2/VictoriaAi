"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import Link from "next/link";
import Image from "next/image";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

interface Album {
  id: string;
  title: string;
  artistName: string;
  coverUrl?: string | null;
  releaseYear?: number;
}

interface Entry {
  id: string;
  albumId: string;
  rank: number;
  note?: string | null;
  album?: Album;
}

interface ListData {
  id: string;
  title: string;
  description?: string | null;
  isPublic: boolean;
  userId: string;
  user: { username: string; avatarUrl?: string | null };
  entries: Entry[];
}

function SortableEntry({
  entry,
  index,
  isOwner,
  onRemove,
}: {
  entry: Entry;
  index: number;
  isOwner: boolean;
  onRemove: (id: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: entry.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} className="flex items-center gap-3 py-2.5 border-b border-[rgba(255,255,255,0.05)] group">
      <span className="text-[#555] text-sm w-6 text-right shrink-0">{index + 1}</span>
      {isOwner && (
        <button {...attributes} {...listeners} className="text-[#333] hover:text-[#555] cursor-grab active:cursor-grabbing shrink-0">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <circle cx="9" cy="5" r="1.5" /><circle cx="15" cy="5" r="1.5" />
            <circle cx="9" cy="12" r="1.5" /><circle cx="15" cy="12" r="1.5" />
            <circle cx="9" cy="19" r="1.5" /><circle cx="15" cy="19" r="1.5" />
          </svg>
        </button>
      )}
      <Link href={`/album/${entry.albumId}`} className="shrink-0">
        {entry.album?.coverUrl ? (
          <Image src={entry.album.coverUrl} alt={entry.album?.title ?? ""} width={48} height={48} className="rounded object-cover" />
        ) : (
          <div className="w-12 h-12 bg-[#1a1a1a] rounded flex items-center justify-center text-[#444]">♪</div>
        )}
      </Link>
      <div className="flex-1 min-w-0">
        <Link href={`/album/${entry.albumId}`} className="text-[#F5F2EB] text-sm font-medium hover:text-[#E8B84B] transition-colors block truncate">
          {entry.album?.title ?? entry.albumId}
        </Link>
        <p className="text-[#555] text-xs truncate">{entry.album?.artistName}</p>
        {entry.note && <p className="text-[#888] text-xs mt-0.5 italic">{entry.note}</p>}
      </div>
      {isOwner && (
        <button onClick={() => onRemove(entry.id)} className="opacity-0 group-hover:opacity-100 text-[#555] hover:text-red-400 transition-all shrink-0">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      )}
    </div>
  );
}

export default function ListPage() {
  const { id } = useParams<{ id: string }>();
  const { data: session } = useSession();
  const router = useRouter();
  const [list, setList] = useState<ListData | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const me = (session?.user as { id?: string })?.id;
  const isOwner = !!me && list?.userId === me;

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const fetchList = useCallback(async () => {
    const res = await fetch(`/api/lists/${id}`);
    if (!res.ok) { router.push("/"); return; }
    const data = await res.json();
    setList(data);
    setEntries(data.entries ?? []);
    setLoading(false);
  }, [id, router]);

  useEffect(() => { fetchList(); }, [fetchList]);

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const oldIndex = entries.findIndex((e) => e.id === active.id);
      const newIndex = entries.findIndex((e) => e.id === over.id);
      const reordered = arrayMove(entries, oldIndex, newIndex).map((e, i) => ({ ...e, rank: i + 1 }));
      setEntries(reordered);
      saveEntries(reordered);
    }
  }

  async function saveEntries(updated: Entry[]) {
    setSaving(true);
    await fetch(`/api/lists/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        entries: updated.map((e) => ({ albumId: e.albumId, rank: e.rank, note: e.note })),
      }),
    });
    setSaving(false);
  }

  function handleRemove(entryId: string) {
    const updated = entries.filter((e) => e.id !== entryId).map((e, i) => ({ ...e, rank: i + 1 }));
    setEntries(updated);
    saveEntries(updated);
  }

  async function handleDelete() {
    if (!confirm("Delete this list?")) return;
    await fetch(`/api/lists/${id}`, { method: "DELETE" });
    router.push(`/user/${(session?.user as { name?: string })?.name}/lists`);
  }

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-10 animate-pulse">
        <div className="h-8 bg-[#1a1a1a] rounded w-48 mb-2" />
        <div className="h-4 bg-[#1a1a1a] rounded w-32 mb-8" />
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex gap-3 py-2.5 border-b border-[rgba(255,255,255,0.05)]">
            <div className="w-6 h-4 bg-[#1a1a1a] rounded" />
            <div className="w-12 h-12 bg-[#1a1a1a] rounded" />
            <div className="flex-1">
              <div className="h-4 bg-[#1a1a1a] rounded w-40 mb-1" />
              <div className="h-3 bg-[#1a1a1a] rounded w-24" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!list) return null;

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <div className="flex items-start justify-between gap-4 mb-8">
        <div>
          <Link href={`/user/${list.user.username}/lists`} className="text-[#888] text-sm hover:text-[#F5F2EB] transition-colors">
            ← {list.user.username}&apos;s lists
          </Link>
          <h1 className="text-3xl font-bold text-[#F5F2EB] mt-2" style={{ fontFamily: "Playfair Display, serif" }}>
            {list.title}
          </h1>
          {list.description && <p className="text-[#888] mt-1 text-sm">{list.description}</p>}
          <p className="text-[#555] text-xs mt-2">{entries.length} album{entries.length !== 1 ? "s" : ""} {saving && "· saving..."}</p>
        </div>
        {isOwner && (
          <div className="flex gap-2 shrink-0">
            <Link
              href={`/search?addToList=${id}`}
              className="text-xs border border-[rgba(255,255,255,0.15)] text-[#F5F2EB] px-3 py-1.5 rounded-full hover:border-[rgba(255,255,255,0.3)] transition-colors"
            >
              + Add
            </Link>
            <button
              onClick={handleDelete}
              className="text-xs text-[#888] hover:text-red-400 transition-colors"
            >
              Delete
            </button>
          </div>
        )}
      </div>

      {entries.length === 0 ? (
        <div className="text-center py-16 text-[#888]">
          <p>No albums yet.</p>
          {isOwner && (
            <Link href={`/search?addToList=${id}`} className="text-[#E8B84B] hover:underline mt-2 inline-block">
              Search for albums to add
            </Link>
          )}
        </div>
      ) : isOwner ? (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={entries.map((e) => e.id)} strategy={verticalListSortingStrategy}>
            {entries.map((entry, index) => (
              <SortableEntry key={entry.id} entry={entry} index={index} isOwner={isOwner} onRemove={handleRemove} />
            ))}
          </SortableContext>
        </DndContext>
      ) : (
        <div>
          {entries.map((entry, index) => (
            <div key={entry.id} className="flex items-center gap-3 py-2.5 border-b border-[rgba(255,255,255,0.05)]">
              <span className="text-[#555] text-sm w-6 text-right shrink-0">{index + 1}</span>
              <Link href={`/album/${entry.albumId}`} className="shrink-0">
                {entry.album?.coverUrl ? (
                  <Image src={entry.album.coverUrl} alt={entry.album?.title ?? ""} width={48} height={48} className="rounded object-cover" />
                ) : (
                  <div className="w-12 h-12 bg-[#1a1a1a] rounded flex items-center justify-center text-[#444]">♪</div>
                )}
              </Link>
              <div className="flex-1 min-w-0">
                <Link href={`/album/${entry.albumId}`} className="text-[#F5F2EB] text-sm font-medium hover:text-[#E8B84B] transition-colors block truncate">
                  {entry.album?.title ?? entry.albumId}
                </Link>
                <p className="text-[#555] text-xs truncate">{entry.album?.artistName}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
