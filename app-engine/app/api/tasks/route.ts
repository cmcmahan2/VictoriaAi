/**
 * Async task queue — the "Dispatch" pattern.
 *
 * POST /api/tasks  — submit a background Claude task, get back a task ID
 * GET  /api/tasks?id=<id> — poll for result
 *
 * Usage: brief Claude on a task, get an ID, come back later (or poll from
 * another device) to retrieve the finished output. Mirrors the "dispatch from
 * phone, pick up on desktop" workflow without requiring a persistent queue.
 *
 * Limitation: in-process store — tasks are lost on cold start. For
 * production, replace taskStore with Redis or a DB table.
 */

import { NextRequest, NextResponse } from 'next/server';
import Anthropic from '@anthropic-ai/sdk';

type TaskStatus = 'pending' | 'running' | 'done' | 'error';

type Task = {
  id: string;
  status: TaskStatus;
  label: string;
  createdAt: number;
  completedAt?: number;
  result?: string;
  error?: string;
  usage?: { inputTokens: number; outputTokens: number };
};

// In-process store. Keys expire after 2 hours to prevent unbounded growth.
const taskStore = new Map<string, Task>();
const TTL_MS = 2 * 60 * 60 * 1000;

function purgeExpired() {
  const cutoff = Date.now() - TTL_MS;
  for (const [id, task] of taskStore) {
    if (task.createdAt < cutoff) taskStore.delete(id);
  }
}

function generateId(): string {
  return `task_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

async function runTask(task: Task, systemPrompt: string, userPrompt: string, model: string, apiKey: string) {
  task.status = 'running';

  try {
    const client = new Anthropic({ apiKey });

    const response = await client.messages.create({
      model,
      max_tokens: 4096,
      system: [
        {
          type: 'text',
          text: systemPrompt,
          // Cache the system prompt — large repeated prompts benefit greatly
          cache_control: { type: 'ephemeral' },
        },
      ],
      messages: [{ role: 'user', content: userPrompt }],
    });

    const text = response.content
      .filter((b) => b.type === 'text')
      .map((b) => b.text)
      .join('');

    task.status = 'done';
    task.result = text;
    task.completedAt = Date.now();
    task.usage = {
      inputTokens: response.usage.input_tokens,
      outputTokens: response.usage.output_tokens,
    };
  } catch (err) {
    task.status = 'error';
    task.error = err instanceof Error ? err.message : 'Unknown error';
    task.completedAt = Date.now();
  }
}

// POST /api/tasks
// Body: { label, systemPrompt, userPrompt, model? }
// Returns: { id, status }
export async function POST(req: NextRequest) {
  purgeExpired();

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return NextResponse.json({ error: 'ANTHROPIC_API_KEY not configured' }, { status: 500 });
  }

  let body: {
    label?: string;
    systemPrompt?: string;
    userPrompt?: string;
    model?: string;
  };

  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const { label, systemPrompt, userPrompt, model = 'claude-sonnet-4-6' } = body;

  if (!systemPrompt || !userPrompt) {
    return NextResponse.json({ error: 'systemPrompt and userPrompt are required' }, { status: 400 });
  }

  const id = generateId();
  const task: Task = {
    id,
    status: 'pending',
    label: label ?? 'Unnamed task',
    createdAt: Date.now(),
  };

  taskStore.set(id, task);

  // Fire and forget — do not await. The caller polls GET /api/tasks?id=<id>.
  runTask(task, systemPrompt, userPrompt, model, apiKey);

  return NextResponse.json({ id, status: task.status, label: task.label }, { status: 202 });
}

// GET /api/tasks?id=<id>
// Returns full task state including result when done.
export async function GET(req: NextRequest) {
  const id = req.nextUrl.searchParams.get('id');

  if (!id) {
    // Return all tasks (newest first) — useful for a task dashboard
    const all = [...taskStore.values()]
      .sort((a, b) => b.createdAt - a.createdAt)
      .map(({ id, status, label, createdAt, completedAt, error, usage }) => ({
        id, status, label, createdAt, completedAt, error, usage,
      }));
    return NextResponse.json({ tasks: all });
  }

  const task = taskStore.get(id);
  if (!task) {
    return NextResponse.json({ error: 'Task not found' }, { status: 404 });
  }

  return NextResponse.json(task);
}
