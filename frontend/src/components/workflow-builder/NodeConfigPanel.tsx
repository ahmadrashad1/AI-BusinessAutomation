"use client";

import { useBuilderStore } from "@/lib/stores/builder.store";

export function NodeConfigPanel() {
  const { selectedNodeId, nodes, updateNodeData } = useBuilderStore();
  const node = nodes.find((n) => n.id === selectedNodeId);

  if (!node) {
    return (
      <aside className="w-64 flex-none border-l bg-gray-50 p-4 text-sm text-gray-400">
        Select a node to configure it.
      </aside>
    );
  }

  const nodeType = node.data.nodeType as string;
  const label = node.data.label as string;
  const config = (node.data.config as Record<string, string>) ?? {};

  function setLabel(value: string) {
    updateNodeData(node!.id, { label: value });
  }

  function setConfig(key: string, value: string) {
    updateNodeData(node!.id, { config: { ...config, [key]: value } });
  }

  return (
    <aside className="w-64 flex-none border-l bg-gray-50 overflow-y-auto">
      <div className="p-4 space-y-4">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500">Node Config</h2>

        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Label</label>
          <input
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>

        <div>
          <p className="text-xs font-medium text-gray-400 mb-2">Type: {nodeType}</p>
        </div>

        {nodeType === "action.http" && (
          <>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">URL</label>
              <input
                type="text"
                value={config.url ?? ""}
                onChange={(e) => setConfig("url", e.target.value)}
                placeholder="https://api.example.com/endpoint"
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Method</label>
              <select
                value={config.method ?? "GET"}
                onChange={(e) => setConfig("method", e.target.value)}
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
              >
                {["GET", "POST", "PUT", "PATCH", "DELETE"].map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </select>
            </div>
          </>
        )}

        {nodeType === "trigger.schedule" && (
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Cron expression</label>
            <input
              type="text"
              value={config.cron ?? ""}
              onChange={(e) => setConfig("cron", e.target.value)}
              placeholder="0 9 * * 1-5"
              className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm font-mono focus:border-blue-500 focus:outline-none"
            />
          </div>
        )}

        {nodeType === "action.email" && (
          <>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">To</label>
              <input
                type="text"
                value={config.to ?? ""}
                onChange={(e) => setConfig("to", e.target.value)}
                placeholder="recipient@example.com"
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Subject</label>
              <input
                type="text"
                value={config.subject ?? ""}
                onChange={(e) => setConfig("subject", e.target.value)}
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
          </>
        )}

        {nodeType === "action.delay" && (
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Delay (seconds)</label>
            <input
              type="number"
              value={config.seconds ?? "0"}
              onChange={(e) => setConfig("seconds", e.target.value)}
              className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
        )}

        {nodeType === "action.condition" && (
          <>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">JSONPath expression</label>
              <input
                type="text"
                value={config.expression ?? ""}
                onChange={(e) => setConfig("expression", e.target.value)}
                placeholder="$.status"
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm font-mono focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Expected value</label>
              <input
                type="text"
                value={config.expected ?? ""}
                onChange={(e) => setConfig("expected", e.target.value)}
                className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
          </>
        )}
      </div>
    </aside>
  );
}
