import { useState, useEffect, useCallback } from 'react';
import { fetchFiles, uploadFile, updateFileTags, deleteFile } from '../services/api';
import { useNotification } from '../context/NotificationContext';

export const useFiles = () => {
    const [files, setFiles] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const { showNotification } = useNotification();

    const loadFiles = useCallback(async (tags = null) => {
        setLoading(true);
        setError(null);
        try {
            const data = await fetchFiles(tags);
            console.log('📁 Archivos cargados:', data); // Debug
            setFiles(Array.isArray(data) ? data : []);
        } catch (err) {
            console.error('❌ Error al cargar archivos:', err);
            setError(err.message);
            setFiles([]);
            showNotification('Error al cargar archivos', 'error');
        } finally {
            setLoading(false);
        }
    }, [showNotification]);

    useEffect(() => {
        loadFiles();
    }, [loadFiles]);

    const upload = async (file, tags) => {
        try {
            await uploadFile(file, tags);
            showNotification('Archivo subido correctamente', 'success');
            await loadFiles();
            return true;
        } catch (err) {
            showNotification('Error al subir archivo', 'error');
            return false;
        }
    };

    const updateTags = async (filename, tags) => {
        try {
            await updateFileTags(filename, tags);
            showNotification('Tags actualizados', 'success');
            await loadFiles();
            return true;
        } catch (err) {
            showNotification('Error al actualizar tags', 'error');
            return false;
        }
    };

    const remove = async (filename) => {
        try {
            await deleteFile(filename);
            showNotification('Archivo eliminado', 'success');
            await loadFiles();
            return true;
        } catch (err) {
            showNotification('Error al eliminar archivo', 'error');
            return false;
        }
    };

    return {
        files,
        loading,
        error,
        loadFiles,
        upload,
        updateTags,
        remove
    };
};
