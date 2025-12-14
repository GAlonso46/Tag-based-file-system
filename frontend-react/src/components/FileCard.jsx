import { getFileIcon, formatBytes } from '../utils/formatters';
import { downloadFile } from '../services/api';
import './FileCard.css';

export const FileCard = ({ file, onEdit, onDelete }) => {
    if (!file) return null;

    // Soportar ambos formatos: filename (backend antiguo) y name (backend actual)
    const filename = file.filename || file.name;

    const handleDownload = () => {
        downloadFile(file);
    };

    const handleEdit = () => {
        console.log('✏️ Abriendo editor para:', file); // Debug
        onEdit(file);
    };

    const handleDelete = () => {
        if (window.confirm(`¿Eliminar ${filename}?`)) {
            onDelete(filename);
        }
    };

    return (
        <div className="file-card">
            <div className="file-icon">{getFileIcon(filename)}</div>
            <div className="file-name" title={filename}>{filename}</div>
            <div className="file-size">{formatBytes(file.size)}</div>
            
            {/* Mostrar propietario si está disponible (solo para admins) */}
            {file.owner && (
                <div style={{
                    fontSize: '0.8em',
                    color: 'var(--text-secondary)',
                    marginTop: '4px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                }}>
                    👤 <span style={{ fontWeight: '500' }}>{file.owner}</span>
                </div>
            )}
            
            <div className="file-tags">
                {(file.tags || []).map(tag => (
                    <span key={tag} className="file-tag">{tag}</span>
                ))}
            </div>

            <div className="file-actions">
                <button 
                    className="btn-icon" 
                    onClick={handleDownload}
                    title="Descargar"
                >
                    ⬇️
                </button>
                <button 
                    className="btn-icon" 
                    onClick={handleEdit}
                    title="Editar tags"
                >
                    ✏️
                </button>
                <button 
                    className="btn-icon btn-danger" 
                    onClick={handleDelete}
                    title="Eliminar"
                >
                    🗑️
                </button>
            </div>
        </div>
    );
};
