export type LayoutMode = 'force' | 'TB' | 'LR';
export type VisibilityFilter = 'Public' | 'Private';

interface Props {
    nodeTypes: string[];
    edgeTypes: string[];
    hiddenNodeTypes: Set<string>;
    hiddenEdgeTypes: Set<string>;
    hiddenVisibility: Set<VisibilityFilter>;
    onToggleNodeType: (type: string) => void;
    onToggleEdgeType: (type: string) => void;
    onToggleVisibility: (visibility: VisibilityFilter) => void;
    layout: LayoutMode;
    onLayoutChange: (layout: LayoutMode) => void;
    nodeCount: number;
    edgeCount: number;
    publicCount: number;
    privateCount: number;
    onFitView: () => void;
}

function GraphToolbar({
    nodeTypes,
    edgeTypes,
    hiddenNodeTypes,
    hiddenEdgeTypes,
    hiddenVisibility,
    onToggleNodeType,
    onToggleEdgeType,
    onToggleVisibility,
    layout,
    onLayoutChange,
    nodeCount,
    edgeCount,
    publicCount,
    privateCount,
    onFitView,
}: Props) {
    return (
        <div className="graph-toolbar">
            <div className="toolbar-group">
                <span className="toolbar-label">Layout</span>
                <button
                    className={`toolbar-btn ${layout === 'force' ? 'active' : ''}`}
                    onClick={() => onLayoutChange('force')}
                    title="Force-directed clusters (best for social networks)"
                >
                    ✦ Clusters
                </button>
                <button
                    className={`toolbar-btn ${layout === 'TB' ? 'active' : ''}`}
                    onClick={() => onLayoutChange('TB')}
                    title="Top to Bottom hierarchy"
                >
                    ↓ Vertical
                </button>
                <button
                    className={`toolbar-btn ${layout === 'LR' ? 'active' : ''}`}
                    onClick={() => onLayoutChange('LR')}
                    title="Left to Right hierarchy"
                >
                    → Horizontal
                </button>
                <button className="toolbar-btn" onClick={onFitView} title="Fit to viewport">
                    ⊞ Fit
                </button>
            </div>

            <div className="toolbar-group">
                <span className="toolbar-label">Visibility</span>
                <button
                    className={`toolbar-filter ${hiddenVisibility.has('Public') ? 'off' : 'on'}`}
                    onClick={() => onToggleVisibility('Public')}
                    title="Toggle public profiles"
                >
                    Public ({publicCount})
                </button>
                <button
                    className={`toolbar-filter ${hiddenVisibility.has('Private') ? 'off' : 'on'}`}
                    onClick={() => onToggleVisibility('Private')}
                    title="Toggle private profiles"
                >
                    Private ({privateCount})
                </button>
            </div>

            <div className="toolbar-group">
                <span className="toolbar-label">Nodes</span>
                {nodeTypes.map((type) => (
                    <button
                        key={type}
                        className={`toolbar-filter ${hiddenNodeTypes.has(type) ? 'off' : 'on'}`}
                        onClick={() => onToggleNodeType(type)}
                    >
                        {type}
                    </button>
                ))}
            </div>

            <div className="toolbar-group">
                <span className="toolbar-label">Edges</span>
                {edgeTypes.map((type) => (
                    <button
                        key={type}
                        className={`toolbar-filter ${hiddenEdgeTypes.has(type) ? 'off' : 'on'}`}
                        onClick={() => onToggleEdgeType(type)}
                    >
                        {type}
                    </button>
                ))}
            </div>

            <div className="toolbar-stats">
                {nodeCount} nodes · {edgeCount} edges
            </div>
        </div>
    );
}

export default GraphToolbar;
