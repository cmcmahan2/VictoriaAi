'use client';

import { useState, useRef, useEffect } from 'react';

type Message = {
  role: 'user' | 'assistant';
  content: string;
};

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-full bg-[#238636] flex items-center justify-center text-xs font-bold text-white mr-2 shrink-0 mt-0.5">
          C
        </div>
      )}
      <div
        className={`max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
          isUser
            ? 'bg-[#1f6feb] text-white rounded-tr-sm'
            : 'bg-[#161b22] border border-[#30363d] text-[#e6edf3] rounded-tl-sm'
        }`}
      >
        {msg.content}
      </div>
    </div>
  );
}

export default function CoriPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  async function send() {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: Message = { role: 'user', content: text };
    const next = [...messages, userMsg];
    setMessages(next);
    setInput('');
    setError(null);
    setLoading(true);

    try {
      const res = await fetch('/api/cori', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: next.map((m) => ({ role: m.role, content: m.content })),
        }),
      });
      const data = (await res.json()) as { ok: boolean; reply?: string; error?: string };
      if (!data.ok) throw new Error(data.error || 'Request failed');
      setMessages((prev) => [...prev, { role: 'assistant', content: data.reply || '' }]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="flex flex-col h-[calc(100dvh-7.5rem)] md:h-[calc(100dvh-4rem)] max-w-3xl mx-auto p-4">
      <div className="mb-4">
        <h1 className="text-xl font-semibold text-[#e6edf3]">Cori</h1>
        <p className="text-sm text-[#8b949e]">Your domain investing assistant</p>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto min-h-0 pr-1">
        {messages.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center h-full text-center gap-3">
            <div className="w-12 h-12 rounded-full bg-[#238636] flex items-center justify-center text-xl font-bold text-white">
              C
            </div>
            <p className="text-[#8b949e] text-sm max-w-xs">
              Ask me anything about domain investing — strategy, registrar setup, valuations, trends, or how to use Victoria.
            </p>
            <div className="flex flex-wrap gap-2 justify-center mt-2">
              {[
                'How do I get a Namecheap API key?',
                'What makes a domain valuable?',
                'Best TLDs to invest in?',
              ].map((q) => (
                <button
                  key={q}
                  onClick={() => { setInput(q); textareaRef.current?.focus(); }}
                  className="text-xs px-3 py-1.5 bg-[#161b22] border border-[#30363d] rounded-full text-[#8b949e] hover:text-[#e6edf3] hover:border-[#484f58] transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}

        {loading && (
          <div className="flex justify-start mb-3">
            <div className="w-7 h-7 rounded-full bg-[#238636] flex items-center justify-center text-xs font-bold text-white mr-2 shrink-0 mt-0.5">
              C
            </div>
            <div className="px-4 py-2.5 bg-[#161b22] border border-[#30363d] rounded-2xl rounded-tl-sm">
              <div className="flex gap-1 items-center h-4">
                <span className="w-1.5 h-1.5 bg-[#8b949e] rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 bg-[#8b949e] rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 bg-[#8b949e] rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="mb-3 px-4 py-2.5 bg-red-900/20 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="mt-3 flex gap-2 items-end bg-[#161b22] border border-[#30363d] rounded-xl p-2 focus-within:border-[#484f58] transition-colors">
        <textarea
          ref={textareaRef}
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask Cori anything…"
          className="flex-1 bg-transparent text-[#e6edf3] placeholder-[#6e7681] text-sm resize-none outline-none max-h-40 overflow-y-auto py-1 px-2"
          style={{ fieldSizing: 'content' } as React.CSSProperties}
        />
        <button
          onClick={send}
          disabled={!input.trim() || loading}
          className="shrink-0 w-8 h-8 rounded-lg bg-[#238636] hover:bg-[#2ea043] disabled:bg-[#1c2128] disabled:text-[#484f58] text-white flex items-center justify-center transition-colors"
        >
          ↑
        </button>
      </div>
      <p className="text-xs text-[#484f58] text-center mt-2">Enter to send · Shift+Enter for new line</p>
    </div>
  );
}
