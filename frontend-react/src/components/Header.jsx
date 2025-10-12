import { useTheme } from '../context/ThemeContext';
import './Header.css';

export const Header = () => {
    const { isDarkMode, toggleDarkMode } = useTheme();

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
                <button className="theme-toggle" onClick={toggleDarkMode}>
                    <span id="themeIcon">{isDarkMode ? '☀️' : '🌙'}</span>
                    <span id="themeText">{isDarkMode ? 'Light Mode' : 'Dark Mode'}</span>
                </button>
            </div>
        </div>
    );
};
