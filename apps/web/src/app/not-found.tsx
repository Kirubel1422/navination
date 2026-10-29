import Link from "next/link";

export default function NotFound() {
  return (
    <div className="surface mx-auto max-w-md space-y-4 p-8">
      {/* eslint-disable-next-line @next/next/no-img-element -- pixel-art asset */}
      <img src="/art/sun.png" alt="" width={48} height={48} className="pixel" />
      <h1 className="t-title">Page not found</h1>
      <Link href="/" className="inline-flex h-10 items-center rounded-full bg-gulf px-5 text-sm font-medium text-white">
        NaviNation home
      </Link>
    </div>
  );
}
