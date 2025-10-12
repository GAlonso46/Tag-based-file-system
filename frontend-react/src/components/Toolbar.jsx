import { useState } from 'react';
import { useStats } from '../hooks/useStats';
import './Toolbar.css';

export const Toolbar = ({ onSearch, onFilterByTag, onOpenUpload }) => {
    const [searchTerm, setSearchTerm] = useState('');
    const [selectedFilters, setSelectedFilters] = useState(new Set());
    const { popularTags } = useStats();

    const handleSearch = (value) => {
        setSearchTerm(value);
        onSearch(value);
    };

    const handleFilterToggle = (tag) => {
        const newFilters = new Set(selectedFilters);
        
        if (newFilters.has(tag)) {
            newFilters.delete(tag);
        } else {
            newFilters.add(tag);
        }
        
        setSelectedFilters(newFilters);
        onFilterByTag(Array.from(newFilters));
    };

    const clearSearch = () => {
        setSearchTerm('');
        onSearch('');
    };

    const clearFilters = () => {
        setSelectedFilters(new Set());
        onFilterByTag([]);
    };

    return (
        <div className="toolbar">
            <div className="search-bar">
                <div className="search-input-wrapper">
                    <input
                        type="text"
                        className="search-input"
                        placeholder="🔍 Buscar archivos..."
                        value={searchTerm}
                        onChange={(e) => handleSearch(e.target.value)}
                    />
                    {searchTerm && (
                        <button className="clear-search" onClick={clearSearch}>
                            ×
                        </button>
                    )}
                </div>
                <button className="btn btn-primary" onClick={onOpenUpload}>
                    📤 Subir Archivo
                </button>
            </div>

            {popularTags.length > 0 && (
                <div className="filter-section">
                    <div className="filter-header">
                        <span className="filter-label">🏷️ Filtrar por tag:</span>
                        {selectedFilters.size > 0 && (
                            <button className="clear-filters" onClick={clearFilters}>
                                Limpiar filtros
                            </button>
                        )}
                    </div>
                    <div className="filter-tags">
                        {popularTags.map(([tag, count]) => (
                            <button
                                key={tag}
                                className={`filter-tag ${selectedFilters.has(tag) ? 'active' : ''}`}
                                onClick={() => handleFilterToggle(tag)}
                            >
                                {tag} <span className="tag-count">({count})</span>
                            </button>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};
