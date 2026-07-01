import Link from "next/link";

export default function DashboardPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Dashboard</h1>
      <p className="text-gray-500 mb-8">Welcome to AI Business Automation.</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        <Link
          href="/workflows"
          className="block rounded-lg border border-gray-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow"
        >
          <h2 className="text-lg font-semibold text-gray-800 mb-1">Workflows</h2>
          <p className="text-sm text-gray-500">Build and manage automation workflows.</p>
        </Link>
        <Link
          href="/executions"
          className="block rounded-lg border border-gray-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow"
        >
          <h2 className="text-lg font-semibold text-gray-800 mb-1">Executions</h2>
          <p className="text-sm text-gray-500">Monitor workflow run history.</p>
        </Link>
        <Link
          href="/documents"
          className="block rounded-lg border border-gray-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow"
        >
          <h2 className="text-lg font-semibold text-gray-800 mb-1">Documents</h2>
          <p className="text-sm text-gray-500">Manage uploaded documents.</p>
        </Link>
      </div>
    </div>
  );
}
