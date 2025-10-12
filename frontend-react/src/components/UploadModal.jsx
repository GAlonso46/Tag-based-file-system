import { useState, useRef } from 'react';
import './UploadModal.css';

export const UploadModal = ({ isOpen, onClose, onUpload }) => {
    const [selectedFile, setSelectedFile] = useState(null);
    const [tags, setTags] = useState([]);
    const [tagInput, setTagInput] = useState('');
    const [uploading, setUploading] = useState(false);
    const [dragActive, setDragActive] = useState(false);
    const fileInputRef = useRef(null);

    const handleDrag = (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === "dragenter" || e.type === "dragover") {
            setDragActive(true);
        } else if (e.type === "dragleave") {
            setDragActive(false);
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
        
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            setSelectedFile(e.dataTransfer.files[0]);
        }
    };

    const handleFileSelect = (e) => {
        if (e.target.files && e.target.files[0]) {
            setSelectedFile(e.target.files[0]);
        }
    };

    const handleAddTag = (e) => {
        if (e.key === 'Enter' && tagInput.trim()) {
            e.preventDefault();
            if (!tags.includes(tagInput.trim())) {
                setTags([...tags, tagInput.trim()]);
            }
            setTagInput('');
        }
    };

    const handleRemoveTag = (tagToRemove) => {
        setTags(tags.filter(tag => tag !== tagToRemove));
    };

    const handleUpload = async () => {
        if (!selectedFile) return;

        setUploading(true);
        const success = await onUpload(selectedFile, tags);
        setUploading(false);

        if (success) {
            handleClose();
        }
    };

    const handleClose = () => {
        setSelectedFile(null);
        setTags([]);
        setTagInput('');
        setUploading(false);
        onClose();
    };

    if (!isOpen) return null;

    return (
        <div className="modal-overlay" onClick={handleClose}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h2>📤 Subir Archivo</h2>
                    <button className="modal-close" onClick={handleClose}>×</button>
                </div>

                <div className="modal-body">
                    <div 
                        className={`upload-zone ${dragActive ? 'drag-active' : ''}`}
                        onDragEnter={handleDrag}
                        onDragLeave={handleDrag}
                        onDragOver={handleDrag}
                        onDrop={handleDrop}
                        onClick={() => fileInputRef.current?.click()}
                    >
                        <input
                            ref={fileInputRef}
                            type="file"
                            style={{ display: 'none' }}
                            onChange={handleFileSelect}
                        />
                        {selectedFile ? (
                            <div className="file-selected">
                                <div className="file-icon">📎</div>
                                <div className="file-info">
                                    <div className="file-name">{selectedFile.name}</div>
                                    <div className="file-size">
                                        {(selectedFile.size / 1024).toFixed(2)} KB
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="upload-prompt">
                                <div className="upload-icon">☁️</div>
                                <p>Arrastra un archivo aquí</p>
                                <p className="upload-hint">o haz clic para seleccionar</p>
                            </div>
                        )}
                    </div>

                    <div className="tag-input-section">
                        <label>Etiquetas:</label>
                        <input
                            type="text"
                            className="tag-input"
                            placeholder="Escribe y presiona Enter"
                            value={tagInput}
                            onChange={(e) => setTagInput(e.target.value)}
                            onKeyDown={handleAddTag}
                        />
                        <div className="tags-list">
                            {tags.map(tag => (
                                <span key={tag} className="tag">
                                    {tag}
                                    <button onClick={() => handleRemoveTag(tag)}>×</button>
                                </span>
                            ))}
                        </div>
                    </div>
                </div>

                <div className="modal-footer">
                    <button className="btn btn-secondary" onClick={handleClose}>
                        Cancelar
                    </button>
                    <button 
                        className="btn btn-primary" 
                        onClick={handleUpload}
                        disabled={!selectedFile || uploading}
                    >
                        {uploading ? 'Subiendo...' : 'Subir Archivo'}
                    </button>
                </div>
            </div>
        </div>
    );
};
