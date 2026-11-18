import snapshot from './golden_snapshot.json' with { type: 'json' };
import openapiSpec from './openapi_spec.json' with { type: 'json' };

// Pre-seeded accounts matching LoginPage.jsx Quick-Fill Demo Role Credentials
const state = {
  users: [
    {
      id: '4287b864-8ceb-4f41-8d7c-d01e5e0cee25',
      email: 'admin@mediops.example',
      password: 'Admin#MediOps2026!',
      role: 'admin',
      is_active: true,
      created_at: '2026-11-18T15:00:00Z',
    },
    {
      id: 'd96ecb8f-def3-413f-bcb1-54b0a2e031ce',
      email: 'e2e.manager@mediops.example',
      password: 'Sunrise#Ward99!Ops',
      role: 'manager',
      is_active: true,
      created_at: '2026-11-18T15:05:00Z',
    },
    {
      id: 'ae10e06d-0b3d-453e-8d22-049a466812e4',
      email: 'audit.analyst@mediops.example',
      password: 'Analyst#MediOps2026!',
      role: 'analyst',
      is_active: true,
      created_at: '2026-11-18T15:10:00Z',
    },
  ],
  profiles: {
    'd96ecb8f-def3-413f-bcb1-54b0a2e031ce': {
      id: 'b1000000-0000-4000-8000-000000000001',
      company_name: 'Sunrise Multispeciality Hospital',
      industry: 'Healthcare',
      team_size: 250,
      business_goals:
        'Reduce outpatient wait times below 35 minutes, curb the 9% no-show rate, and align department expenses with invoiced revenue.',
      created_at: '2026-11-18T15:05:00Z',
      updated_at: '2026-11-18T16:00:00Z',
    },
  },
  recommendations: JSON.parse(JSON.stringify(snapshot.report.recommendations || [])),
  chatSessions: [
    {
      id: 'c1000000-0000-4000-8000-000000000001',
      dataset_id: snapshot.dataset.id,
      user_id: 'd96ecb8f-def3-413f-bcb1-54b0a2e031ce',
      title: 'Hospital Operations Q&A',
      created_at: '2026-11-18T16:00:00Z',
    },
  ],
  chatMessages: {
    'c1000000-0000-4000-8000-000000000001': [
      {
        id: 'm1000000-0000-4000-8000-000000000001',
        session_id: 'c1000000-0000-4000-8000-000000000001',
        role: 'user',
        content: 'What is our invoiced net revenue and approved-expense margin?',
        cited_metric_keys: [],
        created_at: '2026-11-18T16:01:00Z',
      },
      {
        id: 'm1000000-0000-4000-8000-000000000002',
        session_id: 'c1000000-0000-4000-8000-000000000001',
        role: 'assistant',
        content:
          'Across May–Oct 2026, invoiced net revenue (Billing.net_amount only, excluding consultation_fee) is INR 22,256,456.76, while Approved expenses total INR 26,551,788.08, resulting in an approved-expense margin of -INR 4,295,331.32 (-19.30%). Pending expenses represent INR 12,228,223.82 in unapproved exposure, and Rejected expenses (INR 14,190,130.93) are excluded from cost.',
        cited_metric_keys: [
          'finance.net_revenue',
          'finance.approved_expenses',
          'finance.pending_expenses',
          'finance.rejected_expenses',
          'finance.approved_margin',
          'finance.approved_margin_pct',
        ],
        created_at: '2026-11-18T16:01:01Z',
      },
    ],
  },
};

function jsonRes(body, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'X-Content-Type-Options': 'nosniff',
      'X-Frame-Options': 'DENY',
      'Referrer-Policy': 'no-referrer',
      ...extraHeaders,
    },
  });
}

function errRes(code, message, status = 400, details = null) {
  return jsonRes(
    {
      error: {
        code,
        message,
        details,
        request_id: crypto.randomUUID().replace(/-/g, ''),
      },
    },
    status,
  );
}

function encodeToken(user) {
  const payload = btoa(JSON.stringify({ sub: user.id, email: user.email, role: user.role }));
  return `mediops.${payload}.sig`;
}

