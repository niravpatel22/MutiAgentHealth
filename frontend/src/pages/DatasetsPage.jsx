import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiRequest } from '../api/client.js';
import { useAuth } from '../features/auth/AuthContext.jsx';

export default function DatasetsPage() {
  const { user, activeDatasetId, setActiveDatasetId, notify } = useAuth();
  const queryClient = useQueryClient();

  const [datasetName, setDatasetName] = useState('');
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [selectedQualityId, setSelectedQualityId] = useState(null);
  const [uploadError, setUploadError] = useState(null);

  const canModify = user?.role === 'admin' || user?.role === 'manager';

  const datasetsQuery = useQuery({
    queryKey: ['datasets'],
    queryFn: ({ signal }) => apiRequest('/datasets?page=1&page_size=50', { signal }),
  });

  const qualityQuery = useQuery({
    queryKey: ['quality-report', selectedQualityId],
    queryFn: ({ signal }) =>
      apiRequest(`/datasets/${selectedQualityId}/quality-report`, { signal }),
    enabled: Boolean(selectedQualityId),
  });

  const uploadMutation = useMutation({
    mutationFn: async () => {
      const form = new FormData();
      if (datasetName.trim()) {
        form.append('name', datasetName.trim());
      }
      for (const file of selectedFiles) {
        form.append('files', file);
      }
      return apiRequest('/datasets', { method: 'POST', body: form });
    },
    onSuccess: (created) => {
      setUploadError(null);
      setDatasetName('');
      setSelectedFiles([]);
      setActiveDatasetId(created.id);
      setSelectedQualityId(created.id);
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
      notify(
        `Dataset "${created.name}" ingested (${created.quality_report.total_loaded} rows)`,
        'success',
      );
    },
    onError: (err) => {
      setUploadError(err.message || 'Upload failed');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id) => apiRequest(`/datasets/${id}`, { method: 'DELETE' }),
    onSuccess: (_, deletedId) => {
      if (activeDatasetId === deletedId) setActiveDatasetId(null);
      if (selectedQualityId === deletedId) setSelectedQualityId(null);
      queryClient.invalidateQueries({ queryKey: ['datasets'] });
      notify('Dataset deleted', 'info');
    },
  });

  const datasets = datasetsQuery.data?.items ?? [];
  const qr = qualityQuery.data;

  return (
    <section aria-labelledby="datasets-heading">
      <div className="page-header">
        <div>
          <h1 id="datasets-heading" className="page-title">
            Datasets &amp; Quality Reports
          </h1>
          <p className="page-subtitle">
            Upload <code>01_Healthcare.xlsx</code> (or the 5 entity CSVs). Every upload is
            validated, quarantined with reasons, and isolated by dataset ID.
          </p>
        </div>
      </div>

      {canModify && (
        <div className="card" style={{ marginBottom: '24px' }}>
          <h2 style={{ margin: '0 0 12px', fontSize: '1.05rem' }}>Upload New Dataset</h2>
          {uploadError && (
            <div
              role="alert"
              className="badge badge-danger"
              style={{
                display: 'block',
                padding: '10px 12px',
                borderRadius: '8px',
                marginBottom: '12px',
              }}
            >
              {uploadError}
            </div>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (selectedFiles.length === 0) {
                setUploadError('Please choose a .xlsx file or the 5 entity .csv files.');
                return;
              }
              uploadMutation.mutate();
            }}
          >
            <div className="form-group">
              <label htmlFor="dataset-name" className="form-label">
                Dataset Label (optional)
              </label>
              <input
                id="dataset-name"
                className="input"
                value={datasetName}
                onChange={(e) => setDatasetName(e.target.value)}
                placeholder="Hospital Operations (May–Oct 2026)"
              />
            </div>

            <div className="form-group">
              <label htmlFor="dataset-files" className="form-label">
                Workbook (.xlsx) or 5 CSV files (max 10 MB, 100,000 rows)
              </label>
              <input
                id="dataset-files"
                type="file"
                className="input"
                accept=".xlsx,.csv"
                multiple
                onChange={(e) => setSelectedFiles(Array.from(e.target.files || []))}
              />
            </div>

            <button type="submit" className="btn btn-primary" disabled={uploadMutation.isPending}>
              {uploadMutation.isPending ? 'Validating & Loading…' : 'Upload & Validate'}
            </button>
          </form>
        </div>
      )}

      <div className="card" style={{ marginBottom: '24px' }}>
        <h2 style={{ margin: '0 0 12px', fontSize: '1.05rem' }}>Uploaded Datasets</h2>
        {datasets.length === 0 ? (
          <p className="page-subtitle">No datasets uploaded yet.</p>
        ) : (
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Source File</th>
                  <th>Period</th>
                  <th>Rows Loaded</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {datasets.map((ds) => {
                  const totalRows = Object.values(ds.row_counts || {}).reduce(
                    (acc, n) => acc + Number(n || 0),
                    0,
                  );
                  return (
                    <tr key={ds.id}>
                      <td>
                        <strong>{ds.name}</strong>
                      </td>
                      <td>{ds.source_filename}</td>
                      <td className="tabular">
                        {ds.period_start} → {ds.period_end}
                      </td>
                      <td className="tabular">{totalRows.toLocaleString('en-IN')}</td>
                      <td>
                        <span className="badge badge-success">{ds.status}</span>
                      </td>
                      <td style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() => setActiveDatasetId(ds.id)}
                        >
                          {activeDatasetId === ds.id ? 'Active' : 'Use in Dashboard'}
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() => setSelectedQualityId(ds.id)}
                        >
                          Quality Report
                        </button>
                        {canModify && (
                          <button
                            type="button"
                            className="btn btn-danger"
                            onClick={() => deleteMutation.mutate(ds.id)}
                          >
                            Delete
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {qr && (
        <div className="card" role="region" aria-label="Ingestion quality report">
          <h2 style={{ margin: '0 0 12px', fontSize: '1.05rem' }}>
            Data Quality &amp; Preprocessing Report
          </h2>
          <p className="page-subtitle" style={{ marginBottom: '16px' }}>
            Total read: <strong className="tabular">{qr.total_read}</strong> · Loaded:{' '}
            <strong className="tabular">{qr.total_loaded}</strong> · Quarantined:{' '}
            <strong className="tabular">{qr.total_quarantined}</strong> · Derived dimensions:{' '}
            <strong className="tabular">{qr.derived_dimensions?.doctors}</strong> doctors,{' '}
            <strong className="tabular">{qr.derived_dimensions?.suppliers}</strong> suppliers,{' '}
            <strong className="tabular">{qr.derived_dimensions?.vendors}</strong> vendors.
          </p>

          {qr.warnings?.length > 0 && (
            <div style={{ marginBottom: '16px' }}>
              {qr.warnings.map((w) => (
                <div
                  key={w.code}
                  className="badge badge-warning"
                  style={{ display: 'block', padding: '10px 12px', borderRadius: '8px' }}
                >
                  <strong>Warning ({w.code}):</strong> {w.message}
                </div>
              ))}
            </div>
          )}

          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Entity Sheet</th>
                  <th>Rows Read</th>
                  <th>Rows Loaded</th>
                  <th>Rows Quarantined</th>
                </tr>
              </thead>
              <tbody>
                {Object.keys(qr.rows_read || {}).map((entity) => (
                  <tr key={entity}>
                    <td>{entity}</td>
                    <td className="tabular">{qr.rows_read[entity]}</td>
                    <td className="tabular">{qr.rows_loaded[entity]}</td>
                    <td className="tabular">{qr.quarantined_by_entity?.[entity] || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
