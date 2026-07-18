import { Handle, Position, type NodeProps } from '@xyflow/react';

export interface GraphNodeData extends Record<string, unknown> {
    label: string;
    nodeType: string;
    filePath?: string;
    metadata?: Record<string, string>;
}

const typeConfig: Record<string, { icon: string; bg: string; border: string; accent: string }> = {
    Repository: { icon: '📦', bg: '#eef2ff', border: '#6366f1', accent: '#4f46e5' },
    Folder: { icon: '📁', bg: '#f8fafc', border: '#94a3b8', accent: '#64748b' },
    File: { icon: '📄', bg: '#eff6ff', border: '#3b82f6', accent: '#2563eb' },
    Namespace: { icon: '🏷️', bg: '#fffbeb', border: '#f59e0b', accent: '#d97706' },
    Class: { icon: '🔷', bg: '#f5f3ff', border: '#8b5cf6', accent: '#7c3aed' },
    Interface: { icon: '🔶', bg: '#eef2ff', border: '#6366f1', accent: '#4f46e5' },
    Function: { icon: '⚡', bg: '#ecfdf5', border: '#10b981', accent: '#059669' },
    Module: { icon: '📦', bg: '#f0f9ff', border: '#0ea5e9', accent: '#0284c7' },
    Seed: { icon: '◎', bg: '#fff1f2', border: '#f43f5e', accent: '#e11d48' },
    Person: { icon: '○', bg: '#f0f9ff', border: '#0ea5e9', accent: '#0284c7' },
    Creator: { icon: '◇', bg: '#f5f3ff', border: '#8b5cf6', accent: '#7c3aed' },
    Brand: { icon: '▣', bg: '#fffbeb', border: '#f59e0b', accent: '#d97706' },
    Verified: { icon: '✓', bg: '#ecfdf5', border: '#10b981', accent: '#059669' },
    Hashtag: { icon: '#', bg: '#fdf2f8', border: '#ec4899', accent: '#db2777' },
};

const defaultConfig = { icon: '●', bg: '#ffffff', border: '#cbd5e1', accent: '#64748b' };

function GraphNodeComponent({ data }: NodeProps) {
    const nodeData = data as unknown as GraphNodeData;
    const cfg = typeConfig[nodeData.nodeType] ?? defaultConfig;

    return (
        <div
            className="graph-node"
            style={{
                background: cfg.bg,
                borderColor: cfg.border,
            }}
        >
            <Handle type="target" position={Position.Top} className="graph-handle" />
            <div className="graph-node-header">
                <span className="graph-node-icon">{cfg.icon}</span>
                <span className="graph-node-type" style={{ color: cfg.accent }}>
                    {nodeData.nodeType}
                </span>
            </div>
            <div className="graph-node-label" title={nodeData.label}>
                {nodeData.label}
            </div>
            {nodeData.filePath && (
                <div className="graph-node-path" title={nodeData.filePath}>
                    {truncatePath(nodeData.filePath)}
                </div>
            )}
            <Handle type="source" position={Position.Bottom} className="graph-handle" />
        </div>
    );
}

function truncatePath(path: string): string {
    if (path.length <= 35) return path;
    const parts = path.split('/');
    if (parts.length <= 2) return path;
    return `…/${parts.slice(-2).join('/')}`;
}

export default GraphNodeComponent;
