import { API_URL } from '../config';

// Obtener todos los archivos o filtrar por tags
export const fetchFiles = async (tags = null) => {
    const url = tags ? `${API_URL}/files?tags=${tags}` : `${API_URL}/files`;
    const response = await fetch(url);
    if (!response.ok) throw new Error('Error al cargar archivos');
    return response.json();
};

// Subir archivo
export const uploadFile = async (file, tags) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('tags', tags.join(','));

    const response = await fetch(`${API_URL}/files`, {
        method: 'POST',
        body: formData
    });

    if (!response.ok) throw new Error('Error al subir archivo');
    return response.json();
};

// Actualizar tags de un archivo
export const updateFileTags = async (filename, tags) => {
    console.log('🔄 API: Actualizando tags para:', filename, 'Tags:', tags); // Debug
    
    if (!filename) {
        console.error('❌ API: filename es undefined o vacío');
        throw new Error('Filename es requerido');
    }
    
    const response = await fetch(`${API_URL}/files/${filename}/tags`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tags })
    });

    if (!response.ok) throw new Error('Error al actualizar tags');
    return response.json();
};

// Eliminar archivo
export const deleteFile = async (filename) => {
    const response = await fetch(`${API_URL}/files/${filename}`, {
        method: 'DELETE'
    });

    if (!response.ok) throw new Error('Error al eliminar archivo');
    return response.json();
};

// Descargar archivo
export const downloadFile = (filename) => {
    window.open(`${API_URL}/files/${filename}/download`, '_blank');
};

// Obtener estadísticas
export const fetchStats = async () => {
    const response = await fetch(`${API_URL}/stats`);
    if (!response.ok) throw new Error('Error al cargar estadísticas');
    return response.json();
};

// Obtener tags populares
export const fetchPopularTags = async () => {
    const response = await fetch(`${API_URL}/tags`);
    if (!response.ok) throw new Error('Error al cargar tags');
    return response.json();
};
