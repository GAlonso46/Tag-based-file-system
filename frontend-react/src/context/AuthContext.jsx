import { createContext, useContext, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const AuthContext = createContext(null);

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth debe usarse dentro de AuthProvider');
    }
    return context;
};

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(null);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();

    // Cargar usuario desde localStorage al iniciar
    useEffect(() => {
        const storedToken = localStorage.getItem('token');
        const storedUsername = localStorage.getItem('username');
        const storedIsAdmin = localStorage.getItem('is_admin');
        
        if (storedToken && storedUsername) {
            setToken(storedToken);
            setUser({ 
                username: storedUsername,
                is_admin: storedIsAdmin === '1'
            });
        }
        
        setLoading(false);
    }, []);

    const login = (accessToken, userData) => {
        localStorage.setItem('token', accessToken);
        localStorage.setItem('username', userData.username);
        localStorage.setItem('is_admin', userData.is_admin || '0');
        setToken(accessToken);
        setUser({ 
            username: userData.username,
            is_admin: userData.is_admin === 1
        });
    };

    const logout = () => {
        localStorage.removeItem('token');
        localStorage.removeItem('username');
        localStorage.removeItem('is_admin');
        setToken(null);
        setUser(null);
        navigate('/login');
    };

    const value = {
        user,
        token,
        loading,
        isAuthenticated: !!token,
        login,
        logout
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
};
