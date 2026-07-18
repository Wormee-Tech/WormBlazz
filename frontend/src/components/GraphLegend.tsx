const nodeTypes = [
    { label: 'Seed', icon: '◎', color: '#f43f5e' },
    { label: 'Person', icon: '○', color: '#0ea5e9' },
    { label: 'Creator', icon: '◇', color: '#8b5cf6' },
    { label: 'Brand', icon: '▣', color: '#f59e0b' },
    { label: 'Verified', icon: '✓', color: '#10b981' },
    { label: 'Hashtag', icon: '#', color: '#ec4899' },
];

const visibilityTypes = [
    { label: 'Public', icon: '●', color: '#0ea5e9', note: 'filled' },
    { label: 'Private', icon: '◌', color: '#64748b', note: 'dashed' },
];

const edgeTypes = [
    { label: 'Follows', color: '#22d3ee', dashed: false },
    { label: 'Mentions', color: '#f59e0b', dashed: false },
    { label: 'Related', color: '#818cf8', dashed: false },
    { label: 'CoMention', color: '#f87171', dashed: true },
    { label: 'SharedHashtag', color: '#a3e635', dashed: true },
    { label: 'UsesHashtag', color: '#84cc16', dashed: false },
];

function GraphLegend() {
    return (
        <div className="graph-legend">
            <div className="legend-section">
                <span className="legend-title">Visibility</span>
                <div className="legend-items">
                    {visibilityTypes.map((t) => (
                        <span key={t.label} className="legend-item">
                            <span
                                className="legend-dot"
                                style={{
                                    background: t.label === 'Private' ? 'transparent' : t.color,
                                    border: `2px ${t.label === 'Private' ? 'dashed' : 'solid'} ${t.color}`,
                                }}
                            />
                            {t.icon} {t.label}
                        </span>
                    ))}
                </div>
            </div>
            <div className="legend-section">
                <span className="legend-title">Nodes</span>
                <div className="legend-items">
                    {nodeTypes.map((t) => (
                        <span key={t.label} className="legend-item">
                            <span
                                className="legend-dot"
                                style={{ background: t.color }}
                            />
                            {t.icon} {t.label}
                        </span>
                    ))}
                </div>
            </div>
            <div className="legend-section">
                <span className="legend-title">Edges</span>
                <div className="legend-items">
                    {edgeTypes.map((e) => (
                        <span key={e.label} className="legend-item">
                            <span
                                className="legend-line"
                                style={{
                                    background: e.color,
                                    borderStyle: e.dashed ? 'dashed' : 'solid',
                                }}
                            />
                            {e.label}
                        </span>
                    ))}
                </div>
            </div>
        </div>
    );
}

export default GraphLegend;