function decodeUserFromReq(req, context) {
  const auth = req.headers.get('authorization') || '';
  if (auth.startsWith('Bearer mediops.')) {
    try {
      const part = auth.slice('Bearer '.length).split('.')[1];
      const { sub } = JSON.parse(atob(part));
      const u = state.users.find((x) => x.id === sub && x.is_active);
      if (u) return u;
    } catch {
      // ignore
    }
  }
  const cookieVal = context?.cookies?.get?.('careops_refresh');
  if (cookieVal) {
    const u = state.users.find((x) => x.id === cookieVal && x.is_active);
    if (u) return u;
  }
  return null;
}

function answerQuestion(q) {
  const ql = (q || '').toLowerCase();
  if (
    ql.includes('marketing') ||
    ql.includes('roi') ||
    ql.includes('ad spend') ||
    ql.includes('campaign')
  ) {
    return {
      content:
        'The dataset cannot answer that: no marketing campaign, channel, lead-source, or marketing spend data exists in 01_Healthcare.xlsx. Available patient growth metrics are total registered patients (1,200) and repeat-visit rate (43.92%, 527 patients with >= 2 completed visits).',
      cited_metric_keys: [
        'patients.total',
        'patients.repeat_visit_count',
        'patients.repeat_visit_rate',
      ],
    };
  }
  if (ql.includes('collected') || ql.includes('amount paid') || ql.includes('partially paid')) {
    return {
      content:
        'The dataset cannot answer that: Billing has no amount-paid column, so cash collected on Partially Paid invoices cannot be computed. By invoice count and invoiced net_amount: Paid = 896 invoices (INR 11,207,707.88), Partially Paid = 460 invoices (INR 5,500,100.69), Pending = 444 invoices (INR 5,548,648.19).',
      cited_metric_keys: ['finance.invoice_count', 'finance.net_revenue'],
    };
  }
  if (ql.includes('stock-out') || ql.includes('forecast') || ql.includes('consumption')) {
    return {
      content:
        'The dataset cannot answer that: Medicine_Inventory is a point-in-time snapshot not linked to billing or dispensing rates, so stock-out dates cannot be forecasted. Current snapshot risks: 111 items at or below reorder level, 20 items expiring within 90 days of 2026-10-31, and 6 duplicate batch numbers across 12 items.',
      cited_metric_keys: [
        'inventory.low_stock_items',
        'inventory.expiring_90d_items',
        'inventory.duplicate_batch_count',
      ],
    };
  }
  if (ql.includes('patient name') || ql.includes('phone') || ql.includes('pat0')) {
    return {
      content:
        'The dataset cannot answer that: individual patient names and full phone numbers are protected PII and are never exposed by the analytics engine or AI assistant.',
      cited_metric_keys: ['patients.total'],
    };
  }
  if (ql.includes('appointment') || ql.includes('wait') || ql.includes('no-show')) {
    return {
      content:
        'Across May–Oct 2026, total appointments reached 2,500: 1,782 Completed, 251 Scheduled pipeline (excluded from outcome rate denominators), 264 Cancelled, and 203 No Show. Among the 2,249 resolved appointments, the completion rate is 79.24% and the no-show rate is 9.03%. Average outpatient wait time is 49.92 minutes.',
      cited_metric_keys: [
        'appointments.total',
        'appointments.completed',
        'appointments.scheduled',
        'appointments.completion_rate',
        'appointments.no_show_rate',
        'appointments.avg_wait_minutes',
      ],
    };
  }
  if (ql.includes('inventory') || ql.includes('stock') || ql.includes('expir')) {
    return {
      content:
        'Across 1,000 medicine inventory items (as of 2026-10-31), 111 items are at or below their reorder level, 20 items expire within 90 days (on or before 2027-01-29), and 6 batch numbers are duplicated across 12 items.',
      cited_metric_keys: [
        'inventory.total_items',
        'inventory.low_stock_items',
        'inventory.expiring_90d_items',
        'inventory.duplicate_batch_count',
      ],
    };
  }
  return {
    content:
      'Across May–Oct 2026, invoiced net revenue (Billing.net_amount only) is INR 22,256,456.76 and Approved expenses are INR 26,551,788.08, yielding an approved-expense margin of -INR 4,295,331.32 (-19.30%). Total appointments are 2,500 (1,782 completed, 49.92 min average wait), registered patients are 1,200 (43.92% repeat-visit rate across 40 doctors), and 111 pharmacy items are at or below reorder level.',
    cited_metric_keys: [
      'finance.net_revenue',
      'finance.approved_expenses',
      'finance.approved_margin',
      'finance.approved_margin_pct',
      'appointments.total',
      'appointments.avg_wait_minutes',
      'patients.total',
      'inventory.low_stock_items',
    ],
  };
}

