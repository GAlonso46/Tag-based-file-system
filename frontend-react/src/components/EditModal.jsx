import { useState, useEffect } from 'react';
import './UploadModal.css'; // Reutilizamos los estilos

export const EditModal = ({ isOpen, file, onClose, onSave }) => {
    const [tags, setTags] = useState([]);
    const [tagInput, setTagInput] = useState('');
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        if (file) {
            console.log('📝 Editando archivo:', file); // Debug
            setTags(file.tags || []);
        }
    }, [file]);

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

    const handleSave = async () => {
        const filename = file.filename || file.name; // Soportar ambos formatos
        console.log('💾 Guardando tags para:', filename, 'Tags:', tags); // Debug
        
        if (!file || !filename) {
            console.error('❌ Error: file o filename es undefined', file);
            return;
        }
        
        setSaving(true);
        const success = await onSave(filename, tags);
        setSaving(false);

        if (success) {
            handleClose();
        }
    };

    const handleClose = () => {
        setTags([]);
        setTagInput('');
        setSaving(false);
        onClose();
    };

    if (!isOpen || !file) return null;

    return (
        <div className="modal-overlay" onClick={handleClose}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h2>✏️ Editar Tags</h2>
                    <button className="modal-close" onClick={handleClose}>×</button>
                </div>

                <div className="modal-body">
                    <div className="file-info-section">
                        <p className="editing-file">
                            <strong>Archivo:</strong> {file.filename || file.name}
                        </p>
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
                        onClick={handleSave}
                        disabled={saving}
                    >
                        {saving ? 'Guardando...' : 'Guardar Cambios'}
                    </button>
                </div>
            </div>
        </div>
    );
};
