import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiRequest } from '../api/client.js';
import { useAuth } from '../features/auth/AuthContext.jsx';

function ProfileForm({ initialData, isSaving, onSave }) {
  const [companyName, setCompanyName] = useState(initialData?.company_name ?? '');
  const [industry, setIndustry] = useState(initialData?.industry ?? 'Healthcare');
  const [teamSize, setTeamSize] = useState(String(initialData?.team_size ?? 250));
  const [businessGoals, setBusinessGoals] = useState(initialData?.business_goals ?? '');

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave({
      company_name: companyName.trim(),
      industry: industry.trim() || 'Healthcare',
      team_size: Number(teamSize) || 1,
      business_goals: businessGoals.trim(),
    });
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="form-group">
        <label htmlFor="company-name" className="form-label">
          Hospital / Organization Name
        </label>
        <input
          id="company-name"
          className="input"
          required
          value={companyName}
          onChange={(e) => setCompanyName(e.target.value)}
          placeholder="Sunrise Multispeciality Hospital"
        />
      </div>

      <div className="form-group">
        <label htmlFor="industry" className="form-label">
          Industry
        </label>
        <input
          id="industry"
          className="input"
          required
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
        />
      </div>

      <div className="form-group">
        <label htmlFor="team-size" className="form-label">
          Team Size (Clinicians &amp; Staff)
        </label>
        <input
          id="team-size"
          type="number"
          min="1"
          className="input tabular"
          required
          value={teamSize}
          onChange={(e) => setTeamSize(e.target.value)}
        />
      </div>

      <div className="form-group">
        <label htmlFor="business-goals" className="form-label">
          Primary Operational &amp; Financial Goals
        </label>
        <textarea
          id="business-goals"
          rows={4}
          className="textarea"
          value={businessGoals}
          onChange={(e) => setBusinessGoals(e.target.value)}
          placeholder="Reduce OPD wait times, curb no-show rates, and align department expenses with invoiced revenue."
        />
      </div>

      <button type="submit" className="btn btn-primary" disabled={isSaving}>
        {isSaving ? 'Saving…' : 'Save Business Profile'}
      </button>
    </form>
  );
}

export default function BusinessProfilePage() {
  const { notify } = useAuth();
  const queryClient = useQueryClient();

  const profileQuery = useQuery({
    queryKey: ['business-profile'],
    queryFn: ({ signal }) => apiRequest('/business-profile', { signal }),
    retry: false,
  });

  const saveMutation = useMutation({
    mutationFn: (payload) => apiRequest('/business-profile', { method: 'PUT', body: payload }),
    onSuccess: (saved) => {
      queryClient.setQueryData(['business-profile'], saved);
      notify('Business profile saved', 'success');
    },
    onError: (err) => {
      notify(err.message || 'Failed to save profile', 'danger');
    },
  });

  const formKey = profileQuery.data?.updated_at || profileQuery.data?.id || 'new';

  return (
    <section aria-labelledby="profile-heading">
      <div className="page-header">
        <div>
          <h1 id="profile-heading" className="page-title">
            Business Profile
          </h1>
          <p className="page-subtitle">
            Configure your hospital organization context for executive reporting and AI agents.
          </p>
        </div>
      </div>

      <div className="card" style={{ maxWidth: '640px' }}>
        <ProfileForm
          key={formKey}
          initialData={profileQuery.data}
          isSaving={saveMutation.isPending}
          onSave={(payload) => saveMutation.mutate(payload)}
        />
      </div>
    </section>
  );
}
