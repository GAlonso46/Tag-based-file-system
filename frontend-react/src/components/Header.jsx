import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';
import './Header.css';

export const Header = () => {
    const { isDarkMode, toggleDarkMode } = useTheme();
    const { user, logout } = useAuth();

    return (
        <div className="header">
            <div className="header-content">
                <div>
                    <h1>
                        <span>🏷️</span>
                        Tag-Based File System
                    </h1>
                    <p>Organiza tus archivos con etiquetas inteligentes</p>
                </div>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                    {user && (
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                            <span style={{ 
                                padding: '8px 15px', 
                                background: 'var(--primary-gradient)', 
                                color: 'white', 
                                borderRadius: '8px',
                                fontSize: '0.9em',
                                fontWeight: '500'
                            }}>
                                👤 {user.username}
                            </span>
                            {user.is_admin && (
                                <span style={{ 
                                    padding: '8px 15px', 
                                    background: 'linear-gradient(135deg, #f39c12 0%, #e67e22 100%)', 
                                    color: 'white', 
                                    borderRadius: '8px',
                                    fontSize: '0.85em',
                                    fontWeight: '600',
                                    border: '2px solid rgba(255,255,255,0.3)'
                                }}>
                                    👑 ADMIN
                                </span>
                            )}
                        </div>
                    )}
                    <button className="theme-toggle" onClick={toggleDarkMode}>
                        <span id="themeIcon">{isDarkMode ? '☀️' : '🌙'}</span>
                        <span id="themeText">{isDarkMode ? 'Light Mode' : 'Dark Mode'}</span>
                    </button>
                    <button 
                        className="theme-toggle" 
                        onClick={logout}
                        style={{ background: '#e74c3c' }}
                    >
                        <span>🚪</span>
                        <span>Salir</span>
                    </button>
                </div>
            </div>
        </div>
    );
};
