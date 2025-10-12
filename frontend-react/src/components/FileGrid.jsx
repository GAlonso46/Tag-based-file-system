import { FileCard } from './FileCard';
import './FileGrid.css';

export const FileGrid = ({ files, loading, onEdit, onDelete }) => {
    if (loading) {
        return <div className="loading">Cargando archivos...</div>;
    }

    if (files.length === 0) {
        return (
            <div className="empty-state">
                <div className="empty-icon">📁</div>
                <h3>No hay archivos</h3>
                <p>Sube tu primer archivo para comenzar</p>
            </div>
        );
    }

    return (
        <div className="file-grid">
            {files.map(file => (
                <FileCard
                    key={file.filename || file.name}
                    file={file}
                    onEdit={onEdit}
                    onDelete={onDelete}
                />
            ))}
        </div>
    );
};
