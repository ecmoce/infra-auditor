export function Loading() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="animate-spin rounded-full h-8 w-8 border-2 border-[var(--color-accent)] border-t-transparent" />
    </div>
  );
}

export function ErrorDisplay({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <span className="text-4xl mb-3">⚠️</span>
      <p className="text-red-400 font-medium">오류가 발생했습니다</p>
      <p className="text-sm text-[var(--color-text-muted)] mt-1">{message}</p>
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <span className="text-4xl mb-3">📭</span>
      <p className="text-[var(--color-text-muted)]">{message}</p>
    </div>
  );
}
