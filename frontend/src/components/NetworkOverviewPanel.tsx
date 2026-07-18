import type { NetworkOverview } from '../types';

interface Props {
    overview: NetworkOverview;
}

function NetworkOverviewPanel({ overview }: Props) {
    return (
        <div className="overview">
            <div className="overview-card summary-card" style={{ gridColumn: '1 / -1' }}>
                <h3>@{overview.seedUsername}</h3>
                <p className="summary-text">{overview.summary}</p>
                <div className="overview-meta">
                    <span className="meta-chip">{overview.platform}</span>
                    <span className="meta-chip">{overview.profileCount} profiles</span>
                    <span className="meta-chip">{overview.publicCount ?? 0} public</span>
                    <span className="meta-chip">{overview.privateCount ?? 0} private</span>
                    <span className="meta-chip">{overview.hashtagCount ?? 0} hashtags</span>
                    <span className="meta-chip">{overview.connectionCount} connections</span>
                </div>
            </div>

            <div className="overview-card" style={{ gridColumn: '1 / -1' }}>
                <h3>Most connected</h3>
                {overview.topConnected.length === 0 ? (
                    <p className="empty-hint">No connection data yet.</p>
                ) : (
                    <ul className="connected-list">
                        {overview.topConnected.map((item) => (
                            <li key={item}>{item}</li>
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
}

export default NetworkOverviewPanel;
