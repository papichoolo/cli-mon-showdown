// DOM Elements - Login Screen
const loginScreen = document.getElementById('login-screen');
const battleScreen = document.getElementById('battle-screen');
const connectBtn = document.getElementById('connect-btn');
const usernameInput = document.getElementById('username');
const passwordInput = document.getElementById('password');
const formatInput = document.getElementById('format');
const loginStatus = document.getElementById('login-status');
const modeOptions = document.querySelectorAll('input[name="mode"]');
const remoteFields = document.getElementById('remote-fields');

// DOM Elements - Battle
const logContainer = document.getElementById('battle-log');
const actionButtons = document.getElementById('action-buttons');
const aiThoughts = document.getElementById('ai-thoughts');
const aiReasoning = document.getElementById('ai-reasoning');
const aiStatus = document.getElementById('ai-status');
const controlsPanel = document.getElementById('controls-panel');
const newBattleBtn = document.getElementById('new-battle-btn');
const showdownLink = document.getElementById('showdown-link');
const localArena = document.getElementById('local-arena');

const p1Name = document.getElementById('p1-name');
const p1HpFill = document.getElementById('p1-hp-fill');
const p1Tags = document.getElementById('p1-tags');
const p2Name = document.getElementById('p2-name');
const p2HpFill = document.getElementById('p2-hp-fill');
const p2Tags = document.getElementById('p2-tags');

let ws = null;
let currentP1Request = null;
let isRemote = true;

// UI Helpers
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
    const title = document.createElement('h4');
    title.textContent = 'Forced Switch';
    title.className = 'controls-section-title';
    actionButtons.appendChild(title);
    
    const grid = document.createElement('div');
    grid.className = 'actions-grid';
    actionButtons.appendChild(grid);
    
    const pokes = req.side?.pokemon || [];
    pokes.forEach((p, index) => {
      const idx = index + 1;
      const isFnt = p.condition && p.condition.includes('fnt');
      if (!p.active && !isFnt) {
        const btn = document.createElement('button');
        btn.className = 'action-btn switch';
        btn.innerHTML = `
          <div class="btn-content">
            <span class="mon-name">${p.details.split(',')[0]}</span>
            <span class="btn-sub">${p.condition}</span>
          </div>
        `;
        btn.onclick = () => sendAction(`switch ${idx}`);
        grid.appendChild(btn);
      }
    });
    return;
  }
  
  if (req.active) {
    const title = document.createElement('h4');
    title.textContent = 'Moves';
    title.className = 'controls-section-title';
    actionButtons.appendChild(title);
    
    const grid = document.createElement('div');
    grid.className = 'actions-grid';
    actionButtons.appendChild(grid);
    
    const moves = req.active[0].moves || [];
    moves.forEach((m, index) => {
        const idx = index + 1;
        if (!m.disabled) {
            const btn = document.createElement('button');
            btn.className = 'action-btn move';
            btn.innerHTML = `
              <div class="btn-content">
                <span class="move-name">${m.move}</span>
                <span class="btn-sub">PP: ${m.pp}/${m.maxpp}</span>
              </div>
            `;
            btn.onclick = () => sendAction(`move ${idx}`);
            grid.appendChild(btn);
        }
    });
  }
  
  const pokes = req.side?.pokemon || [];
  const validSwitches = pokes.filter(p => !p.active && !(p.condition && p.condition.includes('fnt')));
  
  if (validSwitches.length > 0) {
    const title = document.createElement('h4');
    title.textContent = 'Switch To';
    title.className = 'controls-section-title';
    title.style.marginTop = '16px';
    actionButtons.appendChild(title);
    
    const grid = document.createElement('div');
    grid.className = 'actions-grid';
    actionButtons.appendChild(grid);
    
    pokes.forEach((p, index) => {
      const idx = index + 1;
      const isFnt = p.condition && p.condition.includes('fnt');
      if (!p.active && !isFnt) {
          const btn = document.createElement('button');
          btn.className = 'action-btn switch';
          btn.innerHTML = `
            <div class="btn-content">
              <span class="mon-name">${p.details.split(',')[0]}</span>
              <span class="btn-sub">${p.condition}</span>
            </div>
          `;
          btn.onclick = () => sendAction(`switch ${idx}`);
          grid.appendChild(btn);
      }
    });
  }
}

