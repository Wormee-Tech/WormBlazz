import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { resolveProfileUrl } from '../utils/profileUrl';

export interface SocialNodeData extends Record<string, unknown> {
    label: string;
    nodeType: string;
    size: number;
    showLabel: boolean;
    isPrivate?: boolean;
    metadata?: Record<string, string>;
}

const typeColors: Record<string, { fill: string; ring: string; text: string }> = {
    Seed: { fill: '#f43f5e', ring: '#fda4af', text: '#be123c' },
    Verified: { fill: '#10b981', ring: '#6ee7b7', text: '#047857' },
    Creator: { fill: '#8b5cf6', ring: '#c4b5fd', text: '#6d28d9' },
    Brand: { fill: '#f59e0b', ring: '#fcd34d', text: '#b45309' },
    Person: { fill: '#0ea5e9', ring: '#7dd3fc', text: '#0369a1' },
    Hashtag: { fill: '#ec4899', ring: '#f9a8d4', text: '#be185d' },
};

const fallback = { fill: '#64748b', ring: '#cbd5e1', text: '#475569' };

function SocialNode({ data, selected }: NodeProps) {
    const node = data as unknown as SocialNodeData;
    const color = typeColors[node.nodeType] ?? fallback;
    const size = node.size;
    const isPrivate = Boolean(node.isPrivate);
    const isHashtag = node.nodeType === 'Hashtag';

    // Unlabeled leaf dots: minimal DOM — most of a 1k-node graph is these.
    if (!node.showLabel) {
        return (
            <div
                className={`social-node social-node-lite ${isPrivate ? 'is-private' : 'is-public'}`}
                style={{
                    width: size,
                    height: size,
                    background: isPrivate ? '#ffffff' : color.fill,
                    border: isPrivate
                        ? `1.5px dashed ${color.fill}`
                        : `1.5px solid ${color.fill}`,
                    boxShadow: selected ? `0 0 0 2px #312e81` : undefined,
                    opacity: isPrivate ? 0.85 : 1,
                }}
                title={node.label}
            >
                <Handle type="target" position={Position.Top} className="social-handle" />
                <Handle type="source" position={Position.Bottom} className="social-handle" />
            </div>
        );
    }

    const profileUrl = resolveProfileUrl(node.metadata);
    const handle = node.metadata?.username ?? node.label;
    const title = isHashtag
        ? `${node.label} · ${node.metadata?.usageCount ?? 0} recent posts`
        : `${node.label} · ${node.nodeType} · ${isPrivate ? 'Private' : 'Public'}`;

    return (
        <div className="social-node" style={{ width: size, height: size }}>
            <Handle type="target" position={Position.Top} className="social-handle" />
            <div
                className={`social-node-dot ${isPrivate ? 'is-private' : 'is-public'}`}
                title={title}
                style={{
                    width: size,
                    height: size,
                    background: isPrivate ? '#ffffff' : color.fill,
                    border: isPrivate
                        ? `2px dashed ${color.fill}`
                        : `2px solid ${color.fill}`,
                    boxShadow: selected
                        ? `0 0 0 3px #312e81, 0 0 14px ${color.ring}`
                        : isPrivate
                          ? 'none'
                          : `0 0 0 3px ${color.ring}66`,
                    opacity: isPrivate ? 0.9 : 1,
                }}
            />
            {profileUrl && !isPrivate ? (
                <a
                    className="social-node-label nodrag nopan"
                    href={profileUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: color.text }}
                    title={
                        isHashtag
                            ? `Open ${node.label} on ${node.metadata?.platform}`
                            : `Open ${node.metadata?.platform ?? 'profile'} @${handle}`
                    }
                    onClick={(event) => event.stopPropagation()}
                >
                    {node.label}
                </a>
            ) : (
                <span
                    className="social-node-label"
                    style={{ color: isPrivate ? '#64748b' : color.text }}
                >
                    {isPrivate ? `🔒 ${node.label}` : node.label}
                </span>
            )}
            <Handle type="source" position={Position.Bottom} className="social-handle" />
        </div>
    );
}

export default memo(SocialNode);
