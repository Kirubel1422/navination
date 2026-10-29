/** NaviNation's mark: a route through a roundel with a saffron stop. Also Navi's avatar. */
export function Mark({ className = "size-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className={`shrink-0 ${className}`}>
      <circle cx="16" cy="16" r="15" fill="#0e6170" />
      <path d="M4 22c6 0 8-9 14-9s8-4 11-4" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" />
      <circle cx="18" cy="13" r="3.6" fill="#e9a23b" stroke="#fff" strokeWidth="1.6" />
    </svg>
  );
}
