import { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { Stats } from './components/Stats';
import { Toolbar } from './components/Toolbar';
import { FileGrid } from './components/FileGrid';
import { UploadModal } from './components/UploadModal';
import { EditModal } from './components/EditModal';
import { Notification } from './components/Notification';
import { useFiles } from './hooks/useFiles';
import { useStats } from './hooks/useStats';
import './App.css';

function App() {
  const { files, loading, upload, updateTags, remove } = useFiles();
  const { refresh: refreshStats } = useStats();
  const [filteredFiles, setFilteredFiles] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTags, setSelectedTags] = useState([]);
  
  // Modales
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingFile, setEditingFile] = useState(null);

  // Filtrar archivos por búsqueda y tags
  useEffect(() => {
    let result = files;

    // Filtrar por búsqueda
    if (searchTerm) {
      result = result.filter(file => {
        const filename = file.filename || file.name || '';
        return filename.toLowerCase().includes(searchTerm.toLowerCase());
      });
    }

    // Filtrar por tags seleccionados
    if (selectedTags.length > 0) {
      result = result.filter(file =>
        selectedTags.every(tag => (file.tags || []).includes(tag))
      );
    }

    setFilteredFiles(result);
  }, [files, searchTerm, selectedTags]);

  const handleSearch = (term) => {
    setSearchTerm(term);
  };

  const handleFilterByTag = (tags) => {
    setSelectedTags(tags);
  };

  const handleUpload = async (file, tags) => {
    const success = await upload(file, tags);
    if (success) {
      refreshStats();
    }
    return success;
  };

  const handleEdit = (file) => {
    setEditingFile(file);
    setEditModalOpen(true);
  };

  const handleSaveTags = async (filename, tags) => {
    const success = await updateTags(filename, tags);
    if (success) {
      refreshStats();
    }
    return success;
  };

  const handleDelete = async (filename) => {
    const success = await remove(filename);
    if (success) {
      refreshStats();
    }
    return success;
  };

  return (
    <div className="container">
      <Header />
      <Stats />
      <Toolbar 
        onSearch={handleSearch}
        onFilterByTag={handleFilterByTag}
        onOpenUpload={() => setUploadModalOpen(true)}
      />
      <FileGrid 
        files={filteredFiles}
        loading={loading}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />

      <UploadModal 
        isOpen={uploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        onUpload={handleUpload}
      />

      <EditModal 
        isOpen={editModalOpen}
        file={editingFile}
        onClose={() => {
          setEditModalOpen(false);
          setEditingFile(null);
        }}
        onSave={handleSaveTags}
      />

      <Notification />
    </div>
  );
}

export default App;
