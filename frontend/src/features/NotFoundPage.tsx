import { Link } from "react-router-dom";

import { Button } from "@/components/ui";

export function NotFoundPage() {
  return (
    <div className="grid place-items-center py-24 text-center">
      <div className="animate-fade-up">
        <p className="font-display text-7xl font-semibold text-gradient">404</p>
        <p className="mt-3 text-sm text-muted">
          This route isn&apos;t part of the console.
        </p>
        <Link to="/" className="mt-5 inline-block">
          <Button variant="secondary">← Back to overview</Button>
        </Link>
      </div>
    </div>
  );
}
