export interface GraphNodeDto {
    id: string;
    name: string;
    type: string;
    metadata: Record<string, string>;
}

export interface GraphEdgeDto {
    source: string;
    target: string;
    relationship: string;
}

export interface ArchitectureResponse {
    nodes: GraphNodeDto[];
    edges: GraphEdgeDto[];
}

export interface GraphStatsResponse {
    totalNodes: number;
    totalEdges: number;
    nodeTypeCounts: Record<string, number>;
    edgeTypeCounts: Record<string, number>;
    maxDepth: number;
    rootNodes: string[];
    leafNodes: string[];
}

export type SocialPlatform = 'Demo' | 'Instagram' | 'TikTok';

export type CrawlSource = 'apify' | 'local';

export interface CrawlNetworkRequest {
    username: string;
    platform: SocialPlatform;
    source?: CrawlSource;
    depth?: number;
    maxProfiles?: number;
    forceRefresh?: boolean;
}

export interface CrawlNetworkResponse {
    networkId: string;
    status: string;
}

export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed';

export interface CrawlJob {
    jobId: string;
    status: JobStatus;
    progress: number;
    message: string;
    networkId?: string | null;
    error?: string | null;
}

export interface NetworkOverview {
    networkId: string;
    seedUsername: string;
    platform: string;
    profileCount: number;
    connectionCount: number;
    publicCount: number;
    privateCount: number;
    hashtagCount: number;
    summary: string;
    topConnected: string[];
}