// Setup logic
modeOptions.forEach(opt => {
  opt.onchange = () => {
    isRemote = opt.value === 'remote';
    remoteFields.classList.toggle('hidden', !isRemote);
  };
});

connectBtn.onclick = () => {
  if (ws) return; // Prevent multiple connections
  connectBtn.disabled = true;
  connectBtn.textContent = 'Connecting...';
  
  const config = {
    remote: isRemote,
    username: usernameInput.value,
    password: passwordInput.value,
    format: formatInput.value
  };

  loginStatus.textContent = "Connecting...";
  loginStatus.className = "login-status";

  ws = new WebSocket('ws://localhost:8000/ws/battle');
  
  ws.onopen = () => {
    ws.send(JSON.stringify({ config }));
    loginScreen.classList.add('hidden');
    battleScreen.classList.remove('hidden');
    if (!isRemote) {
        controlsPanel.classList.remove('hidden');
        localArena.classList.remove('hidden');
    }
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'status') {
      addLog(msg.message, 'system');
    } else if (msg.type === 'error') {
      loginStatus.textContent = msg.message;
      loginStatus.className = "login-status error";
      loginScreen.classList.remove('hidden');
      battleScreen.classList.add('hidden');
      connectBtn.disabled = false;
      connectBtn.textContent = 'Connect & Start Battle';
      if (ws) {
        ws.close();
        ws = null;
      }
    } else if (msg.type === 'log') {
      addLog(msg.message);
    } else if (msg.type === 'room') {
      showdownLink.href = msg.url;
      showdownLink.classList.remove('hidden');
    } else if (msg.type === 'win') {
      addLog(`🎉 ${msg.winner} won the battle! 🎉`, 'system');
      newBattleBtn.classList.remove('hidden');
    } else if (msg.type === 'state_sync') {
      updateState(msg.battle);
      if (!isRemote && msg.p1_request) {
          currentP1Request = msg.p1_request;
          renderControls(currentP1Request);
          aiStatus.textContent = "Waiting for your action...";
      }
    } else if (msg.type === 'ai_insight') {
      aiStatus.textContent = "Gemini has made a decision!";
      const aiInput = document.getElementById('ai-input');
      if (aiInput) aiInput.textContent = msg.input || 'No input context available.';
      aiThoughts.textContent = msg.thoughts || 'No thoughts generated.';
      aiThoughts.scrollTop = aiThoughts.scrollHeight;
      aiReasoning.textContent = msg.reasoning || '—';
    }
  };

  ws.onclose = () => {
    addLog('Connection lost. Please refresh.', 'system');
    aiStatus.textContent = "Disconnected.";
    ws = null;
    connectBtn.disabled = false;
    connectBtn.textContent = 'Connect & Start Battle';
  };
};

newBattleBtn.onclick = () => {
  if (ws) {
    ws.close();
    ws = null;
  }
  battleScreen.classList.add('hidden');
  loginScreen.classList.remove('hidden');
  newBattleBtn.classList.add('hidden');
  showdownLink.classList.add('hidden');
  logContainer.innerHTML = '<div class="log-entry system">Connecting to simulator...</div>';
  const aiInput = document.getElementById('ai-input');
  if (aiInput) aiInput.textContent = 'Waiting for turn...';
  aiThoughts.innerHTML = '<span class="muted">Awaiting observation...</span>';
  aiReasoning.textContent = '—';
  aiStatus.textContent = 'Monitoring battle state...';
  connectBtn.disabled = false;
  connectBtn.textContent = 'Connect & Start Battle';
};
