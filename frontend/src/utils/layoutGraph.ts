import dagre from '@dagrejs/dagre';
import {
    forceCenter,
    forceCollide,
    forceLink,
    forceManyBody,
    forceSimulation,
    type SimulationLinkDatum,
    type SimulationNodeDatum,
} from 'd3-force';
import type { Node, Edge } from '@xyflow/react';

const NODE_WIDTH = 200;
const NODE_HEIGHT = 50;

export interface LayoutOptions {
    direction?: 'TB' | 'LR' | 'BT' | 'RL';
    nodeSpacing?: number;
    rankSpacing?: number;
}

/**
 * Applies dagre hierarchical layout to React Flow nodes/edges.
 * Returns repositioned nodes.
 */
export function layoutGraph(
    nodes: Node[],
    edges: Edge[],
    options: LayoutOptions = {},
): Node[] {
    const { direction = 'TB', nodeSpacing = 40, rankSpacing = 80 } = options;

    const g = new dagre.graphlib.Graph({ compound: false })
        .setDefaultEdgeLabel(() => ({}))
        .setGraph({
            rankdir: direction,
            nodesep: nodeSpacing,
            ranksep: rankSpacing,
            marginx: 20,
            marginy: 20,
        });

    for (const node of nodes) {
        g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
    }

    for (const edge of edges) {
        g.setEdge(edge.source, edge.target);
    }

    dagre.layout(g);

    return nodes.map((node) => {
        const pos = g.node(node.id);
        return {
            ...node,
            position: {
                x: pos.x - NODE_WIDTH / 2,
                y: pos.y - NODE_HEIGHT / 2,
            },
        };
    });
}

interface ForceNode extends SimulationNodeDatum {
    id: string;
    radius: number;
}

export interface ForceLayoutOptions {
    /** Node id => rendered diameter (px). Larger nodes repel more and avoid overlap. */
    sizeById?: Map<string, number>;
    /** Node id pinned to the center of the canvas (e.g. the seed profile). */
    centerId?: string;
}

/**
 * Force / radial layout for social graphs.
 *
 * Follower crawls are typically a star (one hub + N leaves). Force simulation on
 * 1000 nodes is O(n²) and freezes the UI — detect that case and use an O(n)
 * concentric radial layout instead. Dense graphs still use a short force sim.
 */
export function forceLayout(
    nodes: Node[],
    edges: Edge[],
    options: ForceLayoutOptions = {},
): Node[] {
    const { sizeById, centerId } = options;
    const count = nodes.length;
    if (count === 0) return nodes;

    if (isStarLike(nodes, edges, centerId)) {
        return radialLayout(nodes, edges, { sizeById, centerId });
    }

    // Seed positions on a ring so the deterministic simulation starts untangled.
    const simNodes: ForceNode[] = nodes.map((node, index) => {
        const angle = (index / count) * Math.PI * 2;
        const ring = 280 + Math.sqrt(count) * 10;
        return {
            id: node.id,
            radius: (sizeById?.get(node.id) ?? 24) / 2,
            x: Math.cos(angle) * ring,
            y: Math.sin(angle) * ring,
        };
    });

    const indexById = new Map(simNodes.map((node, index) => [node.id, index]));
    const simLinks: SimulationLinkDatum<ForceNode>[] = edges
        .filter((edge) => indexById.has(edge.source) && indexById.has(edge.target))
        .map((edge) => ({ source: edge.source, target: edge.target }));

    const linkDistance = 48 + Math.sqrt(count) * 3;
    const charge = -80 - Math.min(count, 800) / 16;

    const simulation = forceSimulation(simNodes)
        .force(
            'link',
            forceLink<ForceNode, SimulationLinkDatum<ForceNode>>(simLinks)
                .id((node) => node.id)
                .distance(linkDistance)
                .strength(0.08),
        )
        .force(
            'charge',
            forceManyBody<ForceNode>().strength(charge).distanceMax(count > 400 ? 600 : 1000),
        )
        .force('center', forceCenter(0, 0))
        .stop();

    // Collide is the expensive part — only enable for smaller graphs.
    if (count <= 250) {
        simulation.force(
            'collide',
            forceCollide<ForceNode>().radius((node) => node.radius + 4).iterations(1),
        );
    }

    // Cap ticks hard: UI must stay responsive when layout runs on the main thread.
    const ticks = count > 600 ? 40 : count > 300 ? 70 : Math.min(160, 50 + Math.floor(count / 8));
    for (let i = 0; i < ticks; i += 1) simulation.tick();

    if (centerId) {
        const center = simNodes.find((node) => node.id === centerId);
        if (center && center.x != null && center.y != null) {
            const dx = -center.x;
            const dy = -center.y;
            for (const node of simNodes) {
                node.x = (node.x ?? 0) + dx;
                node.y = (node.y ?? 0) + dy;
            }
        }
    }

    const positioned = new Map(simNodes.map((node) => [node.id, node]));
    return nodes.map((node) => {
        const sim = positioned.get(node.id);
        const size = sizeById?.get(node.id) ?? 24;
        return {
            ...node,
            position: {
                x: (sim?.x ?? 0) - size / 2,
                y: (sim?.y ?? 0) - size / 2,
            },
        };
    });
}

/** Concentric rings around the hub — O(n), no simulation. */
export function radialLayout(
    nodes: Node[],
    edges: Edge[],
    options: ForceLayoutOptions = {},
): Node[] {
    const { sizeById, centerId } = options;
    const count = nodes.length;
    if (count === 0) return nodes;

    const degree = new Map<string, number>();
    for (const edge of edges) {
        degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
        degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
    }

    const hubId =
        centerId ??
        [...degree.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ??
        nodes[0]?.id;

    const leaves = nodes.filter((node) => node.id !== hubId);
    // Spread leaves across 2–4 rings so a 1k-node star does not become a solid disc.
    const ringCount = Math.min(4, Math.max(1, Math.ceil(leaves.length / 180)));
    const baseRadius = 180 + Math.sqrt(count) * 8;

    const positions = new Map<string, { x: number; y: number }>();
    if (hubId) positions.set(hubId, { x: 0, y: 0 });

    leaves.forEach((node, index) => {
        const ring = index % ringCount;
        const slotsOnRing = Math.ceil(leaves.length / ringCount);
        const slot = Math.floor(index / ringCount);
        const angle = (slot / slotsOnRing) * Math.PI * 2 + ring * 0.17;
        const radius = baseRadius + ring * (90 + Math.sqrt(count) * 2);
        positions.set(node.id, {
            x: Math.cos(angle) * radius,
            y: Math.sin(angle) * radius,
        });
    });

    return nodes.map((node) => {
        const size = sizeById?.get(node.id) ?? 24;
        const pos = positions.get(node.id) ?? { x: 0, y: 0 };
        return {
            ...node,
            position: {
                x: pos.x - size / 2,
                y: pos.y - size / 2,
            },
        };
    });
}

function isStarLike(nodes: Node[], edges: Edge[], centerId?: string): boolean {
    const count = nodes.length;
    if (count < 40) return false;
    // Follower graphs: almost every edge touches the seed, edge count ≈ node count.
    if (edges.length < count * 0.6) return false;

    const degree = new Map<string, number>();
    for (const edge of edges) {
        degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
        degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
    }
    const hubDegree = centerId
        ? (degree.get(centerId) ?? 0)
        : Math.max(0, ...degree.values());
    return hubDegree >= count * 0.55;
}
