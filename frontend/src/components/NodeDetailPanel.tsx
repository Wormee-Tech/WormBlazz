import type { GraphNodeDto, GraphEdgeDto } from '../types';
import { resolveProfileUrl } from '../utils/profileUrl';

interface Props {
    node: GraphNodeDto;
    allEdges: GraphEdgeDto[];
    allNodes: GraphNodeDto[];
    onClose: () => void;
}

const IMAGE_KEYS = ['avatarUrl', 'avatar', 'profilePic', 'profilePicUrl', 'imageUrl'];

function isImageValue(key: string, value: string): boolean {
    if (IMAGE_KEYS.includes(key)) return true;
    return /^https?:\/\/\S+\.(png|jpe?g|webp|gif)(\?\S*)?$/i.test(value);
}

function NodeDetailPanel({ node, allEdges, allNodes, onClose }: Props) {
    const nodeMap = new Map(allNodes.map((n) => [n.id, n]));
    const profileUrl = resolveProfileUrl(node.metadata);
    const isDemo = node.metadata?.platform === 'Demo';

    const avatarUrl = IMAGE_KEYS.map((key) => node.metadata?.[key]).find(
        (value): value is string => Boolean(value),
    );

    const incoming = allEdges
        .filter((e) => e.target === node.id)
        .map((e) => {
            const related = nodeMap.get(e.source);
            return {
                ...e,
                nodeName: related?.name ?? e.source,
                profileUrl: resolveProfileUrl(related?.metadata),
            };
        });

    const outgoing = allEdges
        .filter((e) => e.source === node.id)
        .map((e) => {
            const related = nodeMap.get(e.target);
            return {
                ...e,
                nodeName: related?.name ?? e.target,
                profileUrl: resolveProfileUrl(related?.metadata),
            };
        });

    return (
        <div className="node-detail-panel">
            <div className="node-detail-header">
                <h3>
                    {profileUrl ? (
                        <a
                            href={profileUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            title={isDemo ? 'Demo handle → Instagram URL shape (account may not exist)' : 'Open profile'}
                        >
                            {node.name} ↗
                        </a>
                    ) : (
                        node.name
                    )}
                </h3>
                <button className="close-btn" onClick={onClose}>
                    ✕
                </button>
            </div>

            {avatarUrl && (
                <a
                    className="node-avatar-wrap"
                    href={profileUrl ?? avatarUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    title="Open avatar / profile"
                >
                    <img
                        className="node-avatar"
                        src={avatarUrl}
                        alt={node.name}
                        loading="lazy"
                        referrerPolicy="no-referrer"
                        onError={(e) => {
                            (e.currentTarget.parentElement as HTMLElement).style.display = 'none';
                        }}
                    />
                </a>
            )}

            {isDemo && (
                <p className="demo-link-hint">
                    Đây là <strong>Demo</strong> — handle giả, không có trang Instagram thật để mở.
                    Chọn platform <strong>Instagram</strong> rồi Map network để crawl followers thật
                    (link profile lúc đó mới bấm được).
                </p>
            )}

            <div className="node-detail-field">
                <span className="field-label">Type</span>
                <span className="node-type-badge">{node.type}</span>
            </div>

            <div className="node-detail-field">
                <span className="field-label">Visibility</span>
                <span
                    className={`node-type-badge ${
                        node.metadata?.visibility === 'Private' ? 'badge-private' : 'badge-public'
                    }`}
                >
                    {node.metadata?.visibility === 'Private' ? 'Private' : 'Public'}
                </span>
            </div>

            {node.metadata?.filePath && (
                <div className="node-detail-field">
                    <span className="field-label">Handle</span>
                    <span className="field-value mono">{node.metadata.filePath}</span>
                </div>
            )}

            {Object.entries(node.metadata ?? {})
                .filter(([k]) => !['filePath', 'profileUrl', 'visibility', 'isPrivate'].includes(k))
                .filter(([k, v]) => !isImageValue(k, v))
                .map(([key, value]) => (
                    <div key={key} className="node-detail-field">
                        <span className="field-label">{key}</span>
                        <span className="field-value">{value}</span>
                    </div>
                ))}

            <div className="node-detail-section">
                <h4>Incoming ({incoming.length})</h4>
                {incoming.length > 0 ? (
                    <ul className="edge-list">
                        {incoming.map((e, i) => (
                            <li key={i}>
                                <span className="edge-rel">{e.relationship}</span>
                                {e.profileUrl ? (
                                    <a
                                        className="edge-name"
                                        href={e.profileUrl}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                    >
                                        {e.nodeName} ↗
                                    </a>
                                ) : (
                                    <span className="edge-name">{e.nodeName}</span>
                                )}
                            </li>
                        ))}
                    </ul>
                ) : (
                    <p className="no-edges">None</p>
                )}
            </div>

            <div className="node-detail-section">
                <h4>Outgoing ({outgoing.length})</h4>
                {outgoing.length > 0 ? (
                    <ul className="edge-list">
                        {outgoing.map((e, i) => (
                            <li key={i}>
                                <span className="edge-rel">{e.relationship}</span>
                                {e.profileUrl ? (
                                    <a
                                        className="edge-name"
                                        href={e.profileUrl}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                    >
                                        {e.nodeName} ↗
                                    </a>
                                ) : (
                                    <span className="edge-name">{e.nodeName}</span>
                                )}
                            </li>
                        ))}
                    </ul>
                ) : (
                    <p className="no-edges">None</p>
                )}
            </div>
        </div>
    );
}

export default NodeDetailPanel;
