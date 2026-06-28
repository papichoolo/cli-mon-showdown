const ws = new WebSocket('ws://localhost:8000/ws/battle');

// DOM Elements
const logContainer = document.getElementById('battle-log');
const actionButtons = document.getElementById('action-buttons');
const aiThoughts = document.getElementById('ai-thoughts');
const aiReasoning = document.getElementById('ai-reasoning');
const aiStatus = document.getElementById('ai-status');

const p1Name = document.getElementById('p1-name');
const p1HpFill = document.getElementById('p1-hp-fill');
const p1Tags = document.getElementById('p1-tags');
const p2Name = document.getElementById('p2-name');
const p2HpFill = document.getElementById('p2-hp-fill');
const p2Tags = document.getElementById('p2-tags');

let currentP1Request = null;

// Helpers
function addLog(text, type = 'normal') {
  const el = document.createElement('div');
  el.className = `log-entry ${type}`;
  el.textContent = text;
  logContainer.appendChild(el);
  logContainer.scrollTop = logContainer.scrollHeight;
}

function updateHpBar(fillEl, hp, maxhp, pct) {
  let percentage = pct;
  if (hp !== undefined && maxhp !== undefined && maxhp > 0) percentage = (hp / maxhp) * 100;
  if (percentage === undefined || percentage === null) percentage = 0;
  
  fillEl.style.width = `${Math.max(0, Math.min(100, percentage))}%`;
  
  fillEl.classList.remove('high', 'medium', 'low');
  if (percentage > 50) fillEl.classList.add('high');
  else if (percentage > 20) fillEl.classList.add('medium');
  else fillEl.classList.add('low');
}

function renderTags(container, status, fainted) {
  container.innerHTML = '';
  if (fainted) {
      const tag = document.createElement('span');
      tag.className = 'tag bg-red';
      tag.style.background = '#000';
      tag.textContent = 'FNT';
      container.appendChild(tag);
  } else if (status) {
      const tag = document.createElement('span');
      tag.className = `tag ${status}`;
      tag.textContent = status.toUpperCase();
      container.appendChild(tag);
  }
}

function updateState(battle) {
  if (!battle) return;
  const p1 = battle.p1 || {};
  const p2 = battle.p2 || {};

  p1Name.textContent = p1.name || '?';
  updateHpBar(p1HpFill, p1.hp, p1.maxhp, p1.hp_pct);
  renderTags(p1Tags, p1.status, p1.fainted);

  p2Name.textContent = p2.name || '?';
  updateHpBar(p2HpFill, p2.hp, p2.maxhp, p2.hp_pct);
  renderTags(p2Tags, p2.status, p2.fainted);
}

function sendAction(actionStr) {
  actionButtons.innerHTML = '<p class="placeholder-text">Waiting for opponent...</p>';
  ws.send(JSON.stringify({ type: 'action', action: actionStr }));
}

function renderControls(req) {
  if (!req) return;
  actionButtons.innerHTML = '';
  
  if (req.forceSwitch) {
    const pokes = req.side?.pokemon || [];
    pokes.forEach((p, index) => {
      // Showdown 1-indexed
      const idx = index + 1;
      const isFnt = p.condition && p.condition.includes('fnt');
      if (!p.active && !isFnt) {
        const btn = document.createElement('button');
        btn.className = 'action-btn switch';
        btn.innerHTML = `${p.details.split(',')[0]} <span class="btn-sub">${p.condition}</span>`;
        btn.onclick = () => sendAction(`switch ${idx}`);
        actionButtons.appendChild(btn);
      }
    });
    return;
  }

  if (req.active) {
    const moves = req.active[0].moves || [];
    moves.forEach((m, index) => {
        const idx = index + 1;
        if (!m.disabled) {
            const btn = document.createElement('button');
            btn.className = 'action-btn move';
            btn.innerHTML = `${m.move} <span class="btn-sub">PP: ${m.pp}/${m.maxpp}</span>`;
            btn.onclick = () => sendAction(`move ${idx}`);
            actionButtons.appendChild(btn);
        }
    });
  }

  const pokes = req.side?.pokemon || [];
  pokes.forEach((p, index) => {
    const idx = index + 1;
    const isFnt = p.condition && p.condition.includes('fnt');
    if (!p.active && !isFnt) {
        const btn = document.createElement('button');
        btn.className = 'action-btn switch';
        btn.innerHTML = `Switch to ${p.details.split(',')[0]} <span class="btn-sub">${p.condition}</span>`;
        btn.onclick = () => sendAction(`switch ${idx}`);
        actionButtons.appendChild(btn);
    }
  });
}

// Websocket Handling
ws.onopen = () => {
  addLog('WebSocket connection established', 'system');
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  
  if (msg.type === 'log') {
    addLog(msg.message);
  } else if (msg.type === 'state_sync') {
    updateState(msg.battle);
    if (msg.p1_request) {
        currentP1Request = msg.p1_request;
        renderControls(currentP1Request);
        aiStatus.textContent = "Waiting for human action...";
    }
  } else if (msg.type === 'ai_insight') {
    aiStatus.textContent = "Gemini has made a decision!";
    
    // Animate typing thoughts
    aiThoughts.textContent = '';
    const textToType = msg.thoughts || 'No thoughts generated for this simple turn.';
    let i = 0;
    const typeInterval = setInterval(() => {
        aiThoughts.textContent += textToType.charAt(i);
        aiThoughts.scrollTop = aiThoughts.scrollHeight;
        i++;
        if (i >= textToType.length) {
            clearInterval(typeInterval);
        }
    }, 10);
    
    aiReasoning.textContent = msg.reasoning || 'Default logic fallback';
  }
};

ws.onclose = () => {
  addLog('Connection lost. Please refresh.', 'system');
  aiStatus.textContent = "Disconnected.";
  aiThoughts.innerHTML = '<span class="muted">Connection lost...</span>';
};
