/* Love Mahomies odds board. Reads data/latest.json and data/history.json; no build step. */
(async function () {
  const app = document.getElementById('app');
  const $ = (s, el = document) => el.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  let D, H;
  try {
    [D, H] = await Promise.all(['data/latest.json', 'data/history.json'].map(u => fetch(u + '?t=' + Date.now()).then(r => { if (!r.ok) throw new Error(u); return r.json(); })));
  } catch (e) {
    app.innerHTML = '<p class="empty">The odds data has not been published yet. Run the "Update odds" workflow in the repository\'s Actions tab, then reload.</p>';
    return;
  }
  const T = D.teams_meta, ids = Object.keys(T);
  const snaps = H.snapshots || [];
  let vig = 0;
  try { vig = parseFloat(localStorage.getItem('vig') || '0') || 0; } catch (e) {}
  const vigSel = $('#vig'); vigSel.value = String(vig);
  vigSel.addEventListener('change', () => { vig = parseFloat(vigSel.value); try { localStorage.setItem('vig', vig); } catch (e) {} route(); });

  // ---------- formatting ----------
  const pct = (p, d = 1) => p == null ? '–' : (p > 0 && p < 0.001 ? '<0.1' : (100 * p).toFixed(p >= 0.9995 ? 0 : d)) + '%';
  function price(p) {              // American odds, with the chosen vig applied
    if (p == null) return '–';
    const q = Math.min(p * (1 + vig), 0.995);
    if (q < 0.0005) return 'Off';
    const a = q >= 0.5 ? -100 * q / (1 - q) : 100 * (1 - q) / q;
    const r = Math.abs(a) >= 1000 ? Math.round(a / 50) * 50 : Math.abs(a) >= 300 ? Math.round(a / 5) * 5 : Math.round(a);
    return (r > 0 ? '+' : '−') + Math.abs(r).toLocaleString('en-US');
  }
  const teamLink = id => `<a class="team-link" href="#/team/${id}"><span class="dot" style="background:${T[id].color}"></span>${esc(T[id].name)}</a>`;
  const rec = t => `${t.w}-${t.l}${t.t ? '-' + t.t : ''}`;
  function delta(now, before, unit = ' pts') {
    if (before == null) return '<span class="flat">–</span>';
    const d = 100 * (now - before);
    if (Math.abs(d) < 0.05) return '<span class="flat">0.0</span>';
    return `<span class="${d > 0 ? 'up' : 'down'}">${d > 0 ? '▲' : '▼'} ${Math.abs(d).toFixed(1)}</span>`;
  }
  const series = (id, key) => snaps.map(s => ({ x: s.week, y: s.teams[id] ? s.teams[id][key] : null }));
  const prevSnap = snaps.length > 1 ? snaps[snaps.length - 2] : null;
  const weekLabel = D.season_over ? 'Final' : `Week ${D.week}`;

  // ---------- charts ----------
  function spark(vals, color) {
    const v = vals.filter(p => p.y != null); if (v.length < 2) return '';
    const w = 96, h = 26, max = Math.max(...v.map(p => p.y), 0.02), x = i => 2 + i * (w - 4) / (v.length - 1), y = p => h - 3 - (h - 6) * p / max;
    return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true"><path d="${v.map((p, i) => (i ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(p.y).toFixed(1)).join('')}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round"/><circle cx="${x(v.length - 1)}" cy="${y(v[v.length - 1].y)}" r="2.6" fill="${color}"/></svg>`;
  }
  function lineChart(lines, opt = {}) {   // lines: [{id,name,color,pts:[{x,y}]}], y in 0..1 unless opt.raw
    const W = 860, Hh = opt.h || 380, m = { l: 44, r: opt.labels === false ? 16 : 168, t: 14, b: 34 };
    const xs = [...new Set(lines.flatMap(l => l.pts.map(p => p.x)))].sort((a, b) => a - b);
    if (xs.length < 1) return '<p class="empty">No history yet.</p>';
    const ymax = opt.raw ? Math.ceil(Math.max(...lines.flatMap(l => l.pts.map(p => p.y || 0))) + 0.5) : [0.1, 0.2, 0.4, 0.6, 0.8, 1].find(v => v >= Math.max(...lines.flatMap(l => l.pts.map(p => p.y || 0))) * 1.04) || 1;
    const X = x => xs.length === 1 ? m.l + (W - m.l - m.r) / 2 : m.l + (W - m.l - m.r) * (x - xs[0]) / (xs[xs.length - 1] - xs[0]);
    const Y = y => m.t + (Hh - m.t - m.b) * (1 - y / ymax);
    const ticks = [0, .25, .5, .75, 1].map(f => f * ymax);
    let g = ticks.map(t => `<line class="grid" x1="${m.l}" x2="${W - m.r}" y1="${Y(t)}" y2="${Y(t)}"/><text x="${m.l - 8}" y="${Y(t) + 4}" text-anchor="end">${opt.raw ? t.toFixed(1) : Math.round(t * 100) + '%'}</text>`).join('');
    g += xs.map(x => `<text x="${X(x)}" y="${Hh - 10}" text-anchor="middle">Wk ${x}</text>`).join('');
    // end labels, nudged apart
    const ends = lines.map(l => ({ l, y: Y(l.pts[l.pts.length - 1].y || 0) })).sort((a, b) => a.y - b.y);
    for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 14) ends[i].y = ends[i - 1].y + 14;
    for (let i = ends.length - 1; i > 0; i--) { if (ends[i].y > Hh - m.b + 6) ends[i].y = Hh - m.b + 6; if (ends[i].y - ends[i - 1].y < 14) ends[i - 1].y = ends[i].y - 14; }
    const body = lines.map(l => {
      const pts = l.pts.filter(p => p.y != null);
      const d = pts.map((p, i) => (i ? 'L' : 'M') + X(p.x).toFixed(1) + ' ' + Y(p.y).toFixed(1)).join('');
      const last = pts[pts.length - 1];
      return `<path class="s" data-id="${l.id}" d="${d}" stroke="${l.color}"><title>${esc(l.name)}</title></path>` +
        pts.map(p => `<circle data-id="${l.id}" cx="${X(p.x)}" cy="${Y(p.y)}" r="${pts.length === 1 ? 4 : 2.4}" fill="${l.color}"><title>${esc(l.name)}, week ${p.x}: ${opt.raw ? p.y.toFixed(2) : pct(p.y)}</title></circle>`).join('') +
        (opt.labels === false ? '' : `<text class="lab" data-id="${l.id}" x="${W - m.r + 10}" y="${ends.find(e => e.l === l).y + 4}" fill="${l.color}" style="fill:${l.color}">${esc(l.name.length > 19 ? l.name.slice(0, 18) + '…' : l.name)} ${opt.raw ? last.y.toFixed(1) : pct(last.y, 0)}</text>`);
    }).join('');
    return `<svg viewBox="0 0 ${W} ${Hh}" role="img" aria-label="${esc(opt.label || 'Odds by week')}">${g}${body}</svg>`;
  }
  function wireChart(box, onPick) {       // hover or tap a line / legend chip to isolate it
    const set = id => { box.classList.toggle('has-on', !!id); box.querySelectorAll('[data-id]').forEach(n => n.classList.toggle('on', n.dataset.id === id)); box.querySelectorAll('.legend button').forEach(b => b.setAttribute('aria-pressed', b.dataset.id === id)); };
    let pinned = null;
    box.addEventListener('pointerover', e => { const n = e.target.closest('svg [data-id]'); if (n && !pinned) set(n.dataset.id); });
    box.addEventListener('pointerout', e => { if (!pinned && e.target.closest('svg [data-id]')) set(null); });
    box.addEventListener('click', e => { const n = e.target.closest('[data-id]'); if (!n) return; pinned = pinned === n.dataset.id ? null : n.dataset.id; set(pinned); if (onPick) onPick(pinned); });
  }

  // ---------- views ----------
  const METRICS = { title: 'Win the title', playoffs: 'Make the playoffs', bye: 'Earn the #1 seed', final: 'Reach the final', exp_wins: 'Expected wins' };
  let boardMetric = 'title';

  function viewBoard() {
    const rows = ids.map(id => ({ id, ...D.teams[id] })).sort((a, b) => b.title - a.title || b.playoffs - a.playoffs);
    const fav = rows[0];
    const mover = prevSnap ? rows.map(r => ({ r, d: r.title - (prevSnap.teams[r.id]?.title ?? r.title) })).sort((a, b) => Math.abs(b.d) - Math.abs(a.d))[0] : null;
    const lede = D.season_over
      ? `${esc(T[fav.id].name)} won the ${D.league.season} title.`
      : `${esc(T[fav.id].name)} leads the board at ${pct(fav.title)} to win it all.` + (mover && Math.abs(mover.d) >= 0.005 ? ` Biggest move since last week: ${esc(T[mover.r.id].name)}, ${mover.d > 0 ? 'up' : 'down'} ${Math.abs(100 * mover.d).toFixed(1)} points.` : '');
    app.innerHTML = `<h1>${esc(D.league.name)} title odds, ${weekLabel.toLowerCase() === 'final' ? 'final' : weekLabel}</h1>
      <p class="lede">${lede}</p>
      <div class="scroll"><table class="board">
        <thead><tr><th class="l" colspan="2">Team</th><th class="hm">Record</th><th class="hm">Points for</th><th>Playoffs</th><th class="hm">#1 seed</th><th>Title</th><th>Price</th><th class="hm">Since last week</th><th class="l hm">Title trend</th></tr></thead>
        <tbody>${rows.map((r, i) => `<tr data-id="${r.id}"><td class="rank">${i + 1}</td><td class="l">${teamLink(r.id)}<span class="sub rec-m"> ${rec(r)}</span></td><td class="hm">${rec(r)}</td><td class="hm">${r.pf.toFixed(1)}</td>
          <td>${pct(r.playoffs)}</td><td class="hm">${pct(r.bye)}</td><td><b>${pct(r.title)}</b></td><td class="price ${i === 0 ? 'fav' : ''}">${price(r.title)}</td>
          <td class="hm">${delta(r.title, prevSnap?.teams[r.id]?.title)}</td><td class="l hm">${spark(series(r.id, 'title'), T[r.id].color)}</td></tr>`).join('')}</tbody>
      </table></div>
      <h2>How the odds have moved</h2>
      <div class="row"><div class="seg" role="group" aria-label="Chart metric">${Object.entries(METRICS).map(([k, v]) => `<button data-m="${k}" aria-pressed="${k === boardMetric}">${v}</button>`).join('')}</div></div>
      <div class="chart" id="trend"></div>
      <p class="sub">Each point is the model's estimate going into that week. Hover or tap a line to isolate a team.${snaps.some(s => s.rebuilt) ? ' Weeks before the site launched were rebuilt after the fact and are approximate.' : ''}</p>`;
    const trend = $('#trend');
    const draw = () => {
      const raw = boardMetric === 'exp_wins';
      trend.innerHTML = lineChart(ids.map(id => ({ id, name: T[id].name, color: T[id].color, pts: series(id, boardMetric) })), { raw, label: METRICS[boardMetric] + ' by week' }) +
        `<div class="legend">${ids.map(id => `<button data-id="${id}" aria-pressed="false"><span class="dot" style="background:${T[id].color}"></span>${esc(T[id].name)}</button>`).join('')}</div>`;
    };
    draw();
    wireChart(trend, id => app.querySelectorAll('.board tr[data-id]').forEach(tr => tr.classList.toggle('is-on', tr.dataset.id === id)));
    app.querySelector('.seg').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; boardMetric = b.dataset.m; app.querySelectorAll('.seg button').forEach(x => x.setAttribute('aria-pressed', x === b)); trend.classList.remove('has-on'); draw(); });
  }

  let weekPick = null, h2hA = null, h2hB = null;
  function gameCard(g) {
    const pa = 1 - g.p_home, ws = D.week_scores, isNow = g.week === D.week;
    const side = (id, p, proj, cls) => `<div class="side ${cls}">${teamLink(id)}<div class="pct">${pct(p, 0)}</div><div class="ml">${price(p)}</div>
      <div class="sub">Projected ${proj.toFixed(1)}${isNow && ws[id] ? ` (likely ${ws[id].p10.toFixed(0)} to ${ws[id].p90.toFixed(0)})` : ''}</div></div>`;
    return `<div class="game"><div class="sides">${side(g.away, pa, g.proj_away, '')}<div class="vs">at</div>${side(g.home, g.p_home, g.proj_home, 'r')}</div>
      <div class="split" aria-hidden="true"><i style="width:${100 * pa}%;background:${T[g.away].color}"></i><i style="width:${100 * g.p_home}%;background:${T[g.home].color}"></i></div></div>`;
  }
  function viewWeek() {
    const weeks = [...new Set(D.games.map(g => g.week))].sort((a, b) => a - b);
    const past = [...new Set(D.results.map(g => g.week))].sort((a, b) => a - b);
    if (weekPick == null || ![...weeks, ...past].includes(weekPick)) weekPick = weeks[0] ?? past[past.length - 1];
    const opts = [...past, ...weeks].map(w => `<option value="${w}" ${w === weekPick ? 'selected' : ''}>Week ${w}${w === D.week ? ' (this week)' : w < D.week ? ' (final)' : ''}</option>`).join('');
    let body;
    if (weeks.includes(weekPick)) body = D.games.filter(g => g.week === weekPick).map(gameCard).join('');
    else body = D.results.filter(g => g.week === weekPick).map(g => `<div class="game"><div class="sides">
        <div class="side">${teamLink(g.away)}<div class="result ${g.as > g.hs ? '' : 'flat'}">${g.as.toFixed(2)}</div></div><div class="vs">at</div>
        <div class="side r">${teamLink(g.home)}<div class="result ${g.hs > g.as ? '' : 'flat'}">${g.hs.toFixed(2)}</div></div></div></div>`).join('');
    const hasH2h = Object.keys(D.h2h || {}).length > 0;
    h2hA = h2hA || ids[0]; h2hB = h2hB || ids[1];
    const sel = (id, v) => `<select class="pick" id="${id}">${ids.map(t => `<option value="${t}" ${t === v ? 'selected' : ''}>${esc(T[t].name)}</option>`).join('')}</select>`;
    app.innerHTML = `<h1>Matchup odds</h1>
      <p class="lede">Win chances and moneylines for every game left on the schedule. Later weeks shift as rosters and projections change.</p>
      <div class="row"><label for="wk" class="sub">Week</label><select class="pick" id="wk">${opts}</select></div>
      ${body || '<p class="empty">No games this week.</p>'}
      ${hasH2h ? `<h2>Any two teams, this week</h2><p class="lede">Pick a pair to see who would win if they played in week ${D.week}, whether or not they are scheduled to.</p>
        <div class="row">${sel('ha', h2hA)}<span class="sub">against</span>${sel('hb', h2hB)}</div><div id="h2h"></div>` : ''}`;
    $('#wk').addEventListener('change', e => { weekPick = +e.target.value; viewWeek(); });
    if (hasH2h) {
      const show = () => {
        const p = h2hA === h2hB ? null : D.h2h[h2hA][h2hB];
        $('#h2h').innerHTML = p == null ? '<p class="empty">Pick two different teams.</p>' :
          gameCard({ week: D.week, away: h2hA, home: h2hB, p_home: 1 - p, proj_away: D.week_scores[h2hA].mean, proj_home: D.week_scores[h2hB].mean }).replace('>at<', '>vs<');
      };
      $('#ha').addEventListener('change', e => { h2hA = e.target.value; show(); });
      $('#hb').addEventListener('change', e => { h2hB = e.target.value; show(); });
      show();
    }
  }

  function viewTeams() {
    const rows = ids.map(id => ({ id, ...D.teams[id] })).sort((a, b) => b.playoffs - a.playoffs || b.title - a.title);
    app.innerHTML = `<h1>Teams</h1><p class="lede">Pick a team to see its odds history, remaining schedule and roster outlook.</p>
      <div class="scroll"><table><thead><tr><th class="l">Team</th><th>Record</th><th>Expected wins</th><th>Playoffs</th><th>Reach final</th><th>Title</th><th class="l">Playoff trend</th></tr></thead><tbody>
      ${rows.map(r => `<tr><td class="l">${teamLink(r.id)}</td><td>${rec(r)}</td><td>${r.exp_wins.toFixed(1)}</td><td>${pct(r.playoffs)}</td><td>${pct(r.final)}</td><td>${pct(r.title)}</td><td class="l">${spark(series(r.id, 'playoffs'), T[r.id].color)}</td></tr>`).join('')}
      </tbody></table></div>
      <h2>Luck check</h2>
      <p class="lede">All-play record is how each team would have done playing every other team every week. The gap to the real record is schedule luck.</p>
      <div class="scroll"><table><thead><tr><th class="l">Team</th><th>Record</th><th>All-play record</th><th>All-play win rate</th><th>Wins it deserved</th><th>Luck, in wins</th><th>Points against</th></tr></thead><tbody>
      ${luckRows().map(x => `<tr><td class="l">${teamLink(x.id)}</td><td>${rec(D.teams[x.id])}</td><td>${x.w}-${x.l}</td><td>${pct(x.rate, 0)}</td><td>${x.deserved.toFixed(1)}</td><td class="${x.luck > 0.3 ? 'up' : x.luck < -0.3 ? 'down' : ''}"><b>${x.luck > 0 ? '+' : x.luck < 0 ? '−' : ''}${Math.abs(x.luck).toFixed(1)}</b></td><td>${D.teams[x.id].pa.toFixed(1)}</td></tr>`).join('')}
      </tbody></table></div>`;
  }
  function luckRows() {
    const byWeek = {};
    D.results.forEach(g => { (byWeek[g.week] = byWeek[g.week] || []).push([String(g.home), g.hs], [String(g.away), g.as]); });
    const acc = {}; ids.forEach(id => acc[id] = { id, w: 0, l: 0, games: 0 });
    Object.values(byWeek).forEach(list => list.forEach(([id, s]) => { if (!acc[id]) return; acc[id].games++; list.forEach(([o, so]) => { if (o !== id) { if (s > so) acc[id].w++; else if (s < so) acc[id].l++; } }); }));
    return Object.values(acc).map(x => { const rate = x.w + x.l ? x.w / (x.w + x.l) : 0, deserved = rate * x.games; return Object.assign(x, { rate, deserved, luck: D.teams[x.id].w + 0.5 * (D.teams[x.id].t || 0) - deserved }); }).sort((a, b) => b.luck - a.luck);
  }

  function sosChip(v) {
    if (v == null) return '<span class="sub">–</span>';
    const lab = v >= 1.04 ? 'Easy' : v <= 0.96 ? 'Hard' : 'Even';
    return `<span class="chip ${lab.toLowerCase()}" title="Fantasy points this position scores against these defenses, vs average: ${(100 * (v - 1)).toFixed(0)}%">${lab}</span>`;
  }
  function trendTag(p) {
    const d = p.pos === 'QB' || p.pos === 'K' || p.pos === 'D/ST' ? null : (p.tgt_delta != null && Math.abs(p.tgt_delta) >= 0.05 ? p.tgt_delta : (p.snap_delta != null && Math.abs(p.snap_delta) >= 0.12 ? p.snap_delta : null));
    if (d == null) return '';
    return `<span class="tag ${d > 0 ? 'upt' : 'dnt'}" title="Share of targets or snaps, last two games vs the four before">${d > 0 ? 'Usage up' : 'Usage down'}</span>`;
  }
  function rosterTable(players, withTeam) {
    const maxW = Math.max(1, ...players.flatMap(p => p.weeks)), maxC = Math.max(1, ...players.map(p => p.ceil));
    const hasAdv = players.some(p => p.boom != null);
    return `<div class="scroll"><table><thead><tr><th class="l">Player</th>${withTeam ? '<th class="l">Fantasy team</th>' : ''}<th>Pos rank</th><th>This week</th><th class="l">Floor to ceiling</th>${hasAdv ? '<th>Boom</th><th>Bust</th><th class="l">Matchup</th><th class="l">Schedule left</th>' : ''}<th>Per game, rest of season</th><th>Total, rest of season</th><th class="l">By week</th></tr></thead><tbody>
      ${players.map(p => `<tr><td class="l"><b>${esc(p.name)}</b> <span class="sub">${p.pos}, ${esc(p.nfl)}${p.opp ? ' vs ' + esc(p.opp) : p.wk ? '' : (p.bye === D.week ? ', bye' : '')}</span>${p.slot === 'IR' ? '<span class="tag out">IR</span>' : p.status ? `<span class="tag ${/OUT|RESERVE|SUSP/.test(p.status) ? 'out' : ''}">${esc(p.status[0] + p.status.slice(1).toLowerCase().replace('_', ' '))}</span>` : ''}${trendTag(p)}</td>
        ${withTeam ? `<td class="l">${teamLink(p.team)}</td>` : ''}<td>${p.pos}${p.pos_rank}</td><td><b>${p.wk ? p.wk.toFixed(1) : '–'}</b></td>
        <td class="l">${p.wk ? `<div class="range" title="${p.floor} to ${p.ceil} points in 8 of 10 games"><i style="left:${100 * Math.max(0, p.floor) / maxC}%;width:${100 * (p.ceil - Math.max(0, p.floor)) / maxC}%"></i><b style="left:${100 * p.wk / maxC}%"></b></div><span class="sub">${p.floor} to ${p.ceil}</span>` : '<span class="sub">Not playing</span>'}</td>
        ${hasAdv ? `<td>${p.boom != null ? pct(p.boom, 0) : '–'}</td><td>${p.bust != null ? pct(p.bust, 0) : '–'}</td><td class="l">${p.wk ? sosChip(p.matchup) : '<span class="sub">–</span>'}</td><td class="l">${sosChip(p.sos)}</td>` : ''}
        <td>${p.ros_avg.toFixed(1)}</td><td>${p.ros_total.toFixed(0)}</td>
        <td class="l"><span class="mini" title="Projected points, week ${D.week} to ${D.league.last_week}">${p.weeks.map((w, k) => `<i class="${w ? '' : 'z'}" title="Week ${D.week + k}${p.opps && p.opps[k] ? ' vs ' + p.opps[k] : ' (bye)'}: ${w}" style="height:${Math.max(2, 20 * w / maxW)}px"></i>`).join('')}</span></td></tr>`).join('')}
      </tbody></table></div>${hasAdv ? '<p class="sub">Boom and bust are the chances of a top-tier week or a dud for the position. Matchup and schedule compare the defenses he faces with average.</p>' : ''}`;
  }

  function viewTeam(id) {
    if (!T[id]) return viewTeams();
    const t = D.teams[id], order = ['QB', 'RB', 'WR', 'TE', 'K', 'D/ST'];
    const players = D.players.filter(p => String(p.team) === id).sort((a, b) => order.indexOf(a.pos) - order.indexOf(b.pos) || b.ros_total - a.ros_total);
    const seedTop = t.seed_dist.map((p, i) => ({ p, i })).sort((a, b) => b.p - a.p)[0];
    const sched = [...D.results.filter(g => g.home == id || g.away == id).map(g => { const home = g.home == id, us = home ? g.hs : g.as, them = home ? g.as : g.hs; return { week: g.week, opp: home ? g.away : g.home, cell: `<b class="${us > them ? 'up' : 'down'}">${us > them ? 'W' : us < them ? 'L' : 'T'}</b> ${us.toFixed(1)} to ${them.toFixed(1)}`, line: '' }; }),
      ...D.games.filter(g => g.home == id || g.away == id).map(g => { const home = g.home == id, p = home ? g.p_home : 1 - g.p_home; return { week: g.week, opp: home ? g.away : g.home, cell: `<div class="bar"><i style="width:${100 * p}%"></i></div>`, p, line: price(p) }; })].sort((a, b) => a.week - b.week);
    app.innerHTML = `<p class="sub"><a href="#/teams">All teams</a></p>
      <h1><span class="dot" style="background:${T[id].color};width:.5em;height:.5em;margin-right:.25em"></span>${esc(T[id].name)}</h1>
      <div class="stats">
        <div><b>${rec(t)}</b><span>Record</span></div><div><b>${pct(t.playoffs, 0)}</b><span>Make the playoffs ${delta(t.playoffs, prevSnap?.teams[id]?.playoffs)}</span></div>
        <div><b>${pct(t.title)}</b><span>Win the title ${delta(t.title, prevSnap?.teams[id]?.title)}</span></div><div><b>${price(t.title)}</b><span>Title price</span></div>
        <div><b>${t.exp_wins.toFixed(1)}</b><span>Expected wins</span></div><div><b>#${seedTop.i + 1}</b><span>Most likely seed (${pct(seedTop.p, 0)})</span></div>
      </div>
      <div class="cols"><div><h2>Odds by week</h2><div class="chart">${lineChart([
        { id: 'p', name: 'Playoffs', color: T[id].color, pts: series(id, 'playoffs') }, { id: 'f', name: 'Reach final', color: 'var(--muted)', pts: series(id, 'final') },
        { id: 't', name: 'Title', color: 'var(--gold)', pts: series(id, 'title') }], { h: 300, label: T[id].name + ' odds by week' })}</div></div>
      <div><h2>Schedule</h2><div class="scroll"><table><thead><tr><th>Wk</th><th class="l">Opponent</th><th class="l">Result or win chance</th></tr></thead><tbody>
        ${sched.map(s => `<tr><td>${s.week}</td><td class="l">${teamLink(s.opp)}</td><td class="l">${s.cell}${s.p != null ? ` <span class="sub">${pct(s.p, 0)}, ${s.line}</span>` : ''}</td></tr>`).join('') || '<tr><td colspan="3" class="l">No games.</td></tr>'}
      </tbody></table></div></div></div>
      <h2>Roster outlook</h2>
      <p class="lede">Projections are scaled to how this league's starters have actually scored. Floor and ceiling cover 8 of 10 outcomes.</p>
      ${players.length ? rosterTable(players, false) : '<p class="empty">The season is over.</p>'}
      <h2>Seeding chances</h2>
      <div class="scroll"><table><thead><tr>${t.seed_dist.map((_, i) => `<th>#${i + 1}</th>`).join('')}</tr></thead><tbody><tr>${t.seed_dist.map((p, i) => `<td style="${i < D.league.playoff_teams ? '' : 'color:var(--muted)'}">${p >= 0.0005 ? pct(p, 0) : '–'}</td>`).join('')}</tr></tbody></table></div>
      <p class="sub">The top ${D.league.playoff_teams} seeds make the playoffs.</p>`;
  }

  let pPos = 'All', pQ = '', pSort = 'ros_total';
  function viewPlayers() {
    const posList = ['All', 'QB', 'RB', 'WR', 'TE', 'K', 'D/ST'];
    app.innerHTML = `<h1>Player outlook</h1><p class="lede">Every rostered player, ranked by projected points for the rest of the fantasy season (through week ${D.league.last_week}).</p>
      <div class="row"><div class="seg" role="group" aria-label="Position">${posList.map(p => `<button data-p="${p}" aria-pressed="${p === pPos}">${p}</button>`).join('')}</div>
      <input class="pick" id="q" type="search" placeholder="Find a player" aria-label="Find a player" value="${esc(pQ)}">
      <select class="pick" id="ps" aria-label="Sort by"><option value="ros_total">Sort: rest of season total</option><option value="ros_avg">Sort: per game</option><option value="wk">Sort: this week</option><option value="ceil">Sort: ceiling</option><option value="boom">Sort: boom chance</option><option value="sos">Sort: easiest schedule</option></select></div><div id="plist"></div>`;
    $('#ps').value = pSort;
    const draw = () => {
      const list = D.players.filter(p => (pPos === 'All' || p.pos === pPos) && (!pQ || p.name.toLowerCase().includes(pQ.toLowerCase()))).sort((a, b) => (b[pSort] ?? -1) - (a[pSort] ?? -1)).slice(0, 150);
      $('#plist').innerHTML = list.length ? rosterTable(list, true) : '<p class="empty">No players match. Clear the search or pick another position.</p>';
    };
    draw();
    app.querySelector('.seg').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; pPos = b.dataset.p; app.querySelectorAll('.seg button').forEach(x => x.setAttribute('aria-pressed', x === b)); draw(); });
    $('#q').addEventListener('input', e => { pQ = e.target.value; draw(); });
    $('#ps').addEventListener('change', e => { pSort = e.target.value; draw(); });
  }

  function viewAbout() {
    const M = D.model, bp = M && M.by_pos ? Object.entries(M.by_pos) : [];
    const nm = { espn: 'ESPN', sleeper: 'Sleeper', usage: 'Usage model', blend: 'Blend' };
    const report = bp.length ? `<h2>How the sources have done this season</h2>
      <p>Each source is scored against what rostered players actually did in weeks ${M.weeks[0]} to ${M.weeks[M.weeks.length - 1]}. Lower error is better. The weights are refitted on every update and pulled halfway toward a fixed starting point so one odd week cannot swing them.</p>
      <div class="scroll"><table><thead><tr><th class="l">Position</th><th>Player-weeks</th><th class="l">Average miss, points</th><th class="l">Weights now</th></tr></thead><tbody>
      ${bp.map(([pos, r]) => `<tr><td class="l">${pos}</td><td>${r.n}</td><td class="l">${r.rmse ? Object.entries(r.rmse).map(([k, v]) => `${nm[k] || k} ${v}`).join(', ') : '–'}</td><td class="l">${Object.entries(r.weights || {}).map(([k, v]) => `${nm[k] || k} ${Math.round(100 * v)}%`).join(', ')}</td></tr>`).join('')}
      </tbody></table></div>
      <p class="sub">Player stats through NFL week ${M.stats_through_week ?? '–'}. Sportsbook lines this week: ${M.vegas_games} games, ${M.props_players} players with props.</p>` : '';
    app.innerHTML = `<h1>How it works</h1><div class="prose">
      <p>Every update plays out the rest of the season ${D.sims.toLocaleString('en-US')} times. A team's odds are the share of those seasons in which it made the playoffs, reached the final or won the title.</p>
      <h2>What goes into a player's projection</h2><ul>
        <li><b>ESPN and Sleeper weekly projections</b>, re-scored under this league's rules. They account for the opponent, byes and expected injury returns.</li>
        <li><b>A usage model</b> built from every NFL box score this season: recent pass attempts, carries and targets count most, while yards per touch and touchdown rates are pulled toward what is normal for the position. That discounts hot streaks and rewards rising workloads.</li>
        <li><b>Sportsbook lines</b> for the current week: player props for yards, catches, passing touchdowns and kicking points, plus each NFL team's implied point total.</li>
        <li><b>A reality check.</b> Everything is scaled to what this league's starters have actually scored.</li></ul>
      <h2>Ceilings, floors and busts</h2><ul>
        <li>Each player's week is drawn from a curve with a floor near zero and a long upside tail. How wide it is comes from his own game log over two seasons, so boom-or-bust players swing more than steady ones.</li>
        <li>Quarterbacks rise and fall with their own receivers and kicker; a defense does worse when the offense it faces has a good day.</li>
        <li>Players can get hurt and miss time. Questionable players sit some of the time.</li>
        <li><b>Matchup and schedule</b> ratings show how many fantasy points each defense gives up to the position, compared with average. They are shown for context; ESPN and Sleeper projections already price the matchup in, and adding it a second time made the backtest worse.</li></ul>
      ${report}
      <h2>Reading the prices</h2>
      <p>Prices are American odds. +400 means a $100 bet would win $400; −150 means you would bet $150 to win $100. "Fair" converts the chance straight to a price. The vig options show what a sportsbook would post after taking its cut.</p>
      <h2>Limits</h2><ul>
        <li>Future trades and waiver pickups are not predicted.</li>
        <li>Odds are set before each week's games and do not move during them.</li>
        <li>Sportsbook lines only exist for the current week; later weeks rely on the other sources.</li>
        <li>History from before the site launched was rebuilt afterwards and is approximate.</li>
        <li>The sportsbook is play money, for league fun only.</li></ul></div>`;
  }

  // ---------- sportsbook (paper trading) ----------
  const MARKETS = { title: 'Win the title', playoffs: 'Make the playoffs', bye: 'Earn the #1 seed', final: 'Reach the final', game: 'This week\'s games' };
  const BOOK = { cfg: null, bets: [], me: null, market: 'title', remote: false, error: null };
  const money = (v, sign) => (sign && v > 0 ? '+' : v < 0 ? '−' : '') + '$' + Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: Math.abs(v) % 1 ? 2 : 0, maximumFractionDigits: 2 });
  function am(q) { const a = q >= 0.5 ? -100 * q / (1 - q) : 100 * (1 - q) / q; const r = Math.abs(a) >= 1000 ? Math.round(a / 50) * 50 : Math.abs(a) >= 300 ? Math.round(a / 5) * 5 : Math.round(a); return (r > 0 ? '+' : '−') + Math.abs(r).toLocaleString('en-US'); }
  async function bookInit() {
    if (BOOK.cfg) return;
    let cfg = {};
    try { cfg = await fetch('book-config.json?t=' + Date.now()).then(r => r.json()); } catch (e) {}
    BOOK.cfg = Object.assign({ max_stake: null, max_win: null, credit_limit: null, vig: 0.08 }, cfg);
    BOOK.remote = !!(BOOK.cfg.supabase_url && BOOK.cfg.supabase_anon_key);
    try { BOOK.me = localStorage.getItem('bettor'); } catch (e) {}
    if (!T[BOOK.me]) BOOK.me = null;
    await loadBets();
  }
  const sbHeaders = () => ({ apikey: BOOK.cfg.supabase_anon_key, Authorization: 'Bearer ' + BOOK.cfg.supabase_anon_key, 'Content-Type': 'application/json' });
  async function loadBets() {
    BOOK.error = null;
    let rows = [];
    if (BOOK.remote) {
      try {
        const r = await fetch(BOOK.cfg.supabase_url.replace(/\/$/, '') + '/rest/v1/bets?select=*&order=id.asc', { headers: sbHeaders() });
        if (!r.ok) throw new Error(await r.text());
        rows = await r.json();
      } catch (e) { BOOK.error = 'The shared bet ledger could not be reached. Reload to try again.'; }
    } else {
      try { rows = JSON.parse(localStorage.getItem('paper_bets') || '[]'); } catch (e) {}
    }
    const cash = {};
    rows.filter(b => b.kind === 'cashout').forEach(c => { cash[c.ref] = +c.amount; });
    BOOK.bets = rows.filter(b => b.kind !== 'cashout').map(b => Object.assign({}, b, { stake: +b.stake, price: +b.price, to_win: +b.to_win, bettor: String(b.bettor), team: String(b.team), cashed: cash[b.id] }));
    BOOK.raw = rows;
  }
  async function saveRow(row) {
    if (BOOK.remote) {
      const r = await fetch(BOOK.cfg.supabase_url.replace(/\/$/, '') + '/rest/v1/bets', { method: 'POST', headers: Object.assign({ Prefer: 'return=minimal' }, sbHeaders()), body: JSON.stringify(row) });
      if (!r.ok) { let m = 'That was not saved. Try again.'; try { m = (await r.json()).message || m; } catch (e) {} throw new Error(m); }
    } else {
      const rows = BOOK.raw || []; rows.push(Object.assign({ id: Date.now(), created_at: new Date().toISOString() }, row));
      try { localStorage.setItem('paper_bets', JSON.stringify(rows)); } catch (e) {}
    }
    await loadBets();
  }
  function ptClock() {               // hours since Sunday 10 am Pacific, and whether the odds are from this week
    const pt = new Date(new Date().toLocaleString('en-US', { timeZone: 'America/Los_Angeles' }));
    const since = ((pt.getDay() * 24 + pt.getHours() + pt.getMinutes() / 60) - 10 + 168) % 168;
    return { since, fresh: (Date.now() - new Date(D.updated).getTime()) / 36e5 <= since - 38 };
  }
  function bookStatus(market) {      // futures close while games are played; game bets close at Thursday kickoff
    if (D.season_over) return { open: false, why: 'The season is over. Everything is settled.' };
    const c = ptClock();
    if (c.since < 38) return { open: false, why: 'Trading is paused while this week\'s games are played. It reopens Tuesday once the odds update.' };
    if (!c.fresh) return { open: false, why: 'Waiting for this week\'s odds update. Trading reopens as soon as it lands.' };
    if (market === 'game' && c.since >= 103.25) return { open: false, why: `Week ${D.week} game bets closed at Thursday kickoff. Next week's games open Tuesday.` };
    return { open: true };
  }
  function prob(b) {                 // current model chance that this bet's side wins; undefined when unknown
    if (b.market === 'game') {
      const g = D.games.find(x => x.week === b.week && (String(x.home) === b.team || String(x.away) === b.team));
      return g ? (String(g.home) === b.team ? g.p_home : 1 - g.p_home) : undefined;
    }
    const p = D.teams[b.team] ? D.teams[b.team][b.market] : undefined;
    return p == null ? undefined : (b.side === 'yes' ? p : 1 - p);
  }
  function settle(b) {               // profit once decided, else null
    if (b.cashed != null) return b.cashed - b.stake;
    if (b.market === 'game') {
      const g = D.results.find(x => x.week === b.week && (String(x.home) === b.team || String(x.away) === b.team));
      if (!g) return null;
      const us = String(g.home) === b.team ? g.hs : g.as, them = String(g.home) === b.team ? g.as : g.hs;
      return us > them ? b.to_win : us < them ? -b.stake : 0;
    }
    const o = D.outcomes && D.outcomes[b.market] ? D.outcomes[b.market][b.team] : undefined;
    if (o === undefined) return null;
    return ((b.side === 'yes') === !!o) ? b.to_win : -b.stake;
  }
  function cashValue(b) {            // what the house pays to close an open futures bet now
    if (b.market === 'game' || settle(b) !== null) return null;
    const ps = prob(b); if (ps == null) return null;
    return Math.round((b.stake + b.to_win) * Math.max(0, ps * (1 - BOOK.cfg.vig) - 0.005) * 100) / 100;
  }
  function markValue(b) { const ps = prob(b); return ps == null ? b.stake : (b.stake + b.to_win) * ps; }   // fair value of an open bet
  function wallet(id) {
    const mine = BOOK.bets.filter(b => b.bettor === String(id));
    let settled = 0, risk = 0, value = 0, staked = 0;
    mine.forEach(b => { staked += b.stake; const r = settle(b); if (r === null) { risk += b.stake; value += markValue(b); } else settled += r; });
    const total = settled + value - risk;
    return { settled, risk, value, total, staked, roi: staked ? total / staked : 0, n: mine.length, mine,
      left: BOOK.cfg.credit_limit == null ? Infinity : BOOK.cfg.credit_limit + settled - risk };
  }
  function quote(market, team, side) {
    const ps = prob({ market, team: String(team), side, week: D.week });
    if (ps == null || (market !== 'game' && D.outcomes && D.outcomes[market])) return null;
    if (ps < 0.003 || ps > 0.985) return null;
    return Math.min(0.985, Math.max(0.01, ps * (1 + BOOK.cfg.vig) + 0.005));
  }
  function maxStake(market, team, q) {
    const w = wallet(BOOK.me), c = BOOK.cfg, caps = [[1e7, '']];
    if (c.max_stake != null) { const on = w.mine.filter(b => b.market === market && b.team === String(team) && (market !== 'game' || b.week === D.week)).reduce((a, b) => a + b.stake, 0); caps.push([c.max_stake - on, `You already have ${money(on)} on this event. The limit is ${money(c.max_stake)} an event.`]); }
    if (c.max_win != null) caps.push([Math.floor(c.max_win * q / (1 - q)), `Wins are capped at ${money(c.max_win)}, so this price takes a smaller stake.`]);
    if (c.credit_limit != null) caps.push([Math.floor(w.left), w.left < 1 ? `You have used your ${money(c.credit_limit)} credit line.` : `You have ${money(w.left)} of credit left.`]);
    caps.sort((a, b) => a[0] - b[0]);
    return { max: Math.max(0, Math.floor(caps[0][0])), why: caps[0][1], limited: caps[0][0] < 1e7 };
  }
  function openSlip(market, team, side) {
    const q = quote(market, team, side);
    if (!q) return;
    const lim = maxStake(market, team, q);
    let dlg = $('#slip'); if (dlg) dlg.remove();
    dlg = document.createElement('dialog'); dlg.id = 'slip';
    const what = market === 'game' ? `${esc(T[team].name)} to win in week ${D.week}` : `<span class="side ${side}">${side === 'yes' ? 'Yes' : 'No'}</span> ${esc(T[team].name)}: ${MARKETS[market].toLowerCase()}`;
    dlg.innerHTML = `<form method="dialog"><h3>Bet slip</h3>
      <p class="pick-line">${what}</p>
      <p class="sub">Price ${am(q)} (${Math.round(q * 100)}¢ per $1 of payout). Betting as ${esc(T[BOOK.me].name)}.</p>
      ${lim.max >= 1 ? `<label for="stake">Stake${lim.limited ? `, up to ${money(lim.max)}` : ''}</label>
        <div class="row"><input class="pick" id="stake" type="number" inputmode="numeric" min="1" ${lim.limited ? `max="${lim.max}"` : ''} step="1" value="${Math.min(25, lim.max)}">
        ${[10, 50, 100, 500].filter(v => v <= lim.max).map(v => `<button type="button" class="chipbtn" data-v="${v}">$${v}</button>`).join('')}</div>
        <p class="towin">To win <b id="tw"></b></p>${lim.limited ? `<p class="sub">${lim.why}</p>` : ''}<p class="err" id="sliperr" role="alert"></p>
        <div class="row end"><button type="button" class="btn ghost" id="cancel">Cancel</button><button type="button" class="btn" id="place">Place bet</button></div>`
        : `<p class="err">${lim.why}</p><div class="row end"><button type="button" class="btn ghost" id="cancel">Close</button></div>`}</form>`;
    document.body.appendChild(dlg);
    const inp = $('#stake', dlg), tw = $('#tw', dlg), win = v => Math.round(v * (1 - q) / q * 100) / 100;
    const upd = () => { if (tw) tw.textContent = money(win(Math.max(0, +inp.value || 0))); };
    if (inp) { inp.addEventListener('input', upd); upd(); dlg.querySelectorAll('.chipbtn').forEach(b => b.addEventListener('click', () => { inp.value = b.dataset.v; upd(); })); }
    $('#cancel', dlg).addEventListener('click', () => dlg.close());
    const place = $('#place', dlg);
    if (place) place.addEventListener('click', async () => {
      const v = Math.floor(+inp.value || 0), err = $('#sliperr', dlg);
      if (v < 1 || v > lim.max) { err.textContent = lim.limited ? `Enter a whole-dollar stake from $1 to ${money(lim.max)}.` : 'Enter a whole-dollar stake of at least $1.'; return; }
      place.disabled = true; place.textContent = 'Placing…';
      try {
        await saveRow({ kind: 'bet', bettor: +BOOK.me, market, team: +team, side, stake: v, price: Math.round(q * 1e4) / 1e4, to_win: win(v), week: D.week });
        dlg.close(); viewBook(`Bet placed: ${market === 'game' ? T[team].name + ' to win' : (side === 'yes' ? 'Yes' : 'No') + ' on ' + T[team].name}, ${money(v)} to win ${money(win(v))}.`);
      } catch (e) { err.textContent = e.message; place.disabled = false; place.textContent = 'Place bet'; }
    });
    dlg.addEventListener('close', () => dlg.remove());
    dlg.showModal();
  }
  const betLine = b => b.market === 'game' ? `${esc(T[b.team]?.name || '?')} to win, week ${b.week}` : `<span class="side ${b.side}">${b.side === 'yes' ? 'Yes' : 'No'}</span> ${esc(T[b.team]?.name || '?')}, ${MARKETS[b.market].toLowerCase()}`;
  const moved = (id, m) => { const b = prevSnap?.teams[id]?.[m]; return b == null ? '' : ' ' + delta(D.teams[id][m], b); };
  async function viewBook(flash) {
    if (!BOOK.cfg) { app.innerHTML = '<p class="loading">Opening the book…</p>'; await bookInit(); }
    const c = BOOK.cfg, m = BOOK.market, st = bookStatus(m), w = BOOK.me ? wallet(BOOK.me) : null;
    const px = (mk, id, side, label) => { const q = quote(mk, id, side); return q && st.open ? `<button class="px ${side}" data-mk="${mk}" data-team="${id}" data-side="${side}" ${BOOK.me ? '' : 'disabled'}><span>${label}</span><b>${am(q)}</b><i>${Math.round(q * 100)}¢</i></button>` : `<span class="px off">${mk !== 'game' && D.outcomes && D.outcomes[mk] ? ((side === 'yes') === !!D.outcomes[mk][id] ? 'Won' : 'Lost') : 'Off'}</span>`; };
    let table;
    if (m === 'game') {
      const gs = D.games.filter(g => g.week === D.week);
      table = gs.length ? `<div class="scroll"><table class="book"><thead><tr><th class="l">Week ${D.week} game</th><th class="hm">Projected</th><th>To win</th></tr></thead><tbody>
        ${gs.map(g => [[g.away, 1 - g.p_home, g.proj_away], [g.home, g.p_home, g.proj_home]].map(([id, p, pr], k) => `<tr class="${k ? 'pair-end' : ''}"><td class="l">${teamLink(id)}<span class="sub"> ${pct(p, 0)}</span></td><td class="hm">${pr.toFixed(1)}</td><td>${px('game', id, 'yes', 'Win')}</td></tr>`).join('')).join('')}
        </tbody></table></div>` : '<p class="empty">No games on the board this week.</p>';
    } else {
      const rows = ids.map(id => ({ id, p: D.teams[id][m] })).sort((a, b) => b.p - a.p);
      table = `<div class="scroll"><table class="book"><thead><tr><th class="l">Team</th><th class="hm">Model chance</th><th class="hm">Since last week</th><th>Yes</th><th>No</th></tr></thead><tbody>
        ${rows.map(r => `<tr><td class="l">${teamLink(r.id)}<span class="sub rec-m"> ${pct(r.p)}</span></td><td class="hm">${pct(r.p)}</td><td class="hm">${moved(r.id, m)}</td><td>${px(m, r.id, 'yes', 'Yes')}</td><td>${px(m, r.id, 'no', 'No')}</td></tr>`).join('')}
        </tbody></table></div>`;
    }
    const board = ids.map(id => Object.assign({ id }, wallet(id))).filter(x => x.n).sort((a, b) => b.total - a.total);
    const recent = BOOK.bets.slice(-12).reverse();
    const futOpen = bookStatus('title').open;
    const cls = v => v > 0.005 ? 'up' : v < -0.005 ? 'down' : '';
    app.innerHTML = `<h1>Sportsbook</h1>
      <p class="lede">Paper trading for bragging rights. Bet Yes or No on any team's season, or pick this week's winners. ${c.max_stake == null && c.credit_limit == null ? 'No stake limits.' : ''} Open bets are marked to the latest odds, and you can cash out early.</p>
      ${flash ? `<p class="flash" role="status">${esc(flash)}</p>` : ''}
      ${BOOK.error ? `<p class="note">${BOOK.error}</p>` : ''}
      ${!BOOK.remote ? '<p class="note">Preview mode: bets are saved in this browser only. Once the shared ledger is connected, everyone will see the same bets.</p>' : ''}
      ${!st.open ? `<p class="note">${st.why}</p>` : ''}
      <div class="wallet"><label for="me">Betting as</label><select class="pick" id="me"><option value="">Pick your team</option>${ids.map(t => `<option value="${t}" ${t === BOOK.me ? 'selected' : ''}>${esc(T[t].name)}</option>`).join('')}</select>
        ${w ? `<div><b class="${cls(w.total)}">${money(w.total, true)}</b><span>Profit and loss</span></div><div><b>${money(w.risk)}</b><span>Open stakes</span></div><div><b>${money(w.value)}</b><span>Open bets worth now</span></div><div><b class="${cls(w.settled)}">${money(w.settled, true)}</b><span>Settled</span></div>` : '<span class="sub">Pick your team to place bets.</span>'}</div>
      <div class="row"><div class="seg" role="group" aria-label="Market">${Object.entries(MARKETS).map(([k, v]) => `<button data-m="${k}" aria-pressed="${k === m}">${v}</button>`).join('')}</div></div>
      ${table}
      <p class="sub">${m === 'game' ? 'Pick a team to win its matchup. A tie returns your stake.' : 'Yes pays if it happens, No pays if it does not.'} Prices include the house's cut and are locked in when you place the bet.</p>
      ${w ? `<h2>My bets</h2>${w.mine.length ? `<div class="scroll"><table class="mybets"><thead><tr><th class="l">Bet</th><th>Stake</th><th>To win</th><th>Worth now</th><th>Result</th></tr></thead><tbody>
        ${w.mine.slice().reverse().map(b => { const r = settle(b), cv = cashValue(b); return `<tr><td class="l">${betLine(b)} <span class="sub">${am(b.price)}${b.market === 'game' ? '' : ', week ' + b.week}</span></td><td>${money(b.stake)}</td><td>${money(b.to_win)}</td>
          <td>${r === null ? `${money(markValue(b))}` : '–'}</td><td>${r === null ? (cv != null && futOpen ? `<button class="chipbtn cash" data-id="${b.id}" data-v="${cv}">Cash out ${money(cv)}</button>` : '<span class="sub">Open</span>') : `<b class="${cls(r)}">${money(r, true)}</b>${b.cashed != null ? ' <span class="sub">cashed out</span>' : ''}`}</td></tr>`; }).join('')}
        </tbody></table></div>` : '<p class="empty">No bets yet. Pick a price above to place your first one.</p>'}` : ''}
      <h2>Leaderboard</h2>${board.length ? `<div class="scroll"><table><thead><tr><th class="l" colspan="2">Bettor</th><th>Profit and loss</th><th>Return</th><th class="hm">Settled</th><th class="hm">Open stakes</th><th>Bets</th></tr></thead><tbody>
        ${board.map((x, i) => `<tr><td class="rank">${i + 1}</td><td class="l">${teamLink(x.id)}</td><td class="${cls(x.total)}"><b>${money(x.total, true)}</b></td><td class="${cls(x.roi)}">${(100 * x.roi).toFixed(0)}%</td><td class="hm ${cls(x.settled)}">${money(x.settled, true)}</td><td class="hm">${money(x.risk)}</td><td>${x.n}</td></tr>`).join('')}
        </tbody></table></div><p class="sub">Profit and loss counts settled bets plus what open bets are worth at today's odds. Return is profit per dollar staked.</p>` : '<p class="empty">Nobody has bet yet. Be the first on the board.</p>'}
      ${recent.length ? `<h2>Latest bets</h2><ul class="feed">${recent.map(b => `<li><b>${esc(T[b.bettor]?.name || '?')}</b>: ${betLine(b)} <span class="sub">${money(b.stake)} to win ${money(b.to_win)}</span></li>`).join('')}</ul>` : ''}`;
    $('#me').addEventListener('change', e => { BOOK.me = e.target.value || null; try { localStorage.setItem('bettor', BOOK.me || ''); } catch (x) {} viewBook(); });
    app.querySelector('.seg').addEventListener('click', e => { const b = e.target.closest('button'); if (b) { BOOK.market = b.dataset.m; viewBook(); } });
    const bk = app.querySelector('.book'); if (bk) bk.addEventListener('click', e => { const b = e.target.closest('button.px'); if (b) openSlip(b.dataset.mk, b.dataset.team, b.dataset.side); });
    const mb = app.querySelector('.mybets'); if (mb) mb.addEventListener('click', async e => {
      const b = e.target.closest('button.cash'); if (!b) return;
      if (b.dataset.armed !== '1') { b.dataset.armed = '1'; b.textContent = `Confirm ${money(+b.dataset.v)}`; return; }
      b.disabled = true;
      try { await saveRow({ kind: 'cashout', bettor: +BOOK.me, market: 'cashout', team: 0, side: 'yes', stake: 1, price: 0.5, to_win: 1, week: D.week, ref: +b.dataset.id, amount: +b.dataset.v }); viewBook(`Cashed out for ${money(+b.dataset.v)}.`); }
      catch (x) { viewBook(x.message); }
    });
  }

  // ---------- shell ----------
  $('#league-name').textContent = D.league.name + ' Odds';
  document.title = D.league.name + ' Odds Board';
  const when = new Date(D.updated);
  $('#stamp').textContent = `Updated ${when.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}. ${D.sims.toLocaleString('en-US')} simulated seasons. Sources: ${D.sources.join(', ')}.`;
  if (D.sample) { const b = $('#banner'); b.hidden = false; b.textContent = 'Sample data: team names and early results are real, but players and current odds are placeholders until the first live update runs.'; }
  function route() {
    const [, sec, arg] = (location.hash || '#/').split('/');
    const name = sec === 'team' ? 'teams' : (sec || 'board');
    document.querySelectorAll('nav a').forEach(a => a.dataset.nav === name ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current'));
    ({ week: viewWeek, teams: viewTeams, team: () => viewTeam(arg), players: viewPlayers, about: viewAbout, book: () => viewBook() }[sec] || viewBoard)();
  }
  addEventListener('hashchange', () => { route(); scrollTo(0, 0); });
  route();
})();
