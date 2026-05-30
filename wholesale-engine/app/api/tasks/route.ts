import { NextResponse } from 'next/server';
import Anthropic from '@anthropic-ai/sdk';

export const maxDuration = 60;

type TaskStatus = 'pending' | 'running' | 'done' | 'error';
type Task = {
  id: string;
  prompt: string;
  status: TaskStatus;
  result?: string;
  error?: string;
  createdAt: number;
  completedAt?: number;
};

// In-memory task store — resets on cold start. Suitable for dev/demo.
const tasks = new Map<string, Task>();

export async function POST(req: Request) {
  try {
    const apiKey = process.env.ANTHROPIC_API_KEY;
    if (!apiKey) {
      return NextResponse.json({ ok: false, error: 'ANTHROPIC_API_KEY not set' }, { status: 503 });
    }

    const body = (await req.json().catch(() => ({}))) as { prompt?: string };
    if (!body.prompt) {
      return NextResponse.json({ ok: false, error: 'prompt required' }, { status: 400 });
    }

    const id = `task-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const task: Task = { id, prompt: body.prompt, status: 'pending', createdAt: Date.now() };
    tasks.set(id, task);

    // Run async — do not await
    void (async () => {
      task.status = 'running';
      try {
        const client = new Anthropic({ apiKey });
        const response = await client.messages.create({
          model: 'claude-sonnet-4-6',
          max_tokens: 2048,
          messages: [{ role: 'user', content: task.prompt }],
        });
        task.result = response.content.filter(b => b.type === 'text').map(b => b.text).join('');
        task.status = 'done';
      } catch (err) {
        task.error = err instanceof Error ? err.message : 'Unknown error';
        task.status = 'error';
      }
      task.completedAt = Date.now();
    })();

    return NextResponse.json({ ok: true, taskId: id });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const id = searchParams.get('id');

  if (!id) {
    return NextResponse.json({ ok: true, tasks: [...tasks.values()].slice(-20) });
  }

  const task = tasks.get(id);
  if (!task) {
    return NextResponse.json({ ok: false, error: 'Task not found' }, { status: 404 });
  }
  return NextResponse.json({ ok: true, task });
}
