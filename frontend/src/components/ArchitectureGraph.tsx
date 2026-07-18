import { useCallback, useEffect, useMemo, useState, type MouseEvent } from 'react';
import {
    ReactFlow,
    Background,
    Controls,
    MiniMap,
    useReactFlow,
    ReactFlowProvider,
    type Node,
    type Edge,
    type NodeMouseHandler,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { ArchitectureResponse, GraphNodeDto, GraphStatsResponse } from '../types';
import { layoutGraph, forceLayout } from '../utils/layoutGraph';
import GraphNodeComponent, { type GraphNodeData } from './GraphNode';
import SocialNode, { type SocialNodeData } from './SocialNode';
import SocialCanvasLayer, {
    hitTestCanvasDot,
    type CanvasDot,
    type CanvasSpoke,
} from './SocialCanvasLayer';
import GraphToolbar, { type LayoutMode, type VisibilityFilter } from './GraphToolbar';
import GraphLegend from './GraphLegend';
import NodeDetailPanel from './NodeDetailPanel';

interface Props {
    architecture: ArchitectureResponse;
    stats?: GraphStatsResponse | null;
}

const edgeColors: Record<string, string> = {
    Follows: '#94a3b8',
    FollowedBy: '#94a3b8',
    Mentions: '#d97706',
    Related: '#818cf8',
    CoMention: '#f87171',
    SharedHashtag: '#84cc16',
    UsesHashtag: '#65a30d',
    Imports: '#0ea5e9',
    Contains: '#94a3b8',
    Inherits: '#f59e0b',
    Implements: '#8b5cf6',
    Calls: '#f87171',
};

const typeFill: Record<string, string> = {
    Seed: '#f43f5e',
    Verified: '#10b981',
    Creator: '#8b5cf6',
    Brand: '#f59e0b',
    Person: '#0ea5e9',
    Hashtag: '#ec4899',
};

const nodeTypes = { graphNode: GraphNodeComponent, socialNode: SocialNode };

const miniMapColors: Record<string, string> = {
    Seed: '#f43f5e',
    Person: '#0ea5e9',
    Creator: '#8b5cf6',
    Brand: '#f59e0b',
    Verified: '#10b981',
    Hashtag: '#ec4899',
};

const SOCIAL_TYPES = new Set(['Seed', 'Person', 'Creator', 'Brand', 'Verified', 'Hashtag']);
const MIN_DOT = 12;
const MAX_DOT = 56;
const MAX_LABELS = 14;
/** Above this, leaf Person nodes are painted on canvas instead of React Flow DOM. */
const CANVAS_MODE_THRESHOLD = 120;
const MAX_RF_EDGES = 80;
const MAX_CANVAS_SPOKES = 800;

function miniMapNodeColor(node: Node): string {
    const data = node.data as { nodeType?: string; isPrivate?: boolean };
    if (data.isPrivate) return '#94a3b8';
    return miniMapColors[data.nodeType ?? ''] ?? '#94a3b8';
}

function ArchitectureGraphInner({ architecture, stats }: Props) {
    const isSocial = useMemo(
        () => architecture.nodes.some((n) => SOCIAL_TYPES.has(n.type)),
        [architecture.nodes],
    );

    const [layout, setLayout] = useState<LayoutMode>(isSocial ? 'force' : 'TB');
    const [hiddenNodeTypes, setHiddenNodeTypes] = useState<Set<string>>(new Set());
    const [hiddenEdgeTypes, setHiddenEdgeTypes] = useState<Set<string>>(new Set());
    const [hiddenVisibility, setHiddenVisibility] = useState<Set<VisibilityFilter>>(new Set());
    const [selectedNode, setSelectedNode] = useState<GraphNodeDto | null>(null);
    const { fitView, screenToFlowPosition, getZoom } = useReactFlow();

    const useCanvasMode = isSocial && layout === 'force' && architecture.nodes.length >= CANVAS_MODE_THRESHOLD;

    const availableNodeTypes = useMemo(
        () => [...new Set(architecture.nodes.map((n) => n.type))].sort(),
        [architecture.nodes],
    );
    const availableEdgeTypes = useMemo(
        () => [...new Set(architecture.edges.map((e) => e.relationship))].sort(),
        [architecture.edges],
    );

    const visibilityCounts = useMemo(() => {
        let publicCount = 0;
        let privateCount = 0;
        for (const node of architecture.nodes) {
            if (node.type === 'Hashtag') continue;
            if (node.metadata?.visibility === 'Private' || node.metadata?.isPrivate === 'true') {
                privateCount += 1;
            } else {
                publicCount += 1;
            }
        }
        return { publicCount, privateCount };
    }, [architecture.nodes]);

    const degreeById = useMemo(() => {
        const degree = new Map<string, number>();
        for (const edge of architecture.edges) {
            degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
            degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
        }
        return degree;
    }, [architecture.edges]);

    const backendById = useMemo(
        () => new Map(architecture.nodes.map((n) => [n.id, n])),
        [architecture.nodes],
    );

    const labelIds = useMemo(() => {
        const ranked = architecture.nodes
            .map((n) => ({
                id: n.id,
                type: n.type,
                degree: degreeById.get(n.id) ?? 0,
            }))
            .sort((a, b) => {
                if (a.type === 'Seed' && b.type !== 'Seed') return -1;
                if (b.type === 'Seed' && a.type !== 'Seed') return 1;
                return b.degree - a.degree;
            });

        const ids = new Set<string>();
        for (const item of ranked) {
            if (ids.size >= MAX_LABELS) break;
            if (item.type === 'Seed' || item.type === 'Hashtag' || item.degree > 1) {
                ids.add(item.id);
            }
        }
        return ids;
    }, [architecture.nodes, degreeById]);

    /** Nodes that stay as real React Flow components (clickable, labeled). */
    const interactiveIds = useMemo(() => {
        if (!useCanvasMode) {
            return new Set(architecture.nodes.map((n) => n.id));
        }
        const ids = new Set<string>();
        for (const n of architecture.nodes) {
            if (
                n.type === 'Seed' ||
                n.type === 'Hashtag' ||
                n.type === 'Verified' ||
                n.type === 'Creator' ||
                n.type === 'Brand' ||
                labelIds.has(n.id)
            ) {
                ids.add(n.id);
            }
        }
        return ids;
    }, [architecture.nodes, labelIds, useCanvasMode]);

    const baseGraph = useMemo(() => {
        const useForce = layout === 'force';
        const maxDegree = Math.max(1, ...degreeById.values());
        const sizeById = new Map<string, number>();

        const layoutNodes: Node[] = architecture.nodes.map((n) => {
            const degree = degreeById.get(n.id) ?? 0;
            if (useForce || isSocial) {
                const scale = Math.sqrt(degree / maxDegree);
                const size = Math.round(MIN_DOT + (MAX_DOT - MIN_DOT) * scale);
                sizeById.set(n.id, size);
                const isPrivate =
                    n.metadata?.visibility === 'Private' || n.metadata?.isPrivate === 'true';
                return {
                    id: n.id,
                    type: 'socialNode',
                    data: {
                        label: n.name,
                        nodeType: n.type,
                        size,
                        showLabel: labelIds.has(n.id),
                        isPrivate,
                        metadata: n.metadata,
                    } satisfies SocialNodeData,
                    position: { x: 0, y: 0 },
                    width: size,
                    height: size,
                    draggable: false,
                    connectable: false,
                    focusable: false,
                };
            }
            return {
                id: n.id,
                type: 'graphNode',
                data: {
                    label: n.name,
                    nodeType: n.type,
                    filePath: n.metadata?.filePath ?? n.metadata?.username,
                    metadata: n.metadata,
                } satisfies GraphNodeData,
                position: { x: 0, y: 0 },
            };
        });

        const seedId = architecture.nodes.find((n) => n.type === 'Seed')?.id;
        const rfEdgesForLayout: Edge[] = architecture.edges.slice(0, 2000).map((e, i) => ({
            id: `layout-e-${i}`,
            source: e.source,
            target: e.target,
        }));

        const laidOut = useForce
            ? forceLayout(layoutNodes, rfEdgesForLayout, { sizeById, centerId: seedId })
            : layoutGraph(layoutNodes, rfEdgesForLayout, { direction: layout });

        const positionById = new Map(
            laidOut.map((n) => {
                const size = sizeById.get(n.id) ?? 24;
                // Convert top-left RF position → center for canvas drawing.
                return [
                    n.id,
                    {
                        left: n.position.x,
                        top: n.position.y,
                        cx: n.position.x + size / 2,
                        cy: n.position.y + size / 2,
                        size,
                    },
                ];
            }),
        );

        return { laidOut, positionById, seedId, sizeById };
    }, [architecture.nodes, architecture.edges, degreeById, labelIds, layout, isSocial]);

    const { nodes, edges, canvasDots, canvasSpokes, visibleCount, edgeCount } = useMemo(() => {
        const nodeVisible = (n: GraphNodeDto) => {
            if (hiddenNodeTypes.has(n.type)) return false;
            if (n.type === 'Hashtag') return true;
            const visibility =
                (n.metadata?.visibility as VisibilityFilter | undefined) ??
                (n.metadata?.isPrivate === 'true' ? 'Private' : 'Public');
            return !hiddenVisibility.has(visibility);
        };

        const visibleIds = new Set(architecture.nodes.filter(nodeVisible).map((n) => n.id));

        const rfNodes = baseGraph.laidOut
            .filter((node) => interactiveIds.has(node.id))
            .map((node) => ({
                ...node,
                hidden: !visibleIds.has(node.id),
            }));

        // RF edges: only between interactive nodes (tiny set).
        const rfEdges: Edge[] = [];
        if (!useCanvasMode) {
            const ranked = architecture.edges.filter(
                (e) =>
                    visibleIds.has(e.source) &&
                    visibleIds.has(e.target) &&
                    !hiddenEdgeTypes.has(e.relationship),
            );
            for (let i = 0; i < Math.min(ranked.length, 450); i += 1) {
                const e = ranked[i];
                const color = edgeColors[e.relationship] ?? '#cbd5e1';
                rfEdges.push({
                    id: `e-${e.source}-${e.target}-${i}`,
                    source: e.source,
                    target: e.target,
                    type: 'straight',
                    animated: false,
                    focusable: false,
                    interactionWidth: 0,
                    style: {
                        stroke: color,
                        strokeWidth: layout === 'force' ? 0.55 : 1.3,
                        opacity: layout === 'force' ? 0.35 : 0.9,
                    },
                    data: { relationship: e.relationship },
                });
            }
        } else {
            let i = 0;
            for (const e of architecture.edges) {
                if (i >= MAX_RF_EDGES) break;
                if (!interactiveIds.has(e.source) || !interactiveIds.has(e.target)) continue;
                if (!visibleIds.has(e.source) || !visibleIds.has(e.target)) continue;
                if (hiddenEdgeTypes.has(e.relationship)) continue;
                const color = edgeColors[e.relationship] ?? '#cbd5e1';
                rfEdges.push({
                    id: `e-${e.source}-${e.target}-${i}`,
                    source: e.source,
                    target: e.target,
                    type: 'straight',
                    animated: false,
                    focusable: false,
                    interactionWidth: 0,
                    style: { stroke: color, strokeWidth: 1.1, opacity: 0.55 },
                    data: { relationship: e.relationship },
                });
                i += 1;
            }
        }

        const dots: CanvasDot[] = [];
        const spokes: CanvasSpoke[] = [];
        if (useCanvasMode) {
            const seedPos = baseGraph.seedId
                ? baseGraph.positionById.get(baseGraph.seedId)
                : undefined;

            for (const n of architecture.nodes) {
                if (interactiveIds.has(n.id) || !visibleIds.has(n.id)) continue;
                if (hiddenNodeTypes.has(n.type)) continue;
                const pos = baseGraph.positionById.get(n.id);
                if (!pos) continue;
                const isPrivate =
                    n.metadata?.visibility === 'Private' || n.metadata?.isPrivate === 'true';
                dots.push({
                    id: n.id,
                    x: pos.cx,
                    y: pos.cy,
                    r: Math.max(2.5, Math.min(5, pos.size / 4)),
                    color: typeFill[n.type] ?? '#0ea5e9',
                    isPrivate,
                });
            }

            // Spokes: leaf → seed (canvas can draw hundreds cheaply).
            let spokeCount = 0;
            if (seedPos && !hiddenEdgeTypes.has('Follows') && !hiddenEdgeTypes.has('FollowedBy')) {
                for (const e of architecture.edges) {
                    if (spokeCount >= MAX_CANVAS_SPOKES) break;
                    const other =
                        e.source === baseGraph.seedId
                            ? e.target
                            : e.target === baseGraph.seedId
                              ? e.source
                              : null;
                    if (!other || interactiveIds.has(other) || !visibleIds.has(other)) continue;
                    const leaf = baseGraph.positionById.get(other);
                    if (!leaf) continue;
                    spokes.push({
                        x1: seedPos.cx,
                        y1: seedPos.cy,
                        x2: leaf.cx,
                        y2: leaf.cy,
                    });
                    spokeCount += 1;
                }
            }
        }

        return {
            nodes: rfNodes,
            edges: rfEdges,
            canvasDots: dots,
            canvasSpokes: spokes,
            visibleCount: visibleIds.size,
            edgeCount: useCanvasMode ? spokes.length + rfEdges.length : rfEdges.length,
        };
    }, [
        architecture.nodes,
        architecture.edges,
        baseGraph,
        interactiveIds,
        useCanvasMode,
        layout,
        hiddenNodeTypes,
        hiddenEdgeTypes,
        hiddenVisibility,
    ]);

    useEffect(() => {
        const id = requestAnimationFrame(() => {
            fitView({ padding: 0.12, duration: 180 });
        });
        return () => cancelAnimationFrame(id);
    }, [baseGraph, fitView]);

    const handleToggleNodeType = useCallback((type: string) => {
        setHiddenNodeTypes((prev) => {
            const next = new Set(prev);
            if (next.has(type)) next.delete(type);
            else next.add(type);
            return next;
        });
    }, []);

    const handleToggleEdgeType = useCallback((type: string) => {
        setHiddenEdgeTypes((prev) => {
            const next = new Set(prev);
            if (next.has(type)) next.delete(type);
            else next.add(type);
            return next;
        });
    }, []);

    const handleToggleVisibility = useCallback((visibility: VisibilityFilter) => {
        setHiddenVisibility((prev) => {
            const next = new Set(prev);
            if (next.has(visibility)) next.delete(visibility);
            else next.add(visibility);
            return next;
        });
    }, []);

    const handleNodeClick: NodeMouseHandler = useCallback(
        (_event, node) => {
            const backendNode = backendById.get(node.id);
            if (backendNode) setSelectedNode(backendNode);
        },
        [backendById],
    );

    const handlePaneClick = useCallback(
        (event: MouseEvent) => {
            if (!useCanvasMode || canvasDots.length === 0) {
                setSelectedNode(null);
                return;
            }
            const flow = screenToFlowPosition({ x: event.clientX, y: event.clientY });
            const hit = hitTestCanvasDot(flow.x, flow.y, canvasDots, getZoom());
            if (hit) {
                const backendNode = backendById.get(hit);
                if (backendNode) setSelectedNode(backendNode);
                return;
            }
            setSelectedNode(null);
        },
        [useCanvasMode, canvasDots, screenToFlowPosition, getZoom, backendById],
    );

    const handleFitView = useCallback(() => {
        fitView({ padding: 0.12, duration: 180 });
    }, [fitView]);

    if (architecture.nodes.length === 0) {
        return (
            <div className="empty-state">
                <p>No network graph data available.</p>
            </div>
        );
    }

    return (
        <div className="architecture-container">
            <GraphToolbar
                nodeTypes={availableNodeTypes}
                edgeTypes={availableEdgeTypes}
                hiddenNodeTypes={hiddenNodeTypes}
                hiddenEdgeTypes={hiddenEdgeTypes}
                hiddenVisibility={hiddenVisibility}
                onToggleNodeType={handleToggleNodeType}
                onToggleEdgeType={handleToggleEdgeType}
                onToggleVisibility={handleToggleVisibility}
                layout={layout}
                onLayoutChange={setLayout}
                nodeCount={visibleCount}
                edgeCount={edgeCount}
                publicCount={visibilityCounts.publicCount}
                privateCount={visibilityCounts.privateCount}
                onFitView={handleFitView}
            />

            <div className="architecture-body">
                <div className="architecture-graph">
                    <ReactFlow
                        nodes={nodes}
                        edges={edges}
                        nodeTypes={nodeTypes}
                        onNodeClick={handleNodeClick}
                        onPaneClick={handlePaneClick}
                        minZoom={0.02}
                        maxZoom={2.5}
                        nodesDraggable={false}
                        nodesConnectable={false}
                        elementsSelectable={!useCanvasMode}
                        edgesFocusable={false}
                        nodesFocusable={false}
                        elevateNodesOnSelect={false}
                        onlyRenderVisibleElements
                        zoomOnDoubleClick={false}
                        proOptions={{ hideAttribution: true }}
                        defaultEdgeOptions={{
                            type: 'straight',
                            focusable: false,
                            interactionWidth: 0,
                        }}
                    >
                        {useCanvasMode && (
                            <SocialCanvasLayer dots={canvasDots} spokes={canvasSpokes} />
                        )}
                        {!useCanvasMode && <Background gap={22} size={1} color="#e2e8f0" />}
                        <Controls showInteractive={false} className="wb-controls" />
                        {nodes.length <= 80 && (
                            <MiniMap
                                nodeColor={miniMapNodeColor}
                                nodeStrokeWidth={0}
                                pannable
                                zoomable
                                maskColor="rgba(15, 23, 42, 0.12)"
                                className="wb-minimap"
                            />
                        )}
                    </ReactFlow>
                </div>

                {selectedNode && (
                    <NodeDetailPanel
                        node={selectedNode}
                        allEdges={architecture.edges}
                        allNodes={architecture.nodes}
                        onClose={() => setSelectedNode(null)}
                    />
                )}
            </div>

            <GraphLegend />

            {stats && (
                <div className="graph-stats-bar">
                    <span>Depth: {stats.maxDepth}</span>
                    <span>·</span>
                    {Object.entries(stats.nodeTypeCounts)
                        .sort(([, a], [, b]) => b - a)
                        .map(([type, count]) => (
                            <span key={type}>
                                {type}: {count}
                            </span>
                        ))}
                    {useCanvasMode && (
                        <>
                            <span>·</span>
                            <span>
                                Fast mode: {nodes.filter((n) => !n.hidden).length} interactive +{' '}
                                {canvasDots.length} canvas dots
                            </span>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}

function ArchitectureGraph({ architecture, stats }: Props) {
    return (
        <ReactFlowProvider>
            <ArchitectureGraphInner architecture={architecture} stats={stats} />
        </ReactFlowProvider>
    );
}

export default ArchitectureGraph;