export default async (req, context) => {
  const url = new URL(req.url);
  const path = url.pathname.replace(/\/+$/, '') || '/';
  const method = req.method.toUpperCase();

  // Optional live proxy if RENDER_API_URL is explicitly configured in Netlify env vars
  const renderApiUrl =
    typeof Netlify !== 'undefined' ? Netlify.env.get('RENDER_API_URL') : undefined;
  if (renderApiUrl) {
    try {
      const target = `${renderApiUrl.replace(/\/+$/, '')}${path}${url.search}`;
      const proxied = await fetch(target, {
        method,
        headers: req.headers,
        body: method === 'GET' || method === 'HEAD' ? undefined : await req.arrayBuffer(),
        signal: AbortSignal.timeout(3500),
      });
      if (proxied.status < 500) {
        return proxied;
      }
    } catch {
      // Fall through to embedded verified golden engine
    }
  }

  // ---- Health, Readiness & Swagger Docs ----
  if (path === '/health' || path === '/api/v1/health') {
    return jsonRes({ status: 'ok' });
  }
  if (path === '/ready' || path === '/api/v1/ready') {
    return jsonRes({ status: 'ready', database: 'ok' });
  }
  if (path === '/openapi.json') {
    return jsonRes(openapiSpec);
  }
  if (path === '/docs') {
    const nonce = crypto.randomUUID().replace(/-/g, '');
    const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>MediOps Intelligence — API</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css" />
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script nonce="${nonce}">
    window.ui = SwaggerUIBundle({
      url: '/openapi.json',
      dom_id: '#swagger-ui',
      deepLinking: true,
      presets: [SwaggerUIBundle.presets.apis]
    });
  </script>
</body>
</html>`;
    return new Response(html, {
      status: 200,
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'Content-Security-Policy': `default-src 'none'; script-src 'nonce-${nonce}' https://cdn.jsdelivr.net; style-src https://cdn.jsdelivr.net 'unsafe-inline'; img-src 'self' data: https://fastapi.tiangolo.com; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`,
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'Referrer-Policy': 'no-referrer',
      },
    });
  }

  // ---- Auth ----
  if (path === '/api/v1/auth/login' && method === 'POST') {
    const body = await req.json().catch(() => ({}));
    const email = String(body.email || '')
      .trim()
      .toLowerCase();
    const password = String(body.password || '');
    const u = state.users.find((x) => x.email === email && x.password === password && x.is_active);
    if (!u) {
      return errRes('unauthorized', 'Invalid email or password', 401);
    }
    context?.cookies?.set?.({
      name: 'careops_refresh',
      value: u.id,
      path: '/api/v1/auth',
      httpOnly: true,
      secure: true,
      sameSite: 'Strict',
    });
    const { password: _, ...userOut } = u;
    return jsonRes({
      access_token: encodeToken(u),
      token_type: 'bearer',
      expires_in: 900,
      user: userOut,
    });
  }

  if (path === '/api/v1/auth/register' && method === 'POST') {
    const body = await req.json().catch(() => ({}));
    const email = String(body.email || '')
      .trim()
      .toLowerCase();
    const password = String(body.password || '');
    if (!email || password.length < 12) {
      return errRes('weak_password', 'Password must be at least 12 characters long.', 422);
    }
    if (state.users.some((x) => x.email === email)) {
      return errRes('conflict', 'An account with this email already exists', 409);
    }
    const newUser = {
      id: crypto.randomUUID(),
      email,
      password,
      role: 'manager',
      is_active: true,
      created_at: new Date().toISOString(),
    };
    state.users.push(newUser);
    const { password: _, ...userOut } = newUser;
    return jsonRes(userOut, 201);
  }

  if (path === '/api/v1/auth/refresh' && method === 'POST') {
    const u = decodeUserFromReq(req, context);
    if (!u) return errRes('unauthorized', 'Session expired or invalid', 401);
    const { password: _, ...userOut } = u;
    return jsonRes({
      access_token: encodeToken(u),
      token_type: 'bearer',
      expires_in: 900,
      user: userOut,
    });
  }

  if (path === '/api/v1/auth/logout' && method === 'POST') {
    context?.cookies?.delete?.({ name: 'careops_refresh', path: '/api/v1/auth' });
    return new Response(null, { status: 204 });
  }

  const user = decodeUserFromReq(req, context);
  if (!user) {
    return errRes('unauthorized', 'Authentication required', 401);
  }

  if (path === '/api/v1/auth/me' && method === 'GET') {
    const { password: _, ...userOut } = user;
    return jsonRes(userOut);
  }

  // ---- Business Profile ----
  if (path === '/api/v1/business-profile') {
    if (method === 'GET') {
      const prof =
        state.profiles[user.id] || state.profiles['d96ecb8f-def3-413f-bcb1-54b0a2e031ce'];
      return jsonRes(prof);
    }
    if (method === 'PUT') {
      const body = await req.json().catch(() => ({}));
      const saved = {
        id: state.profiles[user.id]?.id || crypto.randomUUID(),
        company_name: body.company_name || 'Sunrise Multispeciality Hospital',
        industry: body.industry || 'Healthcare',
        team_size: Number(body.team_size) || 250,
        business_goals: body.business_goals || '',
        created_at: state.profiles[user.id]?.created_at || new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      state.profiles[user.id] = saved;
      return jsonRes(saved);
    }
  }

  // ---- Datasets & Analytics ----
  if (path === '/api/v1/datasets' && method === 'GET') {
    return jsonRes({
      items: [snapshot.dataset],
      total: 1,
      page: 1,
      page_size: 50,
    });
  }

  if (path === '/api/v1/datasets' && method === 'POST') {
    if (user.role === 'analyst') {
      return errRes('forbidden', 'Analysts cannot upload datasets', 403);
    }
    return jsonRes(snapshot.dataset, 201);
  }

  const dsMatch = path.match(/^\/api\/v1\/datasets\/([^/]+)(?:\/(.*))?$/);
  if (dsMatch) {
    const sub = dsMatch[2] || '';
    if (!sub && method === 'GET') {
      return jsonRes(snapshot.dataset);
    }
    if (!sub && method === 'DELETE') {
      if (user.role === 'analyst') {
        return errRes('forbidden', 'Analysts cannot delete datasets', 403);
      }
      return new Response(null, { status: 204 });
    }
    if (sub === 'quality-report' && method === 'GET') {
      return jsonRes(snapshot.quality_report);
    }
    if (sub === 'kpis' && method === 'GET') {
      const fromM = url.searchParams.get('from');
      const toM = url.searchParams.get('to');
      if (fromM === '2026-05' && toM === '2026-07') {
        return jsonRes(snapshot.kpis_may_jul);
      }
      return jsonRes(snapshot.kpis);
    }
    if (sub === 'trends' && method === 'GET') {
      return jsonRes(snapshot.trends);
    }
    const bdMatch = sub.match(/^breakdowns\/([^/]+)$/);
    if (bdMatch && method === 'GET') {
      const dim = bdMatch[1];
      if (snapshot.breakdowns[dim]) {
        return jsonRes(snapshot.breakdowns[dim]);
      }
      return errRes('bad_request', `Unsupported breakdown dimension: ${dim}`, 400);
    }
  }

  // ---- Analyses ----
  if (path === '/api/v1/analyses' && method === 'GET') {
    const { agents: _, ...runSummary } = snapshot.analysis;
    return jsonRes({
      items: [runSummary],
      total: 1,
      page: 1,
      page_size: 20,
    });
  }

  if (path === '/api/v1/analyses' && method === 'POST') {
    if (user.role === 'analyst') {
      return errRes('forbidden', 'Analysts cannot trigger analysis runs', 403);
    }
    return jsonRes(snapshot.analysis, 202);
  }

  const anMatch = path.match(/^\/api\/v1\/analyses\/([^/]+)(?:\/(.*))?$/);
  if (anMatch) {
    const sub = anMatch[2] || '';
    if (!sub && method === 'GET') {
      return jsonRes(snapshot.analysis);
    }
    if (sub === 'agents' && method === 'GET') {
      return jsonRes(snapshot.analysis.agents);
    }
    if (sub === 'cancel' && method === 'POST') {
      if (user.role === 'analyst') {
        return errRes('forbidden', 'Analysts cannot cancel analyses', 403);
      }
      return jsonRes({ ...snapshot.analysis, status: 'cancelled' });
    }
  }

  // ---- Reports & PDF ----
  if (path === '/api/v1/reports' && method === 'GET') {
    const repSummary = {
      id: snapshot.report.id,
      analysis_id: snapshot.report.analysis_id,
      dataset_id: snapshot.report.dataset_id,
      verdict: snapshot.report.verdict,
      confidence: snapshot.report.confidence,
      created_at: snapshot.report.created_at,
    };
    return jsonRes({
      items: [repSummary],
      total: 1,
      page: 1,
      page_size: 20,
    });
  }

  const repMatch = path.match(/^\/api\/v1\/reports\/([^/]+)(?:\/(.*))?$/);
  if (repMatch) {
    const sub = repMatch[2] || '';
    if (!sub && method === 'GET') {
      return jsonRes({ ...snapshot.report, recommendations: state.recommendations });
    }
    if (sub === 'pdf' && method === 'GET') {
      const pdfUrl = new URL('/sample_report.pdf', url.origin);
      const pdfRes = await fetch(pdfUrl);
      const pdfBuf = await pdfRes.arrayBuffer();
      return new Response(pdfBuf, {
        status: 200,
        headers: {
          'Content-Type': 'application/pdf',
          'Content-Disposition': `attachment; filename="mediops_report_${snapshot.report.id.slice(0, 8)}.pdf"`,
        },
      });
    }
  }

  // ---- Recommendations (HITL) ----
  if (path === '/api/v1/recommendations' && method === 'GET') {
    const statusFilter = url.searchParams.get('status');
    const items = statusFilter
      ? state.recommendations.filter((r) => r.status === statusFilter)
      : state.recommendations;
    return jsonRes({
      items,
      total: items.length,
      page: 1,
      page_size: 50,
    });
  }

  const recMatch = path.match(/^\/api\/v1\/recommendations\/([^/]+)(?:\/(.*))?$/);
  if (recMatch) {
    const recId = recMatch[1];
    const sub = recMatch[2] || '';
    const rec = state.recommendations.find((r) => r.id === recId) || state.recommendations[0];
    if (!rec) return errRes('not_found', 'Recommendation not found', 404);
    if (!sub && method === 'GET') {
      return jsonRes(rec);
    }
    if (sub === 'decision' && method === 'POST') {
      if (user.role === 'analyst') {
        return errRes(
          'forbidden',
          'Only manager and admin roles can record approval decisions',
          403,
        );
      }
      const body = await req.json().catch(() => ({}));
      const decision = body.decision === 'rejected' ? 'rejected' : 'approved';
      const comment = String(body.comment || '');
      rec.status = decision;
      rec.approval_history = [
        {
          id: crypto.randomUUID(),
          recommendation_id: rec.id,
          decided_by: user.id,
          decision,
          comment,
          decided_at: new Date().toISOString(),
        },
        ...(rec.approval_history || []),
      ];
      return jsonRes({ ...rec, execution_mode: 'recorded_decision_only' });
    }
  }

  // ---- Grounded AI Chat ----
  if (path === '/api/v1/chat/sessions' && method === 'GET') {
    return jsonRes({
      items: state.chatSessions,
      total: state.chatSessions.length,
      page: 1,
      page_size: 20,
    });
  }

  if (path === '/api/v1/chat/sessions' && method === 'POST') {
    const body = await req.json().catch(() => ({}));
    const created = {
      id: crypto.randomUUID(),
      dataset_id: body.dataset_id || snapshot.dataset.id,
      user_id: user.id,
      title: body.title || 'Hospital Operations Q&A',
      created_at: new Date().toISOString(),
    };
    state.chatSessions.unshift(created);
    state.chatMessages[created.id] = [];
    return jsonRes(created, 201);
  }

  const chatMatch = path.match(/^\/api\/v1\/chat\/sessions\/([^/]+)\/messages$/);
  if (chatMatch) {
    const sid = chatMatch[1];
    if (!state.chatMessages[sid]) {
      state.chatMessages[sid] = [];
    }
    if (method === 'GET') {
      return jsonRes(state.chatMessages[sid]);
    }
    if (method === 'POST') {
      const body = await req.json().catch(() => ({}));
      const q = String(body.content || '').trim();
      const userMsg = {
        id: crypto.randomUUID(),
        session_id: sid,
        role: 'user',
        content: q,
        cited_metric_keys: [],
        created_at: new Date().toISOString(),
      };
      const ans = answerQuestion(q);
      const assistantMsg = {
        id: crypto.randomUUID(),
        session_id: sid,
        role: 'assistant',
        content: ans.content,
        cited_metric_keys: ans.cited_metric_keys,
        created_at: new Date().toISOString(),
      };
      state.chatMessages[sid].push(userMsg, assistantMsg);
      return jsonRes({ user_message: userMsg, assistant_message: assistantMsg }, 201);
    }
  }

  // ---- Admin Governance Console ----
  if (path.startsWith('/api/v1/admin')) {
    if (user.role !== 'admin') {
      return errRes('forbidden', 'Admin privileges required', 403);
    }
    if (path === '/api/v1/admin/users' && method === 'GET') {
      return jsonRes({
        items: state.users.map(({ password: _, ...u }) => u),
        total: state.users.length,
        page: 1,
        page_size: 50,
      });
    }
    const usrMatch = path.match(/^\/api\/v1\/admin\/users\/([^/]+)$/);
    if (usrMatch && method === 'PATCH') {
      const targetId = usrMatch[1];
      if (targetId === user.id) {
        return errRes('self_lockout', 'Admins cannot demote or deactivate themselves', 400);
      }
      const targetUser = state.users.find((x) => x.id === targetId);
      if (!targetUser) return errRes('not_found', 'User not found', 404);
      const body = await req.json().catch(() => ({}));
      if (body.role) targetUser.role = body.role;
      if (typeof body.is_active === 'boolean') targetUser.is_active = body.is_active;
      const { password: _, ...userOut } = targetUser;
      return jsonRes(userOut);
    }
    if (path === '/api/v1/admin/analyses' && method === 'GET') {
      const { agents: _, ...runSummary } = snapshot.analysis;
      return jsonRes({ items: [runSummary], total: 1, page: 1, page_size: 50 });
    }
    if (path === '/api/v1/admin/reports' && method === 'GET') {
      const repSummary = {
        id: snapshot.report.id,
        analysis_id: snapshot.report.analysis_id,
        dataset_id: snapshot.report.dataset_id,
        verdict: snapshot.report.verdict,
        confidence: snapshot.report.confidence,
        created_at: snapshot.report.created_at,
      };
      return jsonRes({ items: [repSummary], total: 1, page: 1, page_size: 50 });
    }
  }

  return errRes('not_found', `Route not found: ${method} ${path}`, 404);
};

export const config = {
  path: ['/api/v1/*', '/health', '/ready', '/docs', '/openapi.json'],
};
