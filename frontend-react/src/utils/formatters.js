// Formatear bytes a tamaño legible
export const formatBytes = (bytes) => {
    if (!bytes || bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
};

// Obtener icono según extensión
export const getFileIcon = (filename) => {
    if (!filename) return '📎';
    const ext = filename.split('.').pop().toLowerCase();
    const icons = {
        pdf: '📄',
        doc: '📝', docx: '📝',
        xls: '📊', xlsx: '📊',
        ppt: '📽️', pptx: '📽️',
        jpg: '🖼️', jpeg: '🖼️', png: '🖼️', gif: '🖼️', svg: '🖼️',
        mp4: '🎥', avi: '🎥', mov: '🎥',
        mp3: '🎵', wav: '🎵',
        zip: '📦', rar: '📦', '7z': '📦',
        txt: '📃',
        js: '💻', jsx: '⚛️', ts: '💻', tsx: '⚛️',
        py: '🐍',
        html: '🌐', css: '🎨',
    };
    return icons[ext] || '📎';
};
