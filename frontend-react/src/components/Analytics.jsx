import { useEffect, useState, useCallback } from 'react';
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    BarElement,
    Title,
    Tooltip,
    Legend,
    ArcElement,
    LineElement,
    PointElement
} from 'chart.js';
import { Bar, Pie, Line } from 'react-chartjs-2';
import { useAuth } from '../context/AuthContext';
import { API_URL } from '../config';
import './Analytics.css';

// Registrar componentes de Chart.js
ChartJS.register(
    CategoryScale,
    LinearScale,
    BarElement,
    Title,
    Tooltip,
    Legend,
    ArcElement,
    LineElement,
    PointElement
);

export const Analytics = () => {
    const { user } = useAuth();
    const [filesByDate, setFilesByDate] = useState(null);
    const [filesByType, setFilesByType] = useState(null);
    const [tagsUsage, setTagsUsage] = useState(null);
    const [storageByTag, setStorageByTag] = useState(null);
    const [userStats, setUserStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [days, setDays] = useState(30);

    const loadAnalytics = useCallback(async () => {
        if (!user?.is_admin) return;
        
        setLoading(true);
        try {
            const token = localStorage.getItem('token');
            const headers = {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            };

            const [dateRes, typeRes, tagsRes, storageRes, usersRes] = await Promise.all([
                fetch(`${API_URL}/analytics/files-by-date?days=${days}`, { headers }),
                fetch(`${API_URL}/analytics/files-by-type`, { headers }),
                fetch(`${API_URL}/analytics/tags-usage`, { headers }),
                fetch(`${API_URL}/analytics/storage-by-tag`, { headers }),
                fetch(`${API_URL}/analytics/user-stats`, { headers })
            ]);

            // Verificar respuestas antes de parsear
            if (dateRes.ok) setFilesByDate(await dateRes.json());
            if (typeRes.ok) setFilesByType(await typeRes.json());
            if (tagsRes.ok) setTagsUsage(await tagsRes.json());
            if (storageRes.ok) setStorageByTag(await storageRes.json());
            if (usersRes.ok) setUserStats(await usersRes.json());
            
        } catch (error) {
            console.error('Error al cargar analytics:', error);
        } finally {
            setLoading(false);
        }
    }, [user, days]);

    useEffect(() => {
        loadAnalytics();
    }, [loadAnalytics]);

    if (!user?.is_admin) {
        return (
            <div className="analytics-container">
                <div className="access-denied">
                    <h2>🔒 Acceso Restringido</h2>
                    <p>Solo los administradores pueden ver el panel de analytics.</p>
                </div>
            </div>
        );
    }

    if (loading) {
        return (
            <div className="analytics-container">
                <div className="loading">📊 Cargando analytics...</div>
            </div>
        );
    }

    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'top',
            },
        },
    };

    return (
        <div className="analytics-container">
            <div className="analytics-header">
                <h2>📊 Panel de Analytics</h2>
                <div className="date-filter">
                    <label>Últimos:</label>
                    <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
                        <option value={7}>7 días</option>
                        <option value={30}>30 días</option>
                        <option value={90}>90 días</option>
                        <option value={365}>1 año</option>
                    </select>
                </div>
            </div>

            <div className="charts-grid">
                {/* Archivos por Día */}
                {filesByDate && (
                    <div className="chart-card">
                        <h3>📈 Archivos Subidos por Día</h3>
                        <div className="chart-wrapper">
                            <Line
                                data={{
                                    labels: filesByDate.labels,
                                    datasets: [{
                                        label: 'Archivos',
                                        data: filesByDate.data,
                                        borderColor: 'rgb(102, 126, 234)',
                                        backgroundColor: 'rgba(102, 126, 234, 0.2)',
                                        tension: 0.4
                                    }]
                                }}
                                options={chartOptions}
                            />
                        </div>
                        <p className="chart-info">Total: {filesByDate.total} archivos</p>
                    </div>
                )}

                {/* Archivos por Tipo */}
                {filesByType && (
                    <div className="chart-card">
                        <h3>🗂️ Distribución por Tipo</h3>
                        <div className="chart-wrapper">
                            <Pie
                                data={{
                                    labels: filesByType.labels,
                                    datasets: [{
                                        data: filesByType.data,
                                        backgroundColor: [
                                            'rgba(255, 99, 132, 0.8)',
                                            'rgba(54, 162, 235, 0.8)',
                                            'rgba(255, 206, 86, 0.8)',
                                            'rgba(75, 192, 192, 0.8)',
                                            'rgba(153, 102, 255, 0.8)',
                                            'rgba(255, 159, 64, 0.8)',
                                        ]
                                    }]
                                }}
                                options={chartOptions}
                            />
                        </div>
                    </div>
                )}

                {/* Tags Más Usados */}
                {tagsUsage && (
                    <div className="chart-card">
                        <h3>🏷️ Top 10 Tags Más Usados</h3>
                        <div className="chart-wrapper">
                            <Bar
                                data={{
                                    labels: tagsUsage.labels,
                                    datasets: [{
                                        label: 'Usos',
                                        data: tagsUsage.data,
                                        backgroundColor: 'rgba(118, 75, 162, 0.8)',
                                    }]
                                }}
                                options={{
                                    ...chartOptions,
                                    scales: {
                                        y: {
                                            beginAtZero: true,
                                            ticks: {
                                                stepSize: 1
                                            }
                                        }
                                    }
                                }}
                            />
                        </div>
                    </div>
                )}

                {/* Almacenamiento por Tag */}
                {storageByTag && (
                    <div className="chart-card">
                        <h3>💾 Almacenamiento por Tag</h3>
                        <div className="chart-wrapper">
                            <Bar
                                data={{
                                    labels: storageByTag.labels,
                                    datasets: [{
                                        label: 'Tamaño (MB)',
                                        data: storageByTag.data,
                                        backgroundColor: 'rgba(75, 192, 192, 0.8)',
                                    }]
                                }}
                                options={chartOptions}
                            />
                        </div>
                    </div>
                )}

                {/* Estadísticas de Usuarios */}
                {userStats && (
                    <div className="chart-card full-width">
                        <h3>👥 Estadísticas de Usuarios</h3>
                        <div className="users-table">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Usuario</th>
                                        <th>Email</th>
                                        <th>Rol</th>
                                        <th>Archivos</th>
                                        <th>Espacio (MB)</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {userStats.users.map((user, index) => (
                                        <tr key={index}>
                                            <td>{user.username}</td>
                                            <td>{user.email}</td>
                                            <td>
                                                {user.is_admin ? (
                                                    <span className="badge admin">👑 Admin</span>
                                                ) : (
                                                    <span className="badge user">👤 Usuario</span>
                                                )}
                                            </td>
                                            <td>{user.file_count}</td>
                                            <td>{user.total_size_mb}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                            <p className="chart-info">Total de usuarios: {userStats.total_users}</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
