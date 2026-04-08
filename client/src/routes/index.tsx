import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  component: HomePage,
});

function HomePage() {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h2 className="font-bold text-2xl">Welcome</h2>
      <p className="text-neutral-600">
        This is the data platform shell. Replace this route with your real landing page.
      </p>
      <div className="rounded-lg border border-neutral-200 bg-white p-4 text-sm">
        <p className="font-medium">Next steps</p>
        <ol className="mt-2 list-inside list-decimal space-y-1 text-neutral-600">
          <li>
            Run <code className="rounded bg-neutral-100 px-1">just openapi</code> to generate API
            types from the server.
          </li>
          <li>
            Add a query hook in <code className="rounded bg-neutral-100 px-1">src/api/queries/</code>.
          </li>
          <li>Replace this route with the real landing page.</li>
        </ol>
      </div>
    </div>
  );
}
