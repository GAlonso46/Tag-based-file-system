import { useStats } from '../hooks/useStats';
import { formatBytes } from '../utils/formatters';
import './Stats.css';

export const Stats = () => {
    const { stats, popularTags, loading } = useStats();

    if (loading) return <div className="stats-loading">Cargando estadísticas...</div>;

    return (
        <div className="stats-container">
            <div className="stats-cards">
                <div className="stat-card">
                    <div className="stat-icon">📁</div>
                    <div className="stat-info">
                        <div className="stat-value">{stats.total_files || 0}</div>
                        <div className="stat-label">Archivos</div>
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon">💾</div>
                    <div className="stat-info">
                        <div className="stat-value">{formatBytes(stats.total_size || 0)}</div>
                        <div className="stat-label">Espacio Usado</div>
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon">🏷️</div>
                    <div className="stat-info">
                        <div className="stat-value">{stats.total_tags || 0}</div>
                        <div className="stat-label">Tags Únicos</div>
                    </div>
                </div>
            </div>

            {popularTags.length > 0 && (
                <div className="popular-tags">
                    <h3>🔥 Tags Populares</h3>
                    <div className="tags-cloud">
                        {popularTags.map(([tag, count]) => (
                            <span key={tag} className="popular-tag">
                                {tag} <span className="tag-count">({count})</span>
                            </span>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};
