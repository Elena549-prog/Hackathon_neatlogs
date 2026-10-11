import type { ReactNode } from "react";

export function Panel({ title, right, children, className = "" }: { title: string; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`flex min-h-0 flex-col rounded-md border border-line bg-panel ${className}`}>
      <header className="flex items-center justify-between border-b border-line px-4 py-2">
        <h2 className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">{title}</h2>
        {right}
      </header>
      <div className="min-h-0 flex-1 p-4">{children}</div>
    </section>
  );
}
