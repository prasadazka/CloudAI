import Link from "next/link";

export function Header() {
  return (
    <>
      <header className="sticky top-0 z-40 bg-vi-red shadow-card">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link
            href="/"
            className="flex items-center gap-2.5 text-white sm:gap-3"
            aria-label="Cloud Siddhi home"
          >
            {/* Inline brand mark - the same motif as the favicon */}
            <svg
              viewBox="0 0 64 64"
              className="h-7 w-7 sm:h-8 sm:w-8"
              aria-hidden="true"
            >
              <circle cx="32" cy="32" r="30" fill="#FFFFFF" />
              <path
                d="M 22 22 C 22 16, 32 16, 32 22 C 32 28, 22 28, 22 34 C 22 40, 32 40, 32 34"
                fill="none"
                stroke="#ED1C2E"
                strokeWidth="4.5"
                strokeLinecap="round"
              />
              <path
                d="M 32 30 C 32 36, 42 36, 42 42 C 42 48, 32 48, 32 42"
                fill="none"
                stroke="#ED1C2E"
                strokeWidth="4.5"
                strokeLinecap="round"
              />
              <circle cx="48" cy="18" r="3.5" fill="#FFB81C" />
            </svg>
            <span className="text-base font-semibold tracking-tight sm:text-lg">
              Cloud Siddhi
            </span>
            <span className="hidden text-xs font-medium text-white/80 sm:inline">
              · Agentic Orchestration
            </span>
          </Link>

          <nav className="flex items-center gap-4 text-xs text-white/90 sm:gap-6 sm:text-sm">
            <Link href="/" className="hover:text-white">
              New
            </Link>
            <Link href="/workflows" className="hover:text-white">
              Workflows
            </Link>
            <a
              href="http://127.0.0.1:8000/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden hover:text-white sm:inline"
            >
              API Docs
            </a>
          </nav>
        </div>
      </header>
      <div className="h-1 w-full bg-vi-yellow" aria-hidden />
    </>
  );
}
