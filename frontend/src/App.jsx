import React, { useState, useEffect } from 'react';
import './index.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:18080';

function App() {
  const [rows, setRows] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [categories, setCategories] = useState([]);
  const [progress, setProgress] = useState({ total: 0, mapped: 0 });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Load categories
    fetch(`${API_URL}/categories`)
      .then(res => res.json())
      .then(data => setCategories(data.categories));

    // Load existing progress
    loadProgress();
  }, []);

  const loadProgress = async () => {
    try {
      const response = await fetch(`${API_URL}/progress`);
      const data = await response.json();
      if (data.rows && data.rows.length > 0) {
        setRows(data.rows);
        setProgress({ total: data.total_rows, mapped: data.mapped_count });
        // Find first unmapped row
        const unmappedIndex = data.rows.findIndex(r => !r.mapped);
        setCurrentIndex(unmappedIndex >= 0 ? unmappedIndex : 0);
      }
    } catch (error) {
      console.error('Error loading progress:', error);
    }
  };

  const handleFileUpload = async (e) => {
    const selectedFile = e.target.files[0];
    if (!selectedFile) return;

    setLoading(true);
    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await fetch(`${API_URL}/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(errorData.detail || `Upload failed with status ${response.status}`);
      }

      const data = await response.json();
      console.log('Upload response:', data);
      
      // After upload, fetch the full progress to get all rows
      const progressResponse = await fetch(`${API_URL}/progress`);
      
      if (!progressResponse.ok) {
        throw new Error('Failed to fetch progress after upload');
      }
      
      const progressData = await progressResponse.json();
      console.log('Progress data:', progressData);
      
      if (!progressData.rows || progressData.rows.length === 0) {
        throw new Error('No rows found in uploaded file');
      }
      
      setRows(progressData.rows);
      setProgress({ total: progressData.total_rows || 0, mapped: progressData.mapped_count || 0 });
      
      // Find first unmapped row
      const unmappedIndex = progressData.rows.findIndex(r => !r.mapped);
      setCurrentIndex(unmappedIndex >= 0 ? unmappedIndex : 0);
    } catch (error) {
      console.error('Upload error:', error);
      alert('Error uploading file: ' + (error.message || 'Unknown error'));
      // Reset file input
      e.target.value = '';
    } finally {
      setLoading(false);
    }
  };

  const handleMapRow = async (category) => {
    if (!rows[currentIndex]) return;

    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/map`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          row_index: currentIndex,
          category: category,
        }),
      });

      const data = await response.json();
      
      // Update local state
      const updatedRows = [...rows];
      updatedRows[currentIndex] = data.row;
      setRows(updatedRows);
      setProgress(prev => ({ ...prev, mapped: prev.mapped + 1 }));

      // Move to next unmapped row
      const nextIndex = updatedRows.findIndex((r, idx) => idx > currentIndex && !r.mapped);
      if (nextIndex >= 0) {
        setCurrentIndex(nextIndex);
      } else {
        // All done or reached end
        alert('All rows mapped!');
      }
    } catch (error) {
      alert('Error mapping row: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const currentRow = rows && rows.length > 0 && currentIndex < rows.length ? rows[currentIndex] : null;

  return (
    <div className="app">
      <header className="header">
        <h1>Budget Planner</h1>
        <div className="progress-bar">
          <div className="progress-info">
            Progress: {progress.mapped} / {progress.total} rows mapped
          </div>
          <div className="progress-fill" style={{ width: `${progress.total > 0 ? (progress.mapped / progress.total) * 100 : 0}%` }}></div>
        </div>
      </header>

      <main className="main">
        {rows.length === 0 ? (
          <div className="upload-section">
            <h2>Upload CSV File</h2>
            <input
              type="file"
              accept=".csv"
              onChange={handleFileUpload}
              disabled={loading}
              key={rows.length} // Reset input when rows change
            />
            <p>Select a CSV file to begin mapping rows to budget categories.</p>
            {loading && <p>Uploading and processing file...</p>}
          </div>
        ) : (
          <div className="mapping-section">
            <div className="row-navigation">
              <button
                onClick={() => setCurrentIndex(Math.max(0, currentIndex - 1))}
                disabled={currentIndex === 0 || loading}
              >
                ← Previous
              </button>
              <span className="row-counter">
                Row {currentIndex + 1} of {rows.length}
              </span>
              <button
                onClick={() => {
                  const next = rows.findIndex((r, idx) => idx > currentIndex && !r.mapped);
                  setCurrentIndex(next >= 0 ? next : Math.min(rows.length - 1, currentIndex + 1));
                }}
                disabled={currentIndex === rows.length - 1 || loading}
              >
                Next →
              </button>
            </div>

            {currentRow && (
              <div className="row-details">
                <h3>Row Data:</h3>
                <div className="row-data">
                  {Object.entries(currentRow.original_data).map(([key, value]) => (
                    <div key={key} className="data-field">
                      <strong>{key}:</strong> {value}
                    </div>
                  ))}
                </div>

                {currentRow.mapped && (
                  <div className="current-category">
                    Current Category: <strong>{currentRow.category}</strong>
                  </div>
                )}

                <div className="category-selection">
                  <h3>Select Category:</h3>
                  <div className="category-buttons">
                    {categories.map(cat => (
                      <button
                        key={cat}
                        onClick={() => handleMapRow(cat)}
                        disabled={loading}
                        className={currentRow.category === cat ? 'active' : ''}
                      >
                        {cat}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;

