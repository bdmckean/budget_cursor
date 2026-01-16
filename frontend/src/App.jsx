import React, { useState, useEffect, useCallback } from 'react';
import './index.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:18080';

const formatErrorDetail = (detail) => {
  if (!detail) return '';

  if (typeof detail === 'string') {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) =>
        typeof item === 'object' && item !== null
          ? [item.msg, item.message, item.detail].filter(Boolean)[0] || JSON.stringify(item)
          : String(item)
      )
      .join('; ');
  }

  if (typeof detail === 'object') {
    const fromKnownKeys = [detail.message, detail.msg, detail.detail, detail.error]
      .filter(Boolean)
      .map((value) => formatErrorDetail(value))
      .filter(Boolean);
    if (fromKnownKeys.length > 0) {
      return fromKnownKeys.join('; ');
    }
    return JSON.stringify(detail);
  }

  try {
    return JSON.stringify(detail);
  } catch (err) {
    return String(detail);
  }
};

function App() {
  const [rows, setRows] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [categories, setCategories] = useState([]);
  const [progress, setProgress] = useState({ total: 0, mapped: 0 });
  const [loading, setLoading] = useState(false);
  const [showAddCategory, setShowAddCategory] = useState(false);
  const [newCategory, setNewCategory] = useState('');
  const [correctionInfo, setCorrectionInfo] = useState(null);
  const [suggestedCategory, setSuggestedCategory] = useState(null);
  const [suggesting, setSuggesting] = useState(false);
  const [currentFileName, setCurrentFileName] = useState(null);
  const [activeView, setActiveView] = useState('mapping');
  const [summaryData, setSummaryData] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState(null);
  const [reviewData, setReviewData] = useState(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [autoMapping, setAutoMapping] = useState(false);
  const fileInputRef = React.useRef(null);

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
        // Set current file name from first row if not already set
        if (!currentFileName && data.rows[0]?.source_file) {
          setCurrentFileName(data.rows[0].source_file);
        }
      }
    } catch (error) {
      console.error('Error loading progress:', error);
    }
  };

  const loadSummary = useCallback(async () => {
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const response = await fetch(`${API_URL}/spending-summary`);
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to load summary' }));
        throw new Error(errorData.detail || `Failed with status ${response.status}`);
      }
      const data = await response.json();
      setSummaryData(data);
    } catch (error) {
      console.error('Error loading summary:', error);
      const errorMessage = error instanceof Error ? error.message : String(error);
      setSummaryError(errorMessage);
    } finally {
      setSummaryLoading(false);
    }
  }, []);

  const loadReview = useCallback(async () => {
    setReviewLoading(true);
    try {
      const response = await fetch(`${API_URL}/review`);
      if (!response.ok) {
        throw new Error(`Failed with status ${response.status}`);
      }
      const data = await response.json();
      setReviewData(data);
    } catch (error) {
      console.error('Error loading review data:', error);
      setReviewData(null);
    } finally {
      setReviewLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeView === 'summary') {
      loadSummary();
    } else if (activeView === 'review') {
      loadReview();
    }
  }, [activeView, loadSummary, loadReview]);

  const handleViewChange = (view) => {
    setActiveView(view);
    if (view === 'mapping') {
      loadProgress();
    }
  };

  const handleAutoMapAll = async () => {
    if (!window.confirm('This will automatically map all remaining unmapped rows using AI. Continue?')) {
      return;
    }

    setAutoMapping(true);
    
    // Poll for progress updates during auto-mapping
    const progressInterval = setInterval(async () => {
      try {
        await loadProgress();
        if (activeView === 'review') {
          await loadReview();
        }
        if (activeView === 'summary') {
          await loadSummary();
        }
      } catch (e) {
        console.error('Error polling progress:', e);
      }
    }, 1000); // Poll every second
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 minute timeout
      
      const response = await fetch(`${API_URL}/auto-map-all`, {
        method: 'POST',
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      clearInterval(progressInterval);

      if (!response.ok) {
        let errorMessage = `Failed with status ${response.status}`;
        try {
          const errorData = await response.json();
          errorMessage = formatErrorDetail(errorData.detail) || errorMessage;
        } catch (e) {
          errorMessage = response.statusText || errorMessage;
        }
        throw new Error(errorMessage);
      }

      const data = await response.json();
      
      // Final reload of progress
      await loadProgress();
      
      // Reload summary if on summary view
      if (activeView === 'summary') {
        await loadSummary();
      }
      
      // Reload review if on review view
      if (activeView === 'review') {
        await loadReview();
      }
      
      alert(data.message + (data.errors ? `\n\nErrors:\n${data.errors.join('\n')}` : ''));
    } catch (error) {
      clearInterval(progressInterval);
      console.error('Error auto-mapping:', error);
      let errorMessage = 'Unknown error';
      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          errorMessage = 'Request timed out. The auto-mapping process may still be running. Please check the review screen.';
        } else {
          errorMessage = error.message;
        }
      } else if (typeof error === 'string') {
        errorMessage = error;
      }
      alert('Error auto-mapping: ' + errorMessage);
    } finally {
      setAutoMapping(false);
    }
  };

  const handleReviewItem = (rowIndex) => {
    setCurrentIndex(rowIndex);
    setActiveView('mapping');
    loadProgress();
  };

  const handleFileUpload = async (e) => {
    const selectedFile = e.target.files[0];
    if (!selectedFile) return;

    setLoading(true);
    // Reset state for new file
    setSuggestedCategory(null);
    setCurrentIndex(0);
    
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
      
      // Store current file name
      setCurrentFileName(data.source_file || selectedFile.name);
      setActiveView('mapping');
      
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
      
      // Find first unmapped row (skip already mapped rows)
      const unmappedIndex = progressData.rows.findIndex(r => !r.mapped);
      setCurrentIndex(unmappedIndex >= 0 ? unmappedIndex : 0);
      
      // Show message if some rows were already mapped
      if (data.mapped_count > 0) {
        alert(`File loaded. ${data.mapped_count} rows already mapped, ${data.unmapped_count} rows remaining.`);
      }
    } catch (error) {
      console.error('Upload error:', error);
      alert('Error uploading file: ' + (error.message || 'Unknown error'));
      // Reset file input
      if (e.target) {
        e.target.value = '';
      }
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } finally {
      setLoading(false);
    }
  };

  const handleUploadNewFile = () => {
    if (fileInputRef.current) {
      // Reset the input value to allow selecting the same file again
      fileInputRef.current.value = '';
      fileInputRef.current.click();
    } else {
      console.error('File input ref is not available');
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

      if (activeView === 'summary') {
        await loadSummary();
      }
      
      if (activeView === 'review') {
        await loadReview();
      }

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

  const handleAddCategory = async (confirmed = false) => {
    if (!newCategory.trim()) {
      alert('Please enter a category name');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/categories/add?confirm=${confirmed}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category: newCategory }),
      });

      if (!response.ok) {
        let errorMessage = `Failed with status ${response.status}`;
        try {
          const errorData = await response.json();
          const formattedDetail =
            formatErrorDetail(errorData.detail) || formatErrorDetail(errorData.message);
          if (formattedDetail) {
            errorMessage = formattedDetail;
          }
        } catch (e) {
          // If JSON parsing fails, use the status text
          errorMessage = response.statusText || errorMessage;
        }
        throw new Error(errorMessage);
      }

      let data;
      try {
        data = await response.json();
      } catch (e) {
        throw new Error('Invalid response from server');
      }
      
      // If corrections were made and not confirmed, show confirmation dialog
      if (data.corrections_made && !confirmed) {
        setCorrectionInfo({
          original: data.original,
          corrected: data.corrected,
        });
      } else {
        // No corrections or already confirmed, just add it
        setCategories(data.categories);
        setNewCategory('');
        setShowAddCategory(false);
        setCorrectionInfo(null);
        alert('Category added successfully!');
      }
    } catch (error) {
      console.error('Error adding category:', error);
      let errorMessage = 'Unknown error';
      if (error instanceof Error) {
        errorMessage = error.message;
      } else if (typeof error === 'string') {
        errorMessage = error;
      } else if (error && typeof error === 'object') {
        errorMessage = error.message || error.detail || JSON.stringify(error);
      }
      alert('Error adding category: ' + errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleCancelCorrection = () => {
    setCorrectionInfo(null);
    setNewCategory('');
  };

  const handleGetSuggestion = async () => {
    if (!rows[currentIndex]) return;

    setSuggesting(true);
    setSuggestedCategory(null);
    
    try {
      const response = await fetch(`${API_URL}/suggest-category`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ row_index: currentIndex }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to get suggestion' }));
        throw new Error(errorData.detail || `Failed with status ${response.status}`);
      }

      const data = await response.json();
      setSuggestedCategory(data.suggested_category);
    } catch (error) {
      alert('Error getting suggestion: ' + error.message);
    } finally {
      setSuggesting(false);
    }
  };

  const handleAcceptSuggestion = () => {
    if (suggestedCategory) {
      handleMapRow(suggestedCategory);
      setSuggestedCategory(null);
    }
  };

  const handleRejectSuggestion = () => {
    setSuggestedCategory(null);
  };

  const handleResetMappings = async () => {
    if (!currentFileName) {
      alert('No file loaded. Please upload a file first.');
      return;
    }

    if (!window.confirm(`Are you sure you want to reset all mappings for "${currentFileName}"? This cannot be undone.`)) {
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/reset-mappings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: currentFileName }),
      });

      if (!response.ok) {
        let errorMessage = `Failed with status ${response.status}`;
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorData.message || errorMessage;
        } catch (e) {
          errorMessage = response.statusText || errorMessage;
        }
        throw new Error(errorMessage);
      }

      const data = await response.json();
      
      // Reload progress to get reset state
      const progressResponse = await fetch(`${API_URL}/progress`);
      if (progressResponse.ok) {
        const progressData = await progressResponse.json();
        if (progressData.rows && progressData.rows.length > 0) {
          setRows(progressData.rows);
          setProgress({ total: progressData.total_rows || 0, mapped: progressData.mapped_count || 0 });
          setCurrentIndex(0);
        } else {
          setRows([]);
          setProgress({ total: 0, mapped: 0 });
          setCurrentIndex(0);
        }
      } else {
        setRows([]);
        setProgress({ total: 0, mapped: 0 });
        setCurrentIndex(0);
      }
      
      if (activeView === 'summary') {
        await loadSummary();
      }
      
      alert(data.message || 'Mappings reset successfully');
    } catch (error) {
      console.error('Error resetting mappings:', error);
      const errorMessage = error instanceof Error ? error.message : String(error);
      alert('Error resetting mappings: ' + errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const formatMonth = (monthKey) => {
    if (!monthKey || typeof monthKey !== 'string') {
      return monthKey || '';
    }

    const [yearStr, monthStr] = monthKey.split('-');
    const year = Number(yearStr);
    const month = Number(monthStr);
    if (!year || !month) {
      return monthKey;
    }

    const date = new Date(year, month - 1, 1);
    return date.toLocaleString(undefined, { month: 'short', year: 'numeric' });
  };

  const formatCurrency = (value) => {
    if (typeof value !== 'number' || Number.isNaN(value)) {
      return '-';
    }

    return value.toLocaleString(undefined, { style: 'currency', currency: 'USD' });
  };

  const currentRow = rows && rows.length > 0 && currentIndex < rows.length ? rows[currentIndex] : null;
  const summaryMonths = summaryData?.months || [];

  return (
    <div className="app">
      <header className="header">
        <div className="header-top">
          <h1>Budget Planner</h1>
          <div className="header-actions">
            <div className="view-toggle">
              <button
                className={activeView === 'mapping' ? 'active' : ''}
                onClick={() => handleViewChange('mapping')}
                disabled={activeView === 'mapping' && loading}
              >
                Mapping
              </button>
              <button
                className={activeView === 'summary' ? 'active' : ''}
                onClick={() => handleViewChange('summary')}
                disabled={summaryLoading && activeView === 'summary'}
              >
                Spending Summary
              </button>
              <button
                className={activeView === 'review' ? 'active' : ''}
                onClick={() => handleViewChange('review')}
                disabled={reviewLoading && activeView === 'review'}
              >
                Review Mappings
              </button>
            </div>
            <button
              className="upload-new-btn"
              onClick={handleUploadNewFile}
              disabled={loading}
              title="Upload a new CSV file"
            >
              📁 Upload New File
            </button>
          </div>
        </div>
        {/* Single file input for all upload buttons */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          onChange={handleFileUpload}
          disabled={loading}
          style={{ display: 'none' }}
          key="main-file-input"
        />
        <div className="progress-bar">
          <div className="progress-info">
            Progress: {progress.mapped} / {progress.total} rows mapped
          </div>
          <div className="progress-fill" style={{ width: `${progress.total > 0 ? (progress.mapped / progress.total) * 100 : 0}%` }}></div>
        </div>
      </header>

      <main className="main">
        {activeView === 'review' ? (
          <div className="review-section">
            <div className="review-header">
              <h2>Review Mappings</h2>
              <button
                className="auto-map-btn"
                onClick={handleAutoMapAll}
                disabled={autoMapping || loading}
              >
                {autoMapping ? 'Auto-mapping...' : '🤖 Auto-map All Remaining'}
              </button>
            </div>
            {reviewLoading ? (
              <p className="review-status">Loading review data...</p>
            ) : reviewData && reviewData.rows && reviewData.rows.length > 0 ? (
              <div className="review-content">
                <p className="review-info">
                  Total mapped: {reviewData.mapped_count} / {reviewData.total_rows} rows
                </p>
                <div className="review-table-container">
                  <table className="review-table">
                    <thead>
                      <tr>
                        <th>Row</th>
                        <th>Transaction Details</th>
                        <th>Category</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reviewData.rows.map((row) => (
                        <tr key={row.row_index}>
                          <td>{row.row_index + 1}</td>
                          <td>
                            <div className="review-transaction-details">
                              {Object.entries(row.original_data || {}).slice(0, 3).map(([key, value]) => (
                                <div key={key} className="review-detail-item">
                                  <strong>{key}:</strong> {String(value).substring(0, 50)}
                                  {String(value).length > 50 ? '...' : ''}
                                </div>
                              ))}
                            </div>
                          </td>
                          <td>
                            <span className="review-category">{row.category}</span>
                          </td>
                          <td>
                            <button
                              className="review-edit-btn"
                              onClick={() => handleReviewItem(row.row_index)}
                              disabled={loading}
                            >
                              Edit
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <p className="review-status">No mapped items to review yet.</p>
            )}
          </div>
        ) : activeView === 'summary' ? (
          <div className="summary-section">
            <h2>Spending Summary</h2>
            {summaryLoading ? (
              <p className="summary-status">Loading summary...</p>
            ) : summaryError ? (
              <p className="summary-status error">{summaryError}</p>
            ) : summaryData && summaryData.summary?.categories && Object.keys(summaryData.summary.categories).length > 0 ? (
              <div className="summary-card">
                <div className="summary-card-header">
                  <h3>All Files Combined</h3>
                  <p className="summary-card-subtitle">
                    Total categories: {Object.keys(summaryData.summary.categories).length}
                  </p>
                </div>
                {summaryMonths.length > 0 ? (
                  <table className="summary-table">
                    <thead>
                      <tr>
                        <th>Category</th>
                        {summaryMonths.map((month) => (
                          <th key={month}>{formatMonth(month)}</th>
                        ))}
                        <th>Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.keys(summaryData.summary.categories)
                        .sort((a, b) => a.localeCompare(b))
                        .map((category) => {
                          const monthTotals = summaryData.summary.categories[category] || {};
                          const categoryTotal = summaryMonths.reduce(
                            (sum, month) => sum + (monthTotals[month] || 0),
                            0
                          );
                          return (
                            <tr key={category}>
                              <td>{category}</td>
                              {summaryMonths.map((month) => {
                                const value = monthTotals[month];
                                return (
                                  <td key={month}>
                                    {typeof value === 'number' ? formatCurrency(value) : '-'}
                                  </td>
                                );
                              })}
                              <td>{formatCurrency(categoryTotal)}</td>
                            </tr>
                          );
                        })}
                    </tbody>
                  </table>
                ) : (
                  <p className="summary-status">No monthly data available yet.</p>
                )}
              </div>
            ) : (
              <p className="summary-status">No mapped transactions yet. Map some rows to see spending insights.</p>
            )}
          </div>
        ) : rows.length === 0 ? (
          <div className="upload-section">
            <h2>Upload CSV File</h2>
            <button
              className="upload-btn"
              onClick={handleUploadNewFile}
              disabled={loading}
            >
              {loading ? 'Uploading...' : '📁 Choose CSV File'}
            </button>
            <p>Select a CSV file to begin mapping rows to budget categories.</p>
            {loading && <p>Uploading and processing file...</p>}
            <button
              className="secondary-btn"
              onClick={() => handleViewChange('summary')}
              disabled={summaryLoading}
            >
              📊 View Spending Summary
            </button>
          </div>
        ) : (
          <div className="mapping-section">
            <div className="row-navigation">
              <button
                onClick={() => {
                  setCurrentIndex(Math.max(0, currentIndex - 1));
                  setSuggestedCategory(null);
                }}
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
                  setSuggestedCategory(null);
                }}
                disabled={currentIndex === rows.length - 1 || loading}
              >
                Next →
              </button>
              <div className="row-actions">
                {rows.length > 0 && (
                  <>
                    {currentFileName && (
                      <button
                        onClick={handleResetMappings}
                        disabled={loading}
                        className="reset-btn"
                      >
                        🔄 Reset Mappings
                      </button>
                    )}
                    <button
                      onClick={handleAutoMapAll}
                      disabled={autoMapping || loading || rows.every(r => r.mapped)}
                      className="auto-map-btn"
                    >
                      {autoMapping ? 'Auto-mapping...' : '🤖 Auto-map All Remaining'}
                    </button>
                  </>
                )}
                <button
                  onClick={() => handleViewChange('summary')}
                  className="summary-btn"
                  disabled={summaryLoading}
                >
                  📊 View Spending Summary
                </button>
                <button
                  onClick={() => handleViewChange('review')}
                  className="review-btn"
                  disabled={reviewLoading}
                >
                  👁️ Review Mappings
                </button>
              </div>
            </div>

            {currentRow ? (
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

                {!currentRow.mapped && (
                  <div className="suggestion-section">
                    <button
                      className="suggest-btn"
                      onClick={handleGetSuggestion}
                      disabled={loading || suggesting}
                    >
                      {suggesting ? 'Getting Suggestion...' : '🤖 Get AI Suggestion'}
                    </button>
                    {suggestedCategory && (
                      <div className="suggestion-box">
                        <div className="suggestion-header">
                          <strong>Suggested Category:</strong> {suggestedCategory}
                        </div>
                        <div className="suggestion-buttons">
                          <button
                            className="accept-btn"
                            onClick={handleAcceptSuggestion}
                            disabled={loading}
                          >
                            ✓ Yes, Use This
                          </button>
                          <button
                            className="reject-btn"
                            onClick={handleRejectSuggestion}
                            disabled={loading}
                          >
                            ✗ No, Choose Manually
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                <div className="category-selection">
                  <div className="category-header">
                    <h3>Select Category:</h3>
                    <button
                      className="add-category-btn"
                      onClick={() => setShowAddCategory(true)}
                      disabled={loading}
                    >
                      + Add Category
                    </button>
                  </div>
                  <div className="category-buttons">
                    {categories.map((cat) => (
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
            ) : (
              <p className="summary-status">No row selected.</p>
            )}
          </div>
        )}
      </main>

      {/* Add Category Modal */}
      {showAddCategory && (
        <div className="modal-overlay" onClick={() => !loading && setShowAddCategory(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Add New Category</h2>
            <input
              type="text"
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value)}
              placeholder="Enter category name"
              disabled={loading}
              onKeyPress={(e) => {
                if (e.key === 'Enter' && !loading) {
                  handleAddCategory();
                }
              }}
              autoFocus
            />
            <div className="modal-buttons">
              <button onClick={handleAddCategory} disabled={loading || !newCategory.trim()}>
                {loading ? 'Adding...' : 'Add Category'}
              </button>
              <button onClick={() => setShowAddCategory(false)} disabled={loading}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Correction Confirmation Modal */}
      {correctionInfo && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h2>Category Correction</h2>
            <p>The category you entered has been corrected:</p>
            <div className="correction-display">
              <div className="correction-item">
                <strong>Original:</strong> {correctionInfo.original}
              </div>
              <div className="correction-arrow">→</div>
              <div className="correction-item">
                <strong>Corrected:</strong> {correctionInfo.corrected}
              </div>
            </div>
            <div className="modal-buttons">
              <button onClick={() => handleAddCategory(true)} disabled={loading}>
                Confirm &amp; Add
              </button>
              <button onClick={handleCancelCorrection} disabled={loading}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;

